import itertools
from pathlib import Path

_single_word_subtractions = ["o", "t", "f", "r"]

_subtractions = set(_single_word_subtractions)


def en_frequent(n: int | None = None) -> list[str]:
    with (Path(__file__).parent / "en_frequent.txt").open() as f:
        return [
            word.strip().lower()
            for word in itertools.islice(f, n)
            if word not in _subtractions
        ]
