"Simulate a nondeterministic symbolic ordered finite transducer"

import typing as t
from collections import deque
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from loguru import logger

from vocoder import exceptions
from vocoder.actions import Action
from vocoder.lexicon_registry import LexiconRegistry
from vocoder.soft import Soft, SpecialPredicate, StateType, Transition


@dataclass
class Node:
    state: int
    parent: t.Optional["Node"] = None
    parent_transition: Transition | None = None
    valuation: Action | None = None


"leaves of the path tree, ordered correctly with deduplicated soft states and at most one final state"
PathLeaves = list[Node]


def step_tree(
    soft: Soft,
    nodes: list[Node],
) -> PathLeaves:
    nodes = nodes[::-1].copy()
    leaves = list[Node]()
    leaf_states = set[int]()
    has_final_state = False
    while nodes:
        node = nodes.pop()

        match soft.state_type(node.state):
            case StateType.SKIP:
                t = soft.skip_transitions[node.state]
                node = Node(t.target, node, t, t.output)
                nodes.append(node)
            case StateType.FINAL:
                if not has_final_state:
                    leaves.append(node)
                    has_final_state = True
            case StateType.CHOICE:
                for t in reversed(soft.choice_transitions[node.state]):
                    child = Node(t.target, node, t, t.output)
                    nodes.append(child)
            case StateType.SYMBOL:
                if node.state not in leaf_states:
                    leaves.append(node)
                    leaf_states.add(node.state)

    return leaves


def _least_common_ancestor(x: Node, y: Node) -> Node:
    x_ancestors = set([id(x)])
    node = x
    while node.parent is not None:
        node = node.parent
        x_ancestors.add(id(node))

    node = y
    while id(node) not in x_ancestors:
        assert node.parent is not None, f"x/y have no common ancestor"
        node = node.parent
    return node


def least_common_ancestor(nodes: Sequence[Node]) -> Node:
    if len(nodes) == 0:
        raise RuntimeError
    lca = nodes[0]
    for node in nodes[1:]:
        lca = _least_common_ancestor(lca, node)
    return lca


def transition_from_word(
    soft: Soft, lexicon_registry: LexiconRegistry, path_leaves: PathLeaves, word: str
) -> PathLeaves:
    leaves = list[Node]()

    for node in path_leaves:
        if soft.is_symbol_state(node.state):
            t = soft.symbol_transitions[node.state]
            if not isinstance(t.predicate, SpecialPredicate):
                if word in lexicon_registry._lexicons[t.predicate]:
                    leaves.append(Node(t.target, node, t, t.output))
    return leaves


def batch_separator_transition(soft: Soft, path_leaves: PathLeaves) -> PathLeaves:
    leaves = list[Node]()

    for node in path_leaves:
        match soft.state_type(node.state):
            case StateType.FINAL:
                leaves.append(node)
            case StateType.SYMBOL:
                t = soft.symbol_transitions[node.state]
                if t.predicate == SpecialPredicate.BATCH_SEPARATOR:
                    leaves.append(Node(t.target, node, t, t.output))
    return leaves


def get_predicate_transitions(soft: Soft, path_leaves: PathLeaves) -> list[str]:
    out = list[str]()
    for node in path_leaves:
        if soft.is_symbol_state(node.state):
            pred = soft.symbol_transitions[node.state].predicate
            if not isinstance(pred, SpecialPredicate):
                out.append(pred)
    return out


def assert_valid_transition(
    soft: Soft, lexicon_registry: LexiconRegistry, path_leaves: PathLeaves, word: str
):

    if word not in lexicon_registry.get_union(
        *get_predicate_transitions(soft, path_leaves)
    ):
        raise exceptions.InvalidWordTransition


def simplify(path_leaves: PathLeaves) -> tuple[PathLeaves, deque[Action]]:
    output = deque[Action]()
    if not path_leaves:
        return path_leaves, output
    lca = least_common_ancestor(path_leaves)
    if lca.valuation is not None:
        output.appendleft(lca.valuation)
    node = lca
    while node.parent is not None:
        node = node.parent
        if node.valuation is not None:
            output.appendleft(node.valuation)
    lca.parent = lca.valuation = None
    return path_leaves, output


def text_simulate(
    soft: Soft,
    initial_leaves: PathLeaves,
    lexicon_registry: LexiconRegistry,
    utterance: str,
) -> tuple[deque[str], PathLeaves]:
    words = deque(utterance.strip().split())
    path_leaves = initial_leaves.copy()
    if words:
        path_leaves = step_tree(soft, path_leaves)
        for word in words:
            assert_valid_transition(soft, lexicon_registry, path_leaves, word)
            path_leaves = transition_from_word(
                soft, lexicon_registry, path_leaves, word
            )
            path_leaves = step_tree(soft, path_leaves)
        path_leaves = batch_separator_transition(soft, path_leaves)
        path_leaves = step_tree(soft, path_leaves)
    return words, path_leaves


def initial_path_leaves(soft: Soft) -> PathLeaves:
    return step_tree(soft, [Node(soft.initial)])


@dataclass
class Executor:
    _lexicon_registry: LexiconRegistry
    _env: t.Any = None

    _words: deque[str] = field(default_factory=deque, init=False)
    _value_stack: list = field(default_factory=list, init=False)
    _namespace_stack: list = field(default_factory=list, init=False)

    def eat(self, new_words: Iterable[str], output: t.Iterable[Action]):
        self._words.extend(new_words)

        for action in output:
            try:
                action(
                    self._value_stack,
                    self._namespace_stack,
                    self._env,
                    self._words,
                    self._lexicon_registry.attribute,
                )
            except exceptions.AttributeFailedError as e:
                logger.exception(f"Encountered exception executing attribute: {e}.")
            except Exception as e:
                logger.exception(f"Encountered unrecoverable exception: {e}")
                raise
