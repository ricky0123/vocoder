from pathlib import Path

from lark import Lark, LarkError, Tree

from vocoder import exceptions

grammar_path = Path(__file__).parent / "dsl_grammar.lark"

_parser = Lark.open(str(grammar_path), propagate_positions=True)


def parse(config: str) -> Tree:
    try:
        return _parser.parse(config)
    except LarkError:
        raise exceptions.SyntaxError
