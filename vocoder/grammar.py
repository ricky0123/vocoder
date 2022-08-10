from collections.abc import Callable
from dataclasses import dataclass, field

from vocoder import exceptions
from vocoder.attribute_registry import AttributeRegistry
from vocoder.compile_grammar import compile_grammar
from vocoder.lexicon_registry import LexiconRegistry
from vocoder.soft import Soft


@dataclass
class Grammar:
    _config: list[str] = field(default_factory=list, init=False)

    lexicon_registry: LexiconRegistry = field(
        default_factory=LexiconRegistry, init=False
    )
    attribute_registry: AttributeRegistry = field(
        default_factory=AttributeRegistry, init=False
    )

    def __call__(self, obj):
        match obj:
            case str():
                self._config.append(obj)
            case list() | dict():
                return self.lexicon_registry.new_from_words(obj)
            case Callable():
                return self.attribute_registry.new(obj)
            case _:
                raise exceptions.InvalidGrammarArgument(
                    f"Don't know what to do with object of type {type(obj)}"
                )

    @property
    def config(self):
        return "\n".join(self._config)

    def compile(self) -> Soft:
        return compile_grammar(
            self.config, self.lexicon_registry, self.attribute_registry
        )
