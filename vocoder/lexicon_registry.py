import typing as t
from dataclasses import dataclass, field
from functools import partial

from vocoder import exceptions
from vocoder.id_generator import IDGenerator
from vocoder.lexicon import AbstractLexicon, Lexicon, LexiconUnion
from vocoder.utils import transitive_closure

INLINE_PREFIX = "___"


@dataclass
class LexiconRegistry:
    _lexicon_symbols: dict[str, "LexiconSymbol"] = field(
        default_factory=dict, init=False
    )
    _lexicons: dict[str, Lexicon] = field(default_factory=dict, init=False)
    _id_generator: IDGenerator = field(
        default_factory=partial(IDGenerator, INLINE_PREFIX), init=False
    )
    _vars: set[str] = field(default_factory=set, init=False)
    _references: set[str] = field(default_factory=set, init=False)

    def reference(self, name: str):
        self._references.add(name)

    def assign(self, identifier: str, ref: str) -> str:
        assert not identifier.startswith(INLINE_PREFIX)
        lexicon = LexiconReferenceSymbol(ref)
        self._vars.add(identifier)
        return self.register_lexicon(lexicon, identifier)

    def attribute(self, lexicon: str, word: str) -> t.Any:
        return self._lexicons[lexicon].attribute(word)

    def get_union(self, *names: str) -> AbstractLexicon:
        return LexiconUnion(self._lexicons[name] for name in names)

    def compile(self, predicates: t.Iterable[str]):
        for ref in self._references:
            if ref not in self._lexicon_symbols:
                raise exceptions.UndefinedLexiconError(f":{ref} not defined")

        dependence = {var: set(self._deps(var)) for var in self._vars}
        dependence = transitive_closure(dependence)

        for var, deps in dependence.items():
            if var in deps:
                raise exceptions.CircularLexiconDefinitionError(
                    f"Circular definition for :{var}"
                )

        for var in sorted(self._vars, key=lambda var: len(dependence[var])):
            words, attributes = self._words_and_attributes(var)
            self._lexicons[var] = Lexicon(words, attributes)

        for pred in predicates:
            words, attributes = self._words_and_attributes(pred)
            self._lexicons[pred] = Lexicon(words, attributes)

    def _words_and_attributes(
        self,
        name: str,
    ) -> tuple[set[str], dict[str, t.Any]]:
        sym = self._lexicon_symbols[name]
        match sym:
            case WordSetLexiconSymbol(words):
                return set(words), {}
            case AttributedWordSetLexiconSymbol(words):
                return set(words), words
            case LexiconReferenceSymbol(ref):
                if ref in self._lexicons:
                    lex = self._lexicons[ref]
                    return lex._words, lex._attributes
                return self._words_and_attributes(ref)
            case CompoundLexiconSymbol(components):
                words = set[str]()
                attributes = dict[str, t.Any]()
                for sign, ref in components:
                    _words, _attributes = self._words_and_attributes(ref)
                    if sign == "-":
                        words.difference_update(_words)
                        for w in _words:
                            attributes.pop(w, None)
                    else:
                        words.update(_words)
                        attributes.update(_attributes)
                return words, attributes
            case _:
                raise ValueError

    def new_from_words(self, words: list | dict, alias: str | None = None) -> str:
        match words:
            case list():
                lexicon = WordSetLexiconSymbol(words)
            case dict():
                lexicon = AttributedWordSetLexiconSymbol(words)
            case _:
                raise TypeError
        return self.register_lexicon(lexicon, alias)

    def new_compound(
        self, components: t.Sequence[tuple[t.Literal["-", "+"], str]]
    ) -> str:
        assert all(sign in "+-" and isinstance(name, str) for sign, name in components)
        lexicon = CompoundLexiconSymbol(components)
        return self.register_lexicon(lexicon)

    def register_lexicon(
        self, lexicon: "LexiconSymbol", alias: str | None = None
    ) -> str:
        if alias is None:
            id = self._id_generator.new()
            self._lexicon_symbols[id] = lexicon
            return id
        else:
            assert alias not in self._lexicon_symbols
            self._lexicon_symbols[alias] = lexicon
            return alias

    def _deps(self, name: str, visited: set[str] | None = None) -> t.Iterator[str]:
        visited = set[str]() if visited is None else visited
        if name in visited:
            return
        visited.add(name)
        if name not in self._lexicon_symbols:
            raise exceptions.UndefinedLexiconError
        sym = self._lexicon_symbols[name]
        match sym:
            case LexiconReferenceSymbol():
                if sym.ref in self._vars:
                    yield sym.ref
                yield from self._deps(sym.ref, visited)
            case CompoundLexiconSymbol():
                for _, child in sym.components:
                    if child in self._vars:
                        yield child
                    yield from self._deps(child, visited)


class LexiconSymbol:
    ...


@dataclass
class WordSetLexiconSymbol(LexiconSymbol):
    words: t.Sequence[str]


@dataclass
class AttributedWordSetLexiconSymbol(LexiconSymbol):
    words: dict[str, t.Any]


@dataclass
class CompoundLexiconSymbol(LexiconSymbol):
    components: list[tuple[t.Literal["-", "+"], str]]


@dataclass
class LexiconReferenceSymbol(LexiconSymbol):
    ref: str
