import typing as t
from collections import deque
from collections.abc import Callable
from functools import wraps
from inspect import signature

from vocoder.namespace import Namespace

Captures = dict[int | str, t.Any]
LexiconAttributor = (Callable[[str, str], t.Any],)  # (lexicon name, word) -> attribute


class ClosureValue(list):
    def __init__(self):
        super().__init__()
        self.captures = list[Captures]()

    def iter_captures(self) -> t.Iterator[t.Any]:
        for c in self.captures:
            pos = []
            i = 1
            while i in c:
                pos.append(c[i])
                i += 1

            named = Namespace(**{k: v for k, v in c.items() if not isinstance(k, int)})
            yield named, *pos


class Action(t.Protocol):
    def __call__(
        self,
        value_stack: list,
        namespace_stack: list[Captures],
        env: t.Any,
        words: deque[str],
        lexicon_attributor: LexiconAttributor,
    ) -> None:
        ...


def action(func: Callable) -> Action:
    sig = signature(func)
    assert set(sig.parameters) <= {
        "value_stack",
        "namespace_stack",
        "env",
        "words",
        "lexicon_attributor",
    }

    @wraps(func)
    def wrapped(
        value_stack: list,
        namespace_stack: list[Captures],
        env: t.Any,
        words: deque[str],
        lexicon_attributor: LexiconAttributor,
    ) -> None:
        all_args = {
            "value_stack": value_stack,
            "namespace_stack": namespace_stack,
            "env": env,
            "words": words,
            "lexicon_attributor": lexicon_attributor,
        }
        return func(
            **{
                name: value
                for name, value in all_args.items()
                if name in sig.parameters
            }
        )

    return wrapped


@action
def snoc_closure_namespace(value_stack: list, namespace_stack: list[Captures]):
    closure = value_stack[-1]
    namespace = namespace_stack.pop()
    closure.captures.append(namespace)


def sequence(*actions: Action):
    def _action(
        value_stack: list,
        namespace_stack: list[Captures],
        env: t.Any,
        words: deque[str],
        lexicon_attributor: LexiconAttributor,
    ):
        for action in actions:
            action(value_stack, namespace_stack, env, words, lexicon_attributor)

    return _action


def push_immutable(value, _repr=None):
    @action
    def _action(value_stack: list):
        value_stack.append(value)

    return _action


def push_mutable(constructor: Callable, _repr=None):
    @action
    def _action(value_stack: list):
        value_stack.append(constructor())

    return _action


@action
def snoc(value_stack: list):
    value = value_stack.pop()
    value_stack[-1].append(value)


def push_namespace(identifiers: set[int | str]) -> Action:
    @action
    def _push_namespace(namespace_stack: list[Captures]):
        namespace_stack.append({i: None for i in identifiers})

    return _push_namespace
