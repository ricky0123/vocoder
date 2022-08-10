import typing as t
from functools import partial

import pytest

from vocoder import exceptions
from vocoder.grammar import Grammar


class CompileErrorProgram(t.NamedTuple):
    build: t.Callable
    context: t.Any


_compile_error_programs = dict[str, t.Callable[[], CompileErrorProgram]]()


def _register_compile_error_program(f):
    if f.__name__ in _compile_error_programs:
        raise ValueError(f"Already defined compile error program {f.__name__}")
    _compile_error_programs[f.__name__] = f
    return f


@_register_compile_error_program
def circular_lexicon_defs() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        :a = :b
        :b = :a
        !start = :a
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.CircularLexiconDefinitionError)
    )


@_register_compile_error_program
def undefined_lexicon() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = :a
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.UndefinedLexiconError)
    )


@_register_compile_error_program
def invalid_lexicon_literal() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = :{g(1)}
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.InvalidGrammarArgument)
    )


@_register_compile_error_program
def invalid_syntax() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        x 1 * = blue
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.SyntaxError))


@_register_compile_error_program
def undefined_attribute() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = _ => %x
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.UndefinedAttributeError)
    )


@_register_compile_error_program
def circular_nonterminal() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = !A
        !A = !B
        !B = !A
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.CircularNonterminalError)
    )


@_register_compile_error_program
def undefined_nonterminal() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = !A
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.UndefinedNonterminalError)
    )


@_register_compile_error_program
def empty_string_lexicon() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = :{g([""])}
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.InvalidLexiconError)
    )


@_register_compile_error_program
def invalid_lexicon() -> CompileErrorProgram:
    def build():
        g = Grammar()
        config = f"""
        !start = :{g(["abc", "1"])}
        """
        g(config)
        return g.compile()

    return CompileErrorProgram(
        build, partial(pytest.raises, exceptions.InvalidLexiconError)
    )


@_register_compile_error_program
def closure_of_null() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!start = <* _ > hello")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def positive_closure_of_null() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!start = < _ > hello")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def unmatched_named_captures() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!start = hello@x world => %{g(lambda z: print(z))}")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def capture_with_no_attribute() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!start = hello@x world")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def wrong_positional_capture_count() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!start = hello@1 world@2 => %{g(lambda x: print(x))}")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def missing_position_arg() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!start = hello@1 world@3 => %{g(lambda z: print(z))}")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def no_start_nonterminal() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g(f"!not_start = hello world")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.ConfigError))


@_register_compile_error_program
def empty_grammar() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g("")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.SyntaxError))


@_register_compile_error_program
def uppercase() -> CompileErrorProgram:
    def build():
        g = Grammar()
        g("!start = CAN'T HAVE UPPERCASE")
        return g.compile()

    return CompileErrorProgram(build, partial(pytest.raises, exceptions.SyntaxError))


@pytest.fixture(params=list(_compile_error_programs))
def compile_error_program(request) -> CompileErrorProgram:
    return _compile_error_programs[request.param]()
