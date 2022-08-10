# Table of Contents
1. [Overview](#overview)
    1. [Quick start](#quick-start)
    1. [Instructions on how to run examples](#instructions-on-how-to-run-examples)
1. [DSL](#dsl)
    1. [Nonterminals](#nonterminals)
    1. [Lexicons](#lexicons)
    1. [Attributes](#attributes)
    1. [Syntax of common regular expression operations](#syntax-of-common-regex-operations)
    1. [Within utterance expressions](#within-utterance-expressions)
    1. [Attribute arguments and captures](#attribute-arguments-and-captures)
    1. [The `env` argument](#the-env-argument)
    1. [Attributed lexicons](#attributed-lexicons)
    1. [Null symbol](#the-null-symbol)
    1. [Captures within closures](#captures-within-closures)
1. [Examples](#examples)
    1. [Sleep mode](#sleep)
    1. [Spoken numbers](#numbers)
    1. [Key chords](#key-chords)
1. [Grammar inspiration and resources](#grammar-inspiration-and-resources)
1. [Credits](#credits)


# Overview

Vocoder is a software package for dictation and voice control, in a similar category of software as [Dragon](https://www.nuance.com/dragon.html), [Dragonfly](https://github.com/dictation-toolbox/dragonfly), [Caster](https://github.com/dictation-toolbox/Caster), [Talon](https://talonvoice.com/), and [Serenade](https://serenade.ai/). The user is meant to install it using pip, poetry, or something similar, and write a python script defining a grammar that maps patterns of speech to python functions that will be run when the pattern of speech is detected.

At the core of vocoder is a domain-specific language (DSL) for concisely and flexibly defining the speech command grammar - i.e. the recognizable patterns of speech and the way in which they should trigger the execution of python functions. The grammar can be thought of as a giant regular expression where certain subexpressions are associated with python functions that run as soon as the subexpressions are matched. Vocoder takes advantage of [f-strings](https://docs.python.org/3/tutorial/inputoutput.html#formatted-string-literals) to intersperse python functions with subexpressions of the grammar. Using the DSL to define the grammar and python to define actions that should be taken - like keystroke execution - the user can create scripts that enable them to dictate prose or control desktop applications by voice. For more info about the grammar DSL, see [here](#dsl). The grammar also improves speech recognition accuracy by constraining the set of words that can be recognized.

### Quick start

To get started, install vocoder using `pip install vocoder-dictation` or clone the source code and install the dependencies with [poetry](https://python-poetry.org/). Then run the following in a python interpreter or as a script:

```python
from vocoder.app import App
from vocoder.grammar import Grammar

def _action(t):
    print(f"You said '{' '.join(t)}'!")

g = Grammar()
g(f"""
!start = hello world => %{g(_action)}
""")

App(g).run()
```

When run, vocoder will start listening to input from the microphone. If the words "hello world" are detected, vocoder will print `You said 'hello world'!`. You can hit `ctrl-c` to exit.

Note that after you say "hello world" once vocoder will not recognize any more speech. In vocoder, the grammar is traversed one time instead of resetting for each utterance.

The `run` method in the last line can be given the argument `text=True` in order to start a text prompt where you can enter "hello world" instead of speaking into the microphone. This can be useful to experiment with grammars.

Vocoder may have problems understanding speech with poor or even average quality microphones. For best results, you will need a decent microphone. Vocoder currently uses the [wav2vec2](https://huggingface.co/facebook/wav2vec2-base-960h) acoustic model published by Facebook on Hugging Face.

### Instructions on how to run examples

All of the following examples can be run by first running

```python
from vocoder.app import App
from vocoder.grammar import Grammar

g = Grammar()
```

then running the code given, and finally running

```python
App(g).run()
```

or

```python
App(g).run(text=True)
```

# DSL

### Nonterminals

The DSL represents the speech grammar using assignment statements like

```
!start = !number is a number
!number = one | two | three
```

In this example, `!start` and `!number` can be thought of as variables with values defined by the regular expressions on the right-hand side of the equals signs. The DSL uses special characters prefixed to words to denote their type. Regular expression variables or "nonterminals" are prefixed by `!`. Every configuration must define the nonterminal `!start`, which is the entrypoint to the grammar. Nonterminals can't be recursively defined.

### Lexicons

For regular expressions in contexts like IDEs and most other programs, the basic matching unit of a regular expression is a single character or class of characters like `[a-z]`. In vocoder, the basic unit is better thought of as a word like "one" or "two" in the example above. You can also use a set of words as a basic matching unit:

```python
numbers = ["one", "two", "three"]
g(f"""
!start = :number is a number
:number = :{g(numbers)}  // lexicon assignment statement
""")
```

Sets of words are denoted by identifiers prefixed with `:` and called "lexicons." They can also be inlined like

```python
g(f'!start = :{g(["one", "two", "three"])} is a number')
```

Lexicons can also be provided as python dictionaries. For details, see [below](#attributed-lexicons).

You can also create lexicons by forming the union of or performing subtraction on existing lexicons and words.

```python
g(f'''
:first_three = :{g(["one", "two", "three"])}
:rest = four + five + six + seven + eight + nine
:some_numbers = :first_three + :rest - three - four
!start = :some_numbers is a number
''')
```

### Attributes

The DSL uses the `%` prefix to represent functions called "attributes" that should run when regular expressions are matched.

```python
_print = lambda x: print(x)
g(f"""
!start = print this -> %_print | print that -> %_print | don't print anything
%_print = %{g(_print)}  // attribute assignment statement
""")
```

Attributes can also be inlined as shown in the example in the [quick start](#quick-start).

The DSL consists of three types of statements: nonterminal assignments, lexicon assignments, and attribute assignments. The above examples have shown each type of statement.

### Syntax of common regex operations

The DSL ignores extra whitespace and uses C style comments. The syntax the vocoder uses to represent standard regular expression operations is unique:

| Operation                      | Vocoder          |
| ------------------------------ | ---------------- |
| Match "hello" and then "world" | `hello world`    |
| Match "hello" 0 or 1 times     | `[ hello ]`      |
| Match "hello" 0 or more times  | `<* hello >`     |
| Match "hello" 1 or more times  | `< hello >`      |
| Match "hello" or "world"       | `hello \| world` |

### Within utterance expressions

People usually speak in segments divided by silence. The pause between segments, or utterances, carries some information. For instance, it sometimes indicates that a thought has been completed. Speech recogntion systems naturally reflect the segmented nature of speech. One component of the system, the voice activity detector, segments audio into utterances and another component attempts to determine what words were spoken in each utterance.

In vocoder, we can specify that some regular expression must be matched entirely within a single utterance using the operator `~`:

```python
g(f"""
!start = < ~< hello > -> %{g(lambda words: print(" ".join(words)))} > end
""")
```

Without the `~` in this program, the attribute will not run until you say "end." With the `~`, every time you pause in your speech, vocoder will print all of the "hello"s you just said.

You can use the syntactic sugar <code>!A ~= _regex_</code> for <code>!A = ~(_regex_)</code>, which helps reduce the amount of parentheses in your regular expressions.

### Attribute arguments and captures

As explained [above](#attributes), attributes are python functions. Consider again the example from the [quick start](#quick-start):

```python
def _action(t):
    print(f"You said '{' '.join(t)}'!")

g(f"""
!start = hello world => %{g(_action)}
""")
```

First, note that the single line in the config is actually syntactic sugar for the following:

```python
g(f"""
!start = (hello world)@1 -> %{g(_action)}
""")
```

The "capture" `@1` means that the "value" (defined below) of the regular expression `(hello world)` will be passed to the first argument of the attribute `_action`. The form `!nonterminal = regex => %attribute` always resolves to `!nonterminal = (regex) -> %attribute`. The capture `@1` was added because vocoder detected that the attribute `_action` had one argument and there was no corresponding capture in the regular expression `hello world`.

Here is an example with multiple captures:

```python
g(f"""
!start = hello@1 world@2 => %{g(lambda x, y: print(f"Reversed: {y} {x}"))}
""")
```

Captures of the form `@i` where `i` is an integer indicating the position of an argument in an attribute are called "positional captures." There are also "named captures" that map onto attribute arguments by name. For instance:

```python
g(f"""
!start = (one | two)@num is a number => %{g(lambda num: print(f"{num} is a number"))}
""")
```

The "values" of regular expressions passed to attributes are defined as follows

| Regex | Value | Note |
|-|-|-|
| `word` | `word` | The value of a word or (non-attributed) lexicon is the word that was spoken (as a str) |
| `A ... Z` | `[ Value(A), ..., Value(Z) ]` | I.e. python list of component values |
| `[ A ]`   | `None` if `A` was not matched, otherwise `Value(A)` | |
| `A \| B` | `Value(A)` if `A` was matched, otherwise `Value(B)` | |
| `< A >` | `[ Value(A), ..., Value(A) ]` | I.e. list of values of all matches of child expression |

### The `env` argument

If an attribute has an argument named `env`, that argument will be passed a special `env` object. When the program first starts running, the `env` object will have a single attribute `app` that refers to the running vocoder application. The `app` object has an `exit` method that can be used to exit vocoder. For instance

```python
g(f"""
!start = exit => %{g(lambda env: env.app.exit())}
""")
```

Vocoder will simply exit as soon as you say "exit." You can also assign values to attributes of `env` and use it to store whatever objects you like.

### Attributed lexicons

Normally, the value of a lexicon is the word that was spoken. For instance, in the following example

```python
g(f'!start = :{g(["one", "two", "three"])}@x => %{g(lambda x: print(x))}')
```

vocoder will print whatever word you say from the lexicon.

You can create a lexicon with special values by providing a dictionary with string keys instead of a list of strings:

```python
g(f'!start = :{g({"one": 1, "two": 2, "three": 3})}@x => %{g(lambda x: print(x))}')
```

If you say "one", then vocoder will print the digit 1.

### The null symbol

The symbol `_` matches the empty string. For instance

```python
g(f"!start = _ -> %{g(lambda: print('hello world'))} one two three")
```

will print "hello world" when you run it (before you say "one").

### Captures within closures

If a capture (i.e. an expression of the form `R@i`) is within a "closure" like `< S >` or `<* T >` then the capture doesn't correspond to an argument of an attribute. Instead, the value of the closure will have a special way of referring to the capture. The value of the closure is an object that inherits from python's `list` and has an extra method `iter_captures` that allows you to iterate over all matched instances of the captures. Details in the [number example](#numbers).

# Examples

The following subsections show how to implement some common dictation patterns in vocoder.

## Sleep

We can use regular expressions to create a grammar with a sleep mode.

```python
from vocoder.lexicons import load_en_us

g(f"""
!start = <   ~(vocoder sleep) <* :en_us - vocoder > ~(vocoder wake)
           | ~< :en_us - vocoder > -> %{g(lambda words: print(" ".join(words)))}
         >
:en_us = :{g(load_en_us())}
""")
```

If you say "vocoder sleep," vocoder will enter a mode in which it ignores all audio input except the phrase "vocoder wake." When you are in wake mode, any phrase you speak will be written to stdout.

## Numbers

The following grammar will recognize spoken numbers like "ten thousand eight hundred and fifty five" and print them as integers.

```python
from vocoder.lexicons import digit, tens, teen, scale

def construct_number(closure):
    out = 0
    for var, *_ in closure.iter_captures():
        scale = 1
        for s in var.scales:
            scale *= s
        out += var.head * scale
    return out

g(f"""
!start = < !number -> %{g(lambda i: print(i))} >

!number ~= <!nums_0_99@head <*:scale>@scales [and]> => %{g(construct_number)}
!nums_0_99 = :digit | :teen | !nums_20_99
!nums_20_99 = :tens@x [:digit]@y => %{g(lambda x,y: x+(y or 0))}

:digit = :{g(digit)}
:scale = :{g(scale)}
:tens = :{g(tens)}
:teen = :{g(teen)}
""")
```

## Key chords

You need to install pynput in order to use the following grammar. It allows you to execute key strokes (for the letters "a," "b", and "c") and key chords (like "ctrl-a" or "ctrl-shift-p"). For instance, try saying "alfa", "bravo", "control alfa", etc.

```python
from pynput.keyboard import Controller, Key

keyboard = Controller()

def execute_chord(mods, term):
    with keyboard.pressed(*mods):
        keyboard.press(term)
        keyboard.release(term)


g(f"""
!start = < !chord >
!chord ~= <*:modifier> @mods :terminal @term => %{g(execute_chord)}

:modifier = :{g({
    "super": Key.cmd,
    "control": Key.ctrl,
    "shift": Key.shift,
    "meta": Key.alt,
})}
:terminal = :{g({
    "alfa": "a",
    "bravo": "b",
    "charlie": "c",
})}
""")
```

# Grammar inspiration and resources

- [Travis Rudd on coding by voice](https://www.youtube.com/watch?v=8SkdfdXWYaI)
- [Emily Shea on Voice Driven Development](https://whalequench.club/blog/2019/09/14/strange-loop.html)
- [cursorless](https://github.com/cursorless-dev/cursorless)
- [shorttalk](http://shorttalk-emacs.sourceforge.net/)

# Credits

The way that vocoder represents and works with grammars was inspired by the work leading to [kleenexlang](https://kleenexlang.org/). The presentation in [Søholm and Tørholm](https://brohr.coq.dk/data/thesis-final.pdf) was especially useful.

Thanks also to the creator of Talon for compiling the [list of words](https://github.com/talonvoice/lexicon) included in vocoder as the [en_us](../vocoder/lexicons/en_US.txt) lexicon.
