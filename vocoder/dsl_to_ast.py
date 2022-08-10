import itertools
import sys
import typing as t
from collections import deque
from dataclasses import dataclass
from inspect import signature

from lark import Transformer, Tree, ast_utils

from vocoder import exceptions
from vocoder.actions import (
    Captures,
    ClosureValue,
    LexiconAttributor,
    action,
    push_immutable,
    push_mutable,
    push_namespace,
    sequence,
    snoc,
    snoc_closure_namespace,
)
from vocoder.soft import (
    Soft,
    add_batch_separator_reflection,
    add_choice_transitions,
    add_skip_transition,
    add_symbol_transition,
)
from vocoder.utils import transitive_closure

this_module = sys.modules[__name__]


class _Ast(ast_utils.Ast):
    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        raise NotImplementedError

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        raise NotImplementedError

    def nonterminal_dependencies(self) -> set[str]:
        raise NotImplementedError

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        raise NotImplementedError


def compile_ast(rules: dict[str, "_Ast"]) -> Soft:
    dependencies = {nt: ast.nonterminal_dependencies() for nt, ast in rules.items()}
    for nt in itertools.chain(*dependencies.values()):
        if nt not in dependencies:
            raise exceptions.UndefinedNonterminalError

    dependencies = transitive_closure(dependencies)
    for nt, deps in dependencies.items():
        if nt in deps:
            raise exceptions.CircularNonterminalError

    for node in itertools.chain(*(top.iter_nodes() for top in rules.values())):
        match node:
            case Closure() | PositiveClosure():
                if node.child.nullable(rules):
                    raise exceptions.ConfigError(
                        "closures cannot have nullable children"
                    )
            case AttributedExpression():
                node.validate()

    soft = Soft()
    rules["start"].compile(
        soft,
        rules,
        soft.initial,
        soft.new_state(),
        False,
        False,
    )
    return soft


@dataclass
class Cat(_Ast, ast_utils.AsList):
    children: list[_Ast]

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        if with_return:
            initial = add_skip_transition(soft, initial, push_mutable(list))

        for child in self.children:
            if not within_utterance and not child.nullable(rules):
                initial = add_batch_separator_reflection(soft, initial)

            child_final = soft.new_state()
            child.compile(
                soft,
                rules,
                initial,
                child_final,
                within_utterance,
                with_return,
            )
            if with_return:
                initial = add_skip_transition(soft, child_final, snoc)
            else:
                initial = child_final

        add_skip_transition(soft, initial, None, final)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return all(child.nullable(rules) for child in self.children)

    def nonterminal_dependencies(self) -> set[str]:
        return set().union(
            *(child.nonterminal_dependencies() for child in self.children)
        )

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from itertools.chain(*(child.iter_nodes() for child in self.children))


@dataclass
class Alt(_Ast, ast_utils.AsList):
    children: list[_Ast]

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        if not within_utterance and not all(
            child.nullable(rules) for child in self.children
        ):
            initial = add_batch_separator_reflection(soft, initial)

        children_initial_states = add_choice_transitions(
            soft, initial, n_choices=len(self.children)
        )

        for child, state in zip(self.children, children_initial_states):
            child.compile(
                soft,
                rules,
                state,
                final,
                within_utterance,
                with_return,
            )

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return any(child.nullable(rules) for child in self.children)

    def nonterminal_dependencies(self) -> set[str]:
        return set().union(
            *(child.nonterminal_dependencies() for child in self.children)
        )

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from itertools.chain(*(child.iter_nodes() for child in self.children))


@dataclass
class Nonterminal(_Ast):
    name: str

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        expression = rules[self.name]
        expression.compile(
            soft,
            rules,
            initial,
            final,
            within_utterance,
            with_return,
        )

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return rules[self.name].nullable(rules)

    def nonterminal_dependencies(self) -> set[str]:
        return {self.name}

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self


@dataclass
class AttributedExpression(_Ast):
    expression: _Ast
    attribute: t.Callable
    capture_keys: set[int | str]

    def validate(self):
        int_keys = {i for i in self.capture_keys if isinstance(i, int)}
        if int_keys:
            max_int_key = max(int_keys)
            if int_keys != set(i for i in range(1, max_int_key + 1)):
                raise exceptions.ConfigError(
                    "Attribute signature does not match captures"
                )
        sig = signature(self.attribute)
        if not sum(p != "env" for p in sig.parameters) == len(self.capture_keys):
            raise exceptions.ConfigError("Incorrect number of attribute args")
        str_keys = {k for k in self.capture_keys if isinstance(k, str)}
        if not str_keys <= set(sig.parameters):
            raise exceptions.ConfigError(
                "Named captures with no corresponding attribute arg"
            )

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):

        penultimate = soft.new_state()

        @action
        def _action(
            value_stack: list,
            namespace_stack: list[Captures],
            env: t.Any,
        ) -> None:
            value_stack.pop()
            namespace = namespace_stack.pop()

            sig = signature(self.attribute)
            args = []
            named_params = {a for a in namespace if isinstance(a, str)}
            current_pos = 1
            for param in sig.parameters:
                if param == "env":
                    args.append(env)
                elif param in named_params:
                    args.append(namespace[param])
                else:
                    args.append(namespace[current_pos])
                    current_pos += 1
            try:
                value = self.attribute(*args)
            except Exception as e:
                raise exceptions.AttributeFailedError(e)
            if with_return:
                value_stack.append(value)

        initial = add_skip_transition(soft, initial, push_namespace(self.capture_keys))

        self.expression.compile(
            soft,
            rules,
            initial,
            penultimate,
            within_utterance,
            True,
        )
        add_skip_transition(soft, penultimate, _action, final)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return self.expression.nullable(rules)

    def nonterminal_dependencies(self) -> set[str]:
        return self.expression.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.expression.iter_nodes()


@dataclass
class Lexicon(_Ast):
    predicate: str

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        if not within_utterance:
            initial = add_batch_separator_reflection(soft, initial)

        @action
        def _action(
            value_stack: list,
            words: deque[str],
            lexicon_attributor: LexiconAttributor,
        ):
            word = words.popleft()
            if with_return:
                value = lexicon_attributor(self.predicate, word)
                value_stack.append(value)

        add_symbol_transition(soft, initial, self.predicate, _action, final)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return False

    def nonterminal_dependencies(self) -> set[str]:
        return set()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self


@dataclass
class PositionalCapture(_Ast):
    child: _Ast
    position: int

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        if not with_return:
            raise exceptions.ConfigError

        @action
        def _action(value_stack: list, namespace_stack: list[Captures]):
            value = value_stack[-1]
            namespace_stack[-1][int(self.position)] = value

        intermediate = soft.new_state()

        self.child.compile(
            soft,
            rules,
            initial,
            intermediate,
            within_utterance,
            with_return,
        )
        add_skip_transition(soft, intermediate, _action, final)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return self.child.nullable(rules)

    def nonterminal_dependencies(self) -> set[str]:
        return self.child.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.child.iter_nodes()


@dataclass
class NamedCapture(_Ast):
    child: _Ast
    alias: str

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        if not with_return:
            raise exceptions.ConfigError

        @action
        def _action(value_stack: list, namespace_stack: list[Captures]):
            value = value_stack[-1]
            namespace_stack[-1][self.alias] = value

        intermediate = soft.new_state()
        self.child.compile(
            soft,
            rules,
            initial,
            intermediate,
            within_utterance,
            with_return,
        )
        add_skip_transition(soft, intermediate, _action, final)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return self.child.nullable(rules)

    def nonterminal_dependencies(self) -> set[str]:
        return self.child.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.child.iter_nodes()


class Null(_Ast):
    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        add_skip_transition(soft, initial, push_immutable(None), final)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return True

    def nonterminal_dependencies(self) -> set[str]:
        return set()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self


@dataclass
class Closure(_Ast):
    child: _Ast
    capture_keys: set[int | str]

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):

        if not with_return:
            assert not self.capture_keys

            next_state, _ = add_choice_transitions(
                soft, initial, next_states=(None, final)
            )
            if not within_utterance:
                next_state = add_batch_separator_reflection(soft, next_state)

            self.child.compile(
                soft,
                rules,
                next_state,
                initial,
                within_utterance,
                with_return,
            )
        else:
            """
                                                ┌──push namespace───►state_3
                                                │                       │
                                                │                       │
                                                │                       │
            initial────_/push closure value────►state_2 ◄────child aut────┘
                                                │
                                                │
                                                └───cost 1───────►end
            """
            state_2 = add_skip_transition(soft, initial, push_mutable(ClosureValue))
            state_3, _ = add_choice_transitions(
                soft, state_2, next_states=(None, final)
            )
            if not within_utterance:
                state_3 = add_batch_separator_reflection(soft, state_3)
            state_4 = add_skip_transition(
                soft, state_3, push_namespace(self.capture_keys)
            )
            state_5 = soft.new_state()

            self.child.compile(
                soft,
                rules,
                state_4,
                state_5,
                within_utterance,
                with_return,
            )

            add_skip_transition(
                soft, state_5, sequence(snoc, snoc_closure_namespace), state_2
            )

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return True

    def nonterminal_dependencies(self) -> set[str]:
        return self.child.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.child.iter_nodes()


@dataclass
class Maybe(_Ast):
    child: _Ast

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        if not within_utterance and not self.child.nullable(rules):
            initial = add_batch_separator_reflection(soft, initial)

        if with_return:
            child_initial, _ = add_choice_transitions(
                soft,
                initial,
                outputs=(None, push_immutable(None)),
                next_states=(None, final),
            )
        else:
            child_initial, _ = add_choice_transitions(
                soft, initial, next_states=(None, final)
            )

        self.child.compile(
            soft,
            rules,
            child_initial,
            final,
            within_utterance,
            with_return,
        )

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return True

    def nonterminal_dependencies(self) -> set[str]:
        return self.child.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.child.iter_nodes()


@dataclass
class PositiveClosure(_Ast):
    child: _Ast
    capture_keys: set[int | str]

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):

        if not with_return:
            if not within_utterance:
                second = add_batch_separator_reflection(soft, initial)
            else:
                second = add_skip_transition(soft, initial)
            penultimate = soft.new_state()
            self.child.compile(
                soft,
                rules,
                second,
                penultimate,
                within_utterance,
                with_return,
            )
            add_choice_transitions(soft, penultimate, next_states=(initial, final))

        else:
            initial = add_skip_transition(
                soft,
                initial,
                sequence(push_mutable(ClosureValue)),
            )
            if not within_utterance:
                second = add_batch_separator_reflection(soft, initial)
            else:
                second = add_skip_transition(soft, initial)
            child_initial = add_skip_transition(
                soft, second, push_namespace(self.capture_keys)
            )
            penultimate = soft.new_state()
            child_final = soft.new_state()
            self.child.compile(
                soft,
                rules,
                child_initial,
                child_final,
                within_utterance,
                with_return,
            )
            add_skip_transition(
                soft, child_final, sequence(snoc, snoc_closure_namespace), penultimate
            )
            add_choice_transitions(soft, penultimate, next_states=(initial, final))

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return self.child.nullable(rules)

    def nonterminal_dependencies(self) -> set[str]:
        return self.child.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.child.iter_nodes()


@dataclass
class WithinUtteranceExpression(_Ast):
    child: _Ast

    def compile(
        self,
        soft: Soft,
        rules: dict[str, "_Ast"],
        initial: int,
        final: int,
        within_utterance: bool,
        with_return: bool,
    ):
        self.child.compile(soft, rules, initial, final, True, with_return)

    def nullable(self, rules: dict[str, "_Ast"]) -> bool:
        return self.child.nullable(rules)

    def nonterminal_dependencies(self) -> set[str]:
        return self.child.nonterminal_dependencies()

    def iter_nodes(self) -> t.Iterator["_Ast"]:
        yield self
        yield from self.child.iter_nodes()


class ToAst(Transformer):
    def start(self, children):
        assert all(child.data == "nonterminal_assignment" for child in children)
        definitions = dict(a.children for a in children)
        assert "start" in definitions
        assert all(isinstance(key, str) for key in definitions)
        assert all(isinstance(expr, _Ast) for expr in definitions.values())
        return definitions


def dsl_to_ast(tree: Tree) -> dict[str, _Ast]:
    ast = ast_utils.create_transformer(this_module, ToAst()).transform(tree)
    return ast
