import typing as t
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from itertools import chain, repeat


class SpecialPredicate(Enum):
    BATCH_SEPARATOR = 1


class SkipTransition(t.NamedTuple):
    source: int
    target: int
    output: t.Any


class ChoiceTransition(t.NamedTuple):
    source: int
    target: int
    cost: int
    output: t.Any

    def __lt__(self, other):
        assert isinstance(other, ChoiceTransition)
        return self.cost < other.cost


Predicate = str | SpecialPredicate


class SymbolTransition(t.NamedTuple):
    source: int
    target: int
    predicate: Predicate
    output: t.Any


Transition = SymbolTransition | ChoiceTransition | SkipTransition


class StateType(Enum):
    SYMBOL = 1
    SKIP = 2
    CHOICE = 3
    FINAL = 4


@dataclass
class Soft:
    initial: int = 0
    choice_transitions: defaultdict[int, list[ChoiceTransition]] = field(
        default_factory=lambda: defaultdict(list)
    )
    skip_transitions: dict[int, SkipTransition] = field(default_factory=dict)
    symbol_transitions: dict[int, SymbolTransition] = field(default_factory=dict)

    def is_symbol_state(self, state: int) -> bool:
        return state in self.symbol_transitions

    def is_skip_state(self, state: int) -> bool:
        return state in self.skip_transitions

    def is_choice_state(self, state: int) -> bool:
        return state in self.choice_transitions

    def is_final_state(self, state: int) -> bool:
        return all(
            state not in states
            for states in [
                self.symbol_transitions,
                self.skip_transitions,
                self.choice_transitions,
            ]
        )

    def state_type(self, state: int):
        if self.is_choice_state(state):
            return StateType.CHOICE
        if self.is_skip_state(state):
            return StateType.SKIP
        if self.is_symbol_state(state):
            return StateType.SYMBOL
        if self.is_final_state(state):
            return StateType.FINAL
        raise RuntimeError

    @property
    def nonce(self) -> int:
        if not hasattr(self, "_nonce"):
            self._nonce = 1 + max(
                0,
                self.initial,
                *self.choice_transitions.keys(),
                *self.skip_transitions.keys(),
                *self.symbol_transitions.keys()
            )
        return self._nonce

    @nonce.setter
    def nonce(self, i: int):
        self._nonce = i

    def new_state(self) -> int:
        self.nonce += 1
        return self.nonce - 1


def add_skip_transition(
    soft: "Soft", state: int, output=None, next_state: int | None = None
):
    next_state = soft.new_state() if next_state is None else next_state
    soft.skip_transitions[state] = SkipTransition(state, next_state, output)
    return next_state


def add_symbol_transition(
    soft: "Soft",
    state: int,
    predicate: Predicate,
    output=None,
    next_state: int | None = None,
):
    next_state = soft.new_state() if next_state is None else next_state
    soft.symbol_transitions[state] = SymbolTransition(
        state, next_state, predicate, output
    )
    return next_state


def add_batch_separator_reflection(soft: Soft, state: int) -> int:
    state = add_skip_transition(soft, state)
    s1, s2 = add_choice_transitions(soft, state, n_choices=2)
    add_symbol_transition(soft, s1, SpecialPredicate.BATCH_SEPARATOR, next_state=state)
    out = add_skip_transition(soft, s2)
    return out


def add_choice_transitions(
    soft: "Soft",
    state: int,
    outputs=(),
    next_states: tuple[int | None, ...] = (),
    n_choices: int = 0,
):
    n_choices = max(len(outputs), len(next_states), n_choices)

    outputs = chain(outputs, repeat(None))
    next_states_extended = chain(next_states, repeat(None))
    out = list[int]()
    for i, output, next_state in zip(range(n_choices), outputs, next_states_extended):
        next_state = soft.new_state() if next_state is None else next_state
        out.append(next_state)
        transition = ChoiceTransition(state, next_state, i, output)
        soft.choice_transitions[state].append(transition)

    return tuple(out)
