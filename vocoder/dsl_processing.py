from inspect import signature

from lark import Discard, Transformer, Tree, v_args
from lark.exceptions import VisitError

from vocoder import exceptions
from vocoder.attribute_registry import AttributeRegistry
from vocoder.dsl import parse
from vocoder.lexicon_registry import LexiconRegistry


def process_dsl(
    config: str,
    lexicon_registry: LexiconRegistry,
    attribute_registry: AttributeRegistry,
):
    tree = parse(config)
    try:
        tree = Desugar().transform(tree)
        tree = ProcessLexiconsAndAssignments(lexicon_registry).transform(tree)
        tree = ProcessAttributeAssignments(attribute_registry).transform(tree)
        tree = ProcessAttributes(attribute_registry).transform(tree)
        tree = GatherCaptureKeys().transform(tree)
        tree = DesugarOmittedCaptures(attribute_registry).transform(tree)

    except VisitError as e:
        raise e.orig_exc

    if not any(t.children[0] == "start" for t in tree.children):
        raise exceptions.ConfigError("No 'start' nonterminal")

    return tree


class Desugar(Transformer):
    "Cast constants, desugar =>"

    def __init__(self, visit_tokens: bool = True):
        super().__init__(visit_tokens=visit_tokens)

    @v_args(tree=True)
    def attributed_nonterminal_assignment(self, tree):
        nonterminal, expression, attribute = tree.children
        expression = Tree("attributed_expression", [expression, attribute])
        tree.children = [nonterminal, expression]
        tree.data = "nonterminal_assignment"
        return tree

    @v_args(tree=True)
    def within_utterance_nonterminal_assignment(self, tree):
        nonterminal, expression = tree.children
        expression = Tree("within_utterance_expression", [expression])
        tree.children = [nonterminal, expression]
        tree.data = "nonterminal_assignment"
        return tree

    @v_args(tree=True)
    def within_utterance_attributed_nonterminal_assignment(self, tree):
        nonterminal, expression, attribute = tree.children
        attributed_expression = Tree("attributed_expression", [expression, attribute])
        expression = Tree("within_utterance_expression", [attributed_expression])
        tree.children = [nonterminal, expression]
        tree.data = "nonterminal_assignment"
        return tree


@v_args(inline=True)
class ProcessLexiconsAndAssignments(Transformer):
    def __init__(
        self, lexicon_registry: LexiconRegistry, visit_tokens: bool = True
    ) -> None:
        super().__init__(visit_tokens=visit_tokens)
        self.lexicon_registry = lexicon_registry

    INT = int
    WORD = str
    IDENTIFIER = str

    def singleton_lexicon(self, word: str):
        name = self.lexicon_registry.new_from_words([word])
        return name

    def named_lexicon(self, name: str):
        self.lexicon_registry.reference(name)
        return name

    @v_args(inline=False)
    def lexicon_expression(self, args):
        args[0] = ("+", args[0])
        return self.lexicon_registry.new_compound(args)

    def lexicon_addition(self, lexicon_name):
        return ("+", lexicon_name)

    def lexicon_subtraction(self, lexicon_name):
        return ("-", lexicon_name)

    def lexicon_assignment(self, identifier: str, ref: str):
        self.lexicon_registry.assign(identifier, ref)
        raise Discard

    def lex_ref(self, name: str):
        return Tree("lexicon", children=[name])


@v_args(inline=True)
class ProcessAttributeAssignments(Transformer):
    def __init__(self, attribute_registry: AttributeRegistry):
        super().__init__(False)
        self.attribute_registry = attribute_registry

    def attribute_assignment(self, variable: str, ref: str):
        self.attribute_registry.alias(variable, ref)
        raise Discard


@v_args(inline=True)
class ProcessAttributes(Transformer):
    def __init__(self, attribute_registry: AttributeRegistry):
        super().__init__(False)
        self.attribute_registry = attribute_registry

    def attribute(self, alias: str):
        assert isinstance(alias, str)
        return self.attribute_registry.get(alias)


@v_args(tree=True)
class GatherCaptureKeys(Transformer):
    def attributed_expression(self, tree: Tree):
        tree.children.append(get_capture_keys(tree))
        return tree

    def closure(self, tree: Tree):
        tree.children.append(get_capture_keys(tree))
        return tree

    def positive_closure(self, tree: Tree):
        tree.children.append(get_capture_keys(tree))
        return tree


def get_capture_keys(tree: Tree, keys: set[str] | None = None) -> set[int | str]:
    keys = keys if keys is not None else set[str]()
    for child in tree.children:
        if not isinstance(child, Tree):
            continue
        if child.data == "named_capture":
            _, identifier = child.children
            keys.add(identifier)
            get_capture_keys(child, keys)
        elif child.data == "positional_capture":
            _, position = child.children
            keys.add(int(position))
            get_capture_keys(child, keys)
        elif child.data in {
            "attributed_expression",
            "closure",
            "positive_closure",
        }:
            continue
        else:
            get_capture_keys(child, keys)
    return keys


@v_args(tree=True)
class DesugarOmittedCaptures(Transformer):
    def __init__(self, attribute_registry: AttributeRegistry):
        super().__init__()
        self.attribute_registry = attribute_registry

    def attributed_expression(self, tree: Tree):
        expression, attribute, capture_keys = tree.children
        n_attribute_args = sum(p != "env" for p in signature(attribute).parameters)
        if len(capture_keys) == 0 and n_attribute_args == 1:
            tree.children[0] = Tree("positional_capture", [expression, 1])
            capture_keys.add(1)
        return tree
