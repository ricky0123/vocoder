import typing as t
from dataclasses import dataclass, field

from vocoder import exceptions
from vocoder.id_generator import IDGenerator


@dataclass
class AttributeRegistry:
    _attributes: dict[str, t.Callable] = field(default_factory=dict)
    _aliases: dict[str, str] = field(default_factory=dict)
    _id_generator: IDGenerator = field(default_factory=IDGenerator, init=False)
    _resolved: bool = False

    def alias(self, alias: str, ref: str):
        self._aliases[alias] = ref

    def _resolve(self, alias: str, visited: set[str] | None = None) -> t.Callable:
        visited = set() if visited is None else visited
        if alias in visited:
            raise exceptions.CircularAttributeDefinitionError
        visited.add(alias)
        if alias in self._attributes:
            return self._attributes[alias]
        elif alias in self._aliases:
            return self._resolve(self._aliases[alias])
        else:
            raise exceptions.UndefinedAttributeError

    def resolve(self):
        for alias in self._aliases:
            self._attributes[alias] = self._resolve(alias)
        self._resolved = True

    def get(self, name: str) -> t.Callable:
        if not self._resolved:
            self.resolve()
        try:
            return self._attributes[name]
        except KeyError:
            raise exceptions.UndefinedAttributeError(
                f"Attribute %{name} not recognized"
            )

    def new(self, attribute: t.Callable, alias: str | None = None) -> int:
        if alias is None:
            id = self._id_generator.new()
            self._attributes[id] = attribute
            return id
        else:
            assert alias not in self._attributes
            self._attributes[alias] = attribute
            return alias
