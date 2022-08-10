from collections.abc import Iterable
from dataclasses import dataclass

import numpy as np

_tokens = " abcdefghijklmnopqrstuvwxyz'."


@dataclass
class TokenEncoding:
    "A 'token' is a column index in the ctc output matrix"
    token_to_str: dict[int, str]
    str_to_token: dict[str, int]
    space: int
    blank: int
    ignore_tokens: set[int]

    def encode(self, s: str) -> tuple[int, ...]:
        return tuple(self.str_to_token[c] for c in s)

    def decode(self, tokens: Iterable[int]) -> str:
        return "".join(self.token_to_str[i] for i in tokens)

    def greedy_decode_tokens(self, ctc: np.ndarray) -> str:
        tokens = ctc.argmax(1)
        raw_str = self.decode(tokens)
        return squash_str(raw_str)

    @property
    def n_tokens(self):
        return len(self.token_to_str)

    @classmethod
    def from_str_to_token(cls, str_to_token: dict[str, int]):
        return cls(
            {i: c for c, i in str_to_token.items()},
            str_to_token,
            str_to_token[" "],
            str_to_token["."],
            {c for c in str_to_token if c not in _tokens},
        )


def squash_str(s: str):
    deduplicated_chars = list[str]()
    last_char = ""
    for char in s:
        if char != last_char:
            deduplicated_chars.append(char)
        last_char = char
    return "".join(c for c in deduplicated_chars if c != ".")
