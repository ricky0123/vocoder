import typing as t
from unittest.mock import MagicMock, call

import pytest

from vocoder.grammar import Grammar
from vocoder.lexicons import digit, scale, teen, tens


class Program(t.NamedTuple):
    grammar: Grammar
    input: list[str]
    test: t.Callable[[], None]


def no_test():
    pass


_programs = dict[str, t.Callable[[], Program]]()


def _register_program(f):
    if f.__name__ in _programs:
        raise ValueError(f"Already defined program {f.__name__}")

    _programs[f.__name__] = f
    return f


@_register_program
def attributed_lexicon() -> Program:
    mock = MagicMock()
    g = Grammar()
    g(f"!start = :{g({'x': 1})} @ arg => %{g(lambda arg: mock(arg))}")
    input = ["x"]

    def test():
        mock.assert_called_once_with(1)

    return Program(g, input, test)


@_register_program
def cat_no_input() -> Program:
    g = Grammar()
    g("!start = hello world")
    input = [""]
    return Program(g, input, no_test)


@_register_program
def cat_with_input() -> Program:
    g = Grammar()
    g("!start = hello world")
    input = ["hello world"]
    return Program(g, input, no_test)


@_register_program
def comments() -> Program:
    g = Grammar()
    g("!start = hello world // this is a comment")
    input = ["hello world"]
    return Program(g, input, no_test)


@_register_program
def cat_with_input_multiple_utterances() -> Program:
    g = Grammar()
    g("!start = hello world")
    input = ["hello", "world"]
    return Program(g, input, no_test)


@_register_program
def attribute_no_capture() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello world => %{g(lambda: mock())}")

    input = ["hello world"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def attribute_with_env_arg() -> Program:
    mock = MagicMock()

    def _assign(env):
        env.x = 1

    g = Grammar()
    g(
        f"""
    !start = (
        hello -> %{g(_assign)}
        world -> %{g(lambda env: mock(env.x))}
    )
    """
    )

    input = ["hello world"]

    def test():
        mock.assert_called_once_with(1)

    return Program(g, input, test)


@_register_program
def desugar_ommitted_but_with_env() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(
        f"""
    !start = hello => %{g(lambda env, x: mock(x))}
    """
    )

    input = ["hello"]

    def test():
        mock.assert_called_once_with("hello")

    return Program(g, input, test)


@_register_program
def cat_with_nullable() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello world _ => %{g(lambda: mock())}")

    input = ["hello world"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def attribute_no_capture_multiple_utterances() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello world => %{g(lambda: mock())}")

    input = ["hello world"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def nonterminal_assignment_within_utterance() -> Program:
    g = Grammar()
    g(f"!start ~= hello world")

    input = ["hello world"]

    return Program(g, input, no_test)


@_register_program
def attributed_nonterminal_assignment_within_utterance() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start ~= < hello world > => %{g(lambda: mock())}")

    input = ["hello world hello world"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def alias_capture_word() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello@value => %{g(lambda value: mock(value))}")

    input = ["hello"]

    def test():
        expected = [call("hello")]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def positional_capture_word() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello@1 => %{g(lambda value: mock(value))}")

    input = ["hello"]

    def test():
        expected = [call("hello")]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def implicit_capture_word() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello => %{g(lambda value: mock(value))}")

    input = ["hello"]

    def test():
        expected = [call("hello")]
        assert mock.call_args_list == expected

    return Program(g, input, test)


def capture_word_within_cat() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello@value world => %{g(lambda value: mock(value))}")

    input = ["hello world"]

    def test():
        expected = [call("hello")]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def cat_capture() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello world => %{g(lambda value: mock(value))}")

    input = ["hello world"]

    def test():
        expected = [call(["hello", "world"])]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def alt() -> Program:
    g = Grammar()
    g(f"!start = (hello | world) goodbye")

    input = ["hello goodbye"]

    return Program(g, input, no_test)


@_register_program
def alt_capture() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = (hello | world) => %{g(lambda value: mock(value))}")

    input = ["world"]

    def test():
        expected = [call("world")]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def optional() -> Program:
    g = Grammar()
    g(f"!start = [hello] world")

    input = ["world"]

    return Program(g, input, no_test)


@_register_program
def optional_capture_none() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = [hello]@1 world => %{g(lambda value: mock(value))}")

    input = ["world"]

    def test():
        expected = [call(None)]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def optional_capture_value() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = [hello]@1 world => %{g(lambda value: mock(value))}")

    input = ["hello world"]

    def test():
        expected = [call("hello")]
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def epsilon() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = _ -> %{g(lambda: mock())} hello")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def optional_nullable() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello [ _ -> %{g(lambda: mock())} ]")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def alt_nullable() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello ( _ -> %{g(lambda: mock())} | _ )")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def alt_nullable_within_utterance() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start ~= hello ( _ -> %{g(lambda: mock())} | world )")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def closure() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = < _ -> %{g(lambda: mock())} hello >")

    input = ["hello hello hello"]

    def test():
        expected = [call()] * 3
        assert mock.call_args_list == expected

    return Program(g, input, test)


@_register_program
def within_utterance_inner_attribute() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = ~( hello -> %{g(lambda: mock())} )")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def within_utterance_outer_attribute() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = ~( hello ) -> %{g(lambda: mock())}")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def double_within_utterance() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = ~~ hello  -> %{g(lambda: mock())}")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def consecutive_within_utterances() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = ~one ~two  -> %{g(lambda: mock())}")

    input = ["one", "two"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def drop_within_utterance_branch() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = ~( one two ) | one -> %{g(lambda: mock())} two")

    input = ["one"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def closure_within_utterance() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = ~< x > -> %{g(lambda: mock())}")

    input = ["x x"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def closure_not_within_utterance() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = < x > -> %{g(lambda: mock())}")

    input = ["x x"]

    def test():
        mock.assert_not_called()

    return Program(g, input, test)


@_register_program
def alt_cat_precedence_and_alt_greedy() -> Program:
    mock = MagicMock()

    g = Grammar()
    config = f"""
    !start = (one two three -> %{g(lambda: mock())} | one two three) four
    """
    g(config)

    input = ["one two three four"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def alt_greedy() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello -> %{g(lambda: mock())} | hello")

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def consecutive_optionals() -> Program:
    mocks = [MagicMock() for _ in range(4)]

    g = Grammar()
    config = f"""
    !start = (
        <*
        [one   -> %{g(lambda: mocks[0]())}]
        [two   -> %{g(lambda: mocks[1]())}]
        [three -> %{g(lambda: mocks[2]())}]
        x -> %{g(lambda: mocks[3]())}
        >
    )
    """
    g(config)

    input = ["one x one x one three x", "two three x two"]

    def test():
        assert mocks[0].call_args_list == [call()] * 3
        assert mocks[1].call_args_list == [call()] * 2
        assert mocks[2].call_args_list == [call()] * 2
        assert mocks[3].call_args_list == [call()] * 4

    return Program(g, input, test)


@_register_program
def closure_within_utterance_within_closure() -> Program:
    mock1 = MagicMock()
    mock2 = MagicMock()
    mock3 = MagicMock()

    g = Grammar()
    config = f"""
    !start = (
        <*
            ~<
               x -> %{g(lambda: mock1())}
            > -> %{g(lambda: mock2())}
        > end -> %{g(lambda: mock3())}
    )
    """
    g(config)

    input = ["x x", "x", "x x x x", "x end"]

    def test():
        assert mock1.call_args_list == [call()] * 8
        assert mock2.call_args_list == [call()] * 4
        assert mock3.call_args_list == [call()] * 1

    return Program(g, input, test)


@_register_program
def multiple_nonterminals() -> Program:
    mock = MagicMock()

    g = Grammar()
    config = f"""
    !start = !R !S !T
    !R = hello
    !S = !V
    !V = world
    !T = _ => %{g(lambda: mock())}
    """
    g(config)

    input = ["hello world"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def multiple_captures() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start = hello@x world@y => %{g(lambda x,y: mock(x,y))}")

    input = ["hello world"]

    def test():
        assert mock.call_args_list == [call("hello", "world")]

    return Program(g, input, test)


@_register_program
def closure_capture() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start ~= <* hello | world > => %{g(lambda phrase: mock(list(phrase)))}")

    input = ["hello world"]

    def test():
        assert mock.call_args_list == [call(["hello", "world"])]

    return Program(g, input, test)


@_register_program
def positive_closure_capture() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start ~= < hello | world > => %{g(lambda phrase: mock(list(phrase)))}")

    input = ["hello world"]

    def test():
        assert mock.call_args_list == [call(["hello", "world"])]

    return Program(g, input, test)


@_register_program
def capture_within_closure() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(f"!start ~= < hello@x | world > => %{g(lambda phrase: mock(phrase))}")

    input = ["hello world"]

    def test():
        mock.assert_called_once()
        (parse,), _ = mock.call_args
        assert parse == ["hello", "world"]
        assert parse.captures[0]["x"] == "hello"
        assert parse.captures[1]["x"] is None

    return Program(g, input, test)


@_register_program
def positional_capture_within_closure() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(
        f"""!start ~= < 
            (hello@x | world) [:{g({'end': 'value'})}]@1 
        > => %{g(lambda phrase: mock(phrase))}
        """
    )

    input = ["hello end world"]

    def test():
        mock.assert_called_once()
        (parse,), _ = mock.call_args
        assert parse == [["hello", "value"], ["world", None]]
        assert parse.captures[0]["x"] == "hello"
        assert parse.captures[1]["x"] is None
        assert parse.captures[0][1] == "value"
        assert parse.captures[1][1] is None

    return Program(g, input, test)


@_register_program
def closure_iter_captures() -> Program:
    mock = MagicMock()

    g = Grammar()
    g(
        f"""!start ~= < 
            (hello@x | world) [:{g({'end': 'value'})}]@1 anotherword@2
        > => %{g(lambda phrase: mock(phrase))}
        """
    )

    input = ["hello end anotherword world anotherword"]

    def test():
        mock.assert_called_once()
        (parse,), _ = mock.call_args
        assert parse == [
            ["hello", "value", "anotherword"],
            ["world", None, "anotherword"],
        ]
        for i, (vals, *pos) in enumerate(parse.iter_captures()):
            if i == 0:
                assert vals.x == "hello"
                assert pos[0] == "value"
                assert pos[1] == "anotherword"

            else:
                assert vals.x is None
                assert pos[0] is None
                assert pos[1] == "anotherword"
        assert i == 1

    return Program(g, input, test)


@_register_program
def complex_parse_1() -> Program:
    mock = MagicMock()

    g = Grammar()
    config = f"""
    !start = !a (!b !c) !a => %{g(lambda x: mock(x))}
    !a = [blue]
    !b = red|green => %{g(lambda x: x)}
    !c = _ => %{g(lambda: 10)}
    """
    g(config)

    input = ["green blue"]

    def test():
        assert mock.call_args_list == [call([None, ["green", 10], "blue"])]

    return Program(g, input, test)


@_register_program
def simple_realistic_1() -> Program:
    mock1 = MagicMock()
    mock2 = MagicMock()

    g = Grammar()
    config = f"""
    !start = < 
          key     <* !chord >
        | dictate <* !dictate >
    > 

    !chord = one two three => %{g(lambda: mock1())}

    :any = hello+world+goodbye
    !dictate = ~(< :any-dictate-key >) => %{g(lambda words: mock2(len(words)))}
    """
    g(config)

    input = ["dictate hello world", "dictate goodbye key one two three"]

    def test():
        mock1.assert_called_once()
        assert mock2.call_args_list == [call(2), call(1)]

    return Program(g, input, test)


@_register_program
def simple_realistic_2() -> Program:
    mock = MagicMock()

    g = Grammar()
    config = f"""
    !start = < 
          key     <* !chord >
        | dictate <* !dictate >
    > 

    !chord = one two three => %{g(lambda: mock())}

    :any = hello+world+goodbye
    !dictate = ~(< :any-dictate-key >) => %{g(lambda words: mock(" ".join(words)))}
    """
    g(config)

    input = ["dictate hello world"]

    def test():
        assert mock.call_args_list == [call("hello world")]

    return Program(g, input, test)


@_register_program
def simple_realistic_3() -> Program:
    mock = MagicMock()

    g = Grammar()
    config = f"""
    !start = < 
          key     <* !chord >
        | dictate <* !dictate >
    > 

    !chord = one two three => %{g(lambda: mock())}

    :any = :{g(["hello", "world", "something", "dictate", "one"])}
    !dictate = ~(< :any-dictate-key >) => %{g(lambda words: mock(" ".join(words)))}
    """
    g(config)

    input = ["dictate hello world", "key one two three"]

    def test():
        assert mock.call_args_list == [call("hello world"), call()]

    return Program(g, input, test)


@_register_program
def or_precedence() -> Program:
    g = Grammar()
    config = f"""
    !start = < a b c | one two three >
    """
    g(config)

    input = ["a b c", "one two three"]

    return Program(g, input, no_test)


@_register_program
def sleep_1() -> Program:
    mock = MagicMock()

    g = Grammar()
    config = f"""
    :any = :{g(["hello", "world", "something", "dictate", "one", "two", "three", "four", "five", "six", "a", "b", "c"])}

    !start = < 
          ~(wakeword sleep) <* :any - wakeword > ~(wakeword wake)
        | ~< :any - wakeword > -> %{g(lambda words: mock(" ".join(words)))}
    >
    """
    g(config)

    input = [
        "one two three",
        "four five six",
        "wakeword sleep",
        "a b c",
        "wakeword wake",
        "hello world",
    ]

    def test():
        assert mock.call_args_list == [
            call("one two three"),
            call("four five six"),
            call("hello world"),
        ]

    return Program(g, input, test)


@_register_program
def weird_lexicon_config() -> Program:
    mock = MagicMock()
    g = Grammar()
    config = f"""
    :a = :{g(["hello", "world"])}
    :b = :a
    :c = :b
    !start = :c => %{g(lambda: mock())}
    """
    g(config)

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def weird_attribute_config() -> Program:
    mock = MagicMock()
    g = Grammar()
    config = f"""
    %a = %{g(lambda: mock())}
    %b = %a
    %c = %b
    !start = hello => %c
    """
    g(config)

    input = ["hello"]

    def test():
        mock.assert_called_once()

    return Program(g, input, test)


@_register_program
def within_utterance_closure_bug() -> Program:
    mock = MagicMock()
    g = Grammar()
    config = f"""
    !start = < ~< hello > -> %{g(lambda words: mock(" ".join(words)))} > end
    """
    g(config)

    input = ["hello hello", "hello hello hello"]

    def test():
        assert mock.call_args_list == [call(s) for s in input]

    return Program(g, input, test)


@_register_program
def within_utterance_closure_bug_with_return() -> Program:
    mock = MagicMock()
    g = Grammar()
    config = f"""
    !start = < ~< hello > -> %{g(lambda words: mock(" ".join(words)))} > end => %{g(lambda p: None)}
    """
    g(config)

    input = ["hello hello", "hello hello hello"]

    def test():
        assert mock.call_args_list == [call(s) for s in input]

    return Program(g, input, test)


@_register_program
def within_utterance_closure_bug_closure() -> Program:
    mock = MagicMock()
    g = Grammar()
    config = f"""
    !start = <* ~< hello > -> %{g(lambda words: mock(" ".join(words)))} > end
    """
    g(config)

    input = ["hello hello", "hello hello hello"]

    def test():
        assert mock.call_args_list == [call(s) for s in input]

    return Program(g, input, test)


@_register_program
def within_utterance_closure_bug_closure_with_return() -> Program:
    mock = MagicMock()
    g = Grammar()
    config = f"""
    !start = <* ~< hello > -> %{g(lambda words: mock(" ".join(words)))} > end => %{g(lambda p: None)}
    """
    g(config)

    input = ["hello hello", "hello hello hello"]

    def test():
        assert mock.call_args_list == [call(s) for s in input]

    return Program(g, input, test)


@_register_program
def num_1() -> Program:
    mock = MagicMock()
    g = Grammar()

    def _a(val):
        ten = val.captures[0][1]
        thousand = " ".join(val.captures[0][2])
        return ten + " " + thousand

    config = f"""
    !start = < !number -> %{g(lambda val: mock(val))} >
    !number ~= < ten@1 <* thousand >@2 [and]> => %{g(_a)}
    """
    g(config)

    input = ["ten thousand"]

    def test():
        mock.assert_called_once_with("ten thousand")

    return Program(g, input, test)


@_register_program
def numbers_full() -> Program:
    mock = MagicMock()
    g = Grammar()

    def construct_number(repetitions):
        out = 0
        for _, head, scales in repetitions.iter_captures():
            scale = 1
            for s in scales:
                scale *= s
            out += head * scale
        return out

    config = f"""
    !start = < !number -> %{g(lambda i: mock(i))} >

    !number ~= <!nums_0_99@1 <*:scale>@2 [and]> => %{g(construct_number)}
    !nums_0_99 = :digit | :teen | !nums_20_99
    !nums_20_99 = :tens@x [:digit]@y => %{g(lambda x,y: x+(y or 0))}

    :digit = :{g(digit)}
    :scale = :{g(scale)}
    :tens = :{g(tens)}
    :teen = :{g(teen)}
    """

    g(config)

    input = ["ten thousand"]

    def test():
        mock.assert_called_once_with(10_000)

    return Program(g, input, test)


@_register_program
def numbers_partial() -> Program:
    mock = MagicMock()
    g = Grammar()

    config = f"""
    !start = < !number -> %{g(lambda i: mock(i))} >

    !number ~= :digit | :teen | !nums_20_99
    !nums_20_99 = :tens@x [:digit]@y => %{g(lambda x,y: x+(y or 0))}

    :digit = :{g(digit)}
    :scale = :{g(scale)}
    :tens = :{g(tens)}
    :teen = :{g(teen)}
    """

    g(config)

    input = ["thirty one"]

    def test():
        mock.assert_called_once_with(31)

    return Program(g, input, test)


@pytest.fixture(params=list(_programs))
def program(request) -> Program:
    return _programs[request.param]()
