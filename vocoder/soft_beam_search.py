import typing as t
from collections import defaultdict
from dataclasses import dataclass
from functools import partial

import numpy as np

from vocoder.lexicon import AbstractLexicon
from vocoder.lexicon_registry import LexiconRegistry
from vocoder.math import logadd, negative_infinity
from vocoder.soft import Soft
from vocoder.soft_simulate import (
    PathLeaves,
    batch_separator_transition,
    get_predicate_transitions,
    step_tree,
    transition_from_word,
)
from vocoder.token_encoding import TokenEncoding
from vocoder.utils import get_top_n_indices

TokenWord = tuple[int, ...]


@dataclass
class HypothesisProbabilities:
    blank: float
    no_blank: float

    @property
    def total_probability(self) -> float:
        return logadd(self.no_blank, self.blank)

    @classmethod
    def initial(cls) -> "HypothesisProbabilities":
        return cls(blank=negative_infinity, no_blank=0)

    @classmethod
    def new(cls) -> "HypothesisProbabilities":
        return cls(negative_infinity, negative_infinity)

    def propose_blank(self, last: "HypothesisProbabilities", p: float):
        self.blank = logadd(self.blank, p + last.blank, p + last.no_blank)

    def propose_last_token_unchanged(self, last: "HypothesisProbabilities", p: float):
        self.no_blank = logadd(self.no_blank, p + last.no_blank)

    def propose_last_token_extended(self, last: "HypothesisProbabilities", p: float):
        self.no_blank = logadd(self.no_blank, p + last.blank)

    def propose_new_char(self, last: "HypothesisProbabilities", p: float):
        self.no_blank = logadd(self.no_blank, p + last.blank, p + last.no_blank)


class Hypothesis(t.NamedTuple):
    prefix: TokenWord
    completed: tuple[TokenWord, ...]

    def transition(self) -> "Hypothesis":
        return Hypothesis((), self.completed + (self.prefix,))

    @classmethod
    def empty(cls):
        return cls((), ())

    def extend_current_prefix(self, token: int) -> "Hypothesis":
        return self._replace(prefix=self.prefix + (token,))  # pylint: disable=no-member


def last_token(token_encoding: TokenEncoding, hyp: Hypothesis) -> int:
    if hyp.prefix:
        return hyp.prefix[-1]
    return token_encoding.space


def prefix_complete(
    token_encoding: TokenEncoding,
    lexicon_cache: dict[tuple[TokenWord, ...], AbstractLexicon],
    hyp: Hypothesis,
):
    lex = lexicon_cache[hyp.completed]
    word = token_encoding.decode(hyp.prefix)
    return word in lex


def token_proposals(
    token_encoding: TokenEncoding,
    lexicon_cache: dict[tuple[TokenWord, ...], AbstractLexicon],
    hyp: Hypothesis,
):
    lex = lexicon_cache[hyp.completed]
    word = token_encoding.decode(hyp.prefix)
    for transition in lex.transitions(word):
        yield token_encoding.str_to_token[transition]


def valid_prediction(
    token_encoding: TokenEncoding,
    lexicon_cache: dict[tuple[TokenWord, ...], AbstractLexicon],
    hyp: Hypothesis,
):
    return prefix_complete(token_encoding, lexicon_cache, hyp) or not hyp.prefix


def beam_search(
    soft: Soft,
    lexicon_registry: LexiconRegistry,
    initial_leaves: PathLeaves,
    ctc_output: np.ndarray,
    token_encoding: TokenEncoding,
    beam_width: int = 8,
    n_token_proposals: int = 8,
) -> tuple[tuple[str, ...], float, PathLeaves]:

    bad_out = (), -float("inf"), initial_leaves

    lexicon_cache = dict[tuple[TokenWord, ...], AbstractLexicon]()
    grammar_states = dict[tuple[TokenWord, ...], PathLeaves]()

    leaves = initial_leaves.copy()
    lex = lexicon_registry.get_union(*get_predicate_transitions(soft, leaves))
    hyp = Hypothesis.empty()

    lexicon_cache[()] = lex
    grammar_states[()] = leaves

    _last_token = partial(last_token, token_encoding)
    _prefix_complete = partial(prefix_complete, token_encoding, lexicon_cache)
    _token_proposals = partial(token_proposals, token_encoding, lexicon_cache)
    _valid_prediction = partial(valid_prediction, token_encoding, lexicon_cache)

    sorted_beam = [(hyp, HypothesisProbabilities.initial())]

    for i, ctc_frame in enumerate(ctc_output):
        top_tokens = get_top_n_indices(ctc_frame, n_token_proposals)
        next_beam = defaultdict[Hypothesis, HypothesisProbabilities](
            HypothesisProbabilities.new
        )

        for hyp, probs in sorted_beam:
            ## propose hyp-preserving tokens
            # propose unextended blank
            if token_encoding.blank in top_tokens:
                next_beam[hyp].propose_blank(probs, ctc_frame[token_encoding.blank])

            # propose unextended last char
            if (lt := _last_token(hyp)) in top_tokens:
                next_beam[hyp].propose_last_token_unchanged(probs, ctc_frame[lt])

            ## grammar transition
            # propose space extended hyp
            if token_encoding.space in top_tokens and _prefix_complete(hyp):
                next_hyp = hyp.transition()
                if next_hyp.completed not in grammar_states:
                    # step path tree
                    leaves = transition_from_word(
                        soft,
                        lexicon_registry,
                        grammar_states[hyp.completed],
                        token_encoding.decode(hyp.prefix),
                    )
                    leaves = step_tree(soft, leaves)
                    grammar_states[next_hyp.completed] = leaves

                    lex = lexicon_registry.get_union(
                        *get_predicate_transitions(soft, leaves)
                    )
                    lexicon_cache[next_hyp.completed] = lex
                next_beam[next_hyp].propose_new_char(
                    probs, ctc_frame[token_encoding.space]
                )

            ## extend prefix
            # propose prefix extensions
            for token in _token_proposals(hyp):
                if token in top_tokens:
                    next_hyp = hyp.extend_current_prefix(token)
                    next_probs = next_beam[next_hyp]
                    if token == _last_token(hyp):
                        next_probs.propose_last_token_extended(probs, ctc_frame[token])
                    else:
                        next_probs.propose_new_char(probs, ctc_frame[token])

        if not next_beam:
            # Bad end
            return bad_out

        sorted_beam = sorted(
            next_beam.items(),
            key=lambda item: item[1].total_probability,
            reverse=True,
        )

        if i != len(ctc_output) - 1:
            sorted_beam = sorted_beam[:beam_width]

    # return first valid hyp
    for hyp, probs in sorted_beam:

        # prefix incomplete
        if not _valid_prediction(hyp):
            continue

        # perform grammar transition if needed
        if _prefix_complete(hyp):
            next_hyp = hyp.transition()
            if next_hyp.completed not in grammar_states:
                # step path tree
                leaves = transition_from_word(
                    soft,
                    lexicon_registry,
                    grammar_states[hyp.completed],
                    token_encoding.decode(hyp.prefix),
                )
                leaves = step_tree(soft, leaves)
                grammar_states[next_hyp.completed] = leaves

                lex = lexicon_registry.get_union(
                    *get_predicate_transitions(soft, leaves)
                )
                lexicon_cache[next_hyp.completed] = lex
            hyp = next_hyp

        leaves = grammar_states[hyp.completed]
        leaves = batch_separator_transition(soft, leaves)
        leaves = step_tree(soft, leaves)

        if not leaves:
            continue

        words = tuple(token_encoding.decode(t) for t in hyp.completed)
        return words, probs.total_probability, leaves

    return bad_out
