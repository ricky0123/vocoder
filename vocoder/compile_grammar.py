from vocoder.attribute_registry import AttributeRegistry
from vocoder.dsl_processing import process_dsl
from vocoder.dsl_to_ast import compile_ast, dsl_to_ast
from vocoder.lexicon_registry import LexiconRegistry


def compile_grammar(
    config: str,
    lexicon_registry: LexiconRegistry,
    attribute_registry: AttributeRegistry,
):
    tree = process_dsl(config, lexicon_registry, attribute_registry)
    ast = dsl_to_ast(tree)
    aut = compile_ast(ast)
    lexicon_registry.compile(
        t.predicate
        for t in aut.symbol_transitions.values()
        if isinstance(t.predicate, str)
    )
    return aut
