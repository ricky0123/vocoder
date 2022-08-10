import random
import string
from dataclasses import dataclass, field


@dataclass
class IDGenerator:
    prefix: str = ""
    _ids: set[str] = field(default_factory=set, init=False)

    def new(self) -> str:
        while True:
            id = self.prefix + "".join(
                random.choice(string.ascii_lowercase) for _ in range(8)
            )
            if id not in self._ids:
                self._ids.add(id)
                return id
