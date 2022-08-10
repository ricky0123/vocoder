import typing as t
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable, Iterator

from vocoder import exceptions


def get_set_dict_representation(words: Iterable[str]):

    words = set(words)
    transitions = defaultdict[str, set[str]](set)
    transitions[""] = set()

    for word in words:
        if word in transitions:
            continue
        else:
            transitions[word] = set()

        for end in range(len(word) - 1, -1, -1):
            prefix = word[:end]
            extension = word[end]
            if prefix in transitions and extension in transitions[prefix]:
                break
            transitions[prefix].add(extension)
    return words, transitions


class AbstractLexicon(ABC):
    "Can be empty but can't contain empty string"

    @abstractmethod
    def __contains__(self, word: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def transitions(self, prefix: str) -> Iterator[str]:
        raise NotImplementedError

    @abstractmethod
    def is_prefix(self, prefix: str) -> bool:
        raise NotImplementedError

    def attribute(self, word: str):
        "Override this for attributed lexicons"
        return word

    def words(self, prefix: str = "") -> Iterator[str]:
        if prefix and prefix in self:
            yield prefix
        for transition in sorted(self.transitions(prefix)):
            yield from self.words(prefix + transition)


class Lexicon(AbstractLexicon):
    def __init__(
        self, words: Iterable[str], attributes: dict[str, t.Any] | None = None
    ):
        super().__init__()
        self._words, self._transitions = get_set_dict_representation(words)
        self._attributes = attributes if attributes is not None else {}
        for word in self.words():
            if not set(word) <= set("abcdefghijklmnopqrstuvwxyz'"):
                raise exceptions.InvalidLexiconError(
                    f"Lexicon cannot accept word '{word}'"
                )
        if "" in self:
            raise exceptions.InvalidLexiconError

    def attribute(self, word: str):
        return self._attributes.get(word, word)

    def __contains__(self, word: str) -> bool:
        return word in self._words

    def transitions(self, prefix: str) -> Iterator[str]:
        yield from self._transitions[prefix]

    def is_prefix(self, prefix: str) -> bool:
        return prefix in self._transitions


class LexiconUnion(AbstractLexicon):
    def __init__(self, lexicons: Iterable[AbstractLexicon]):
        self.lexicons = list(lexicons)

    def __contains__(self, word: str) -> bool:
        return any(word in lexicon for lexicon in self.lexicons)

    def is_prefix(self, prefix: str) -> bool:
        return not prefix or any(l.is_prefix(prefix) for l in self.lexicons)

    def transitions(self, prefix: str) -> Iterator[str]:
        _transitions = set().union(
            *(l.transitions(prefix) for l in self.lexicons if l.is_prefix(prefix))
        )
        yield from _transitions


""" 
class CompoundLexicon(Lexicon):
    def __init__(self, lexicons: list[LexiconComponent]):
        super().__init__()
        self.lexicons = lexicons

    def __contains__(self, word: str) -> bool:
        for component in reversed(self.lexicons):
            if component.subtract and word in component.lexicon:
                return False
            elif word in component.lexicon:
                return True
        return False

    def transitions(self, prefix: str) -> Iterator[str]:
        out = set[str]()
        _subtracted = set[Lexicon]()
        subtracted = LexiconUnion(_subtracted)
        for component in reversed(self.lexicons):
            if component.subtract:
                _subtracted.add(component.lexicon)
                subtracted = LexiconUnion(_subtracted)
            else:
                for c in component.lexicon.transitions(prefix):
                    if c not in out:
                        if is_in_difference(component.lexicon, subtracted, prefix, c):
                            yield c
                            out.add(c)

    def is_prefix(self, prefix: str) -> bool:
        return prefix in self or any(self.transitions(prefix))


def is_in_difference(
    minuend: Lexicon, subtrahend: Lexicon, prefix: str, char: str
) -> bool:
    if not subtrahend.is_prefix(prefix) or char not in subtrahend.transitions(prefix):
        return True
    # breadth-first search
    nodes = deque([char])
    while nodes:
        extension = nodes.popleft()
        for next_char in minuend.transitions(prefix + extension):
            if next_char not in subtrahend.transitions(prefix + extension):
                return True
            nodes.append(extension + next_char)
    return False
 """
