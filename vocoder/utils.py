import asyncio as aio
import sys
import typing as t
from collections.abc import Iterable

from loguru import logger

T = t.TypeVar("T")


def panic(msg):
    logger.error(msg)
    sys.exit(1)


def get_top_n_indices(items: Iterable, n_top: int) -> set[int]:
    sorted_indices = sorted(enumerate(items), key=lambda item: item[1], reverse=True)
    return set(index for index, _ in sorted_indices[:n_top])


def queue_to_list(q: aio.Queue[T]) -> list[T]:
    out = []
    while True:
        try:
            out.append(q.get_nowait())
        except aio.QueueEmpty:
            break
    return out


def vocoder_welcome_message():
    logger.opt(colors=True).info("<red>Welcome to vocoder.</red>")


def vocoder_listening_message():
    logger.opt(colors=True).info("<red>Vocoder is loaded and ready for input.</red>")


def transitive_closure(relation: dict[str, set[str]]) -> dict[str, set[str]]:
    last_size = -1
    size = sum(len(children) for children in relation.values())

    while size != last_size:
        for node, children in relation.items():
            for child in children.copy():
                relation[node] |= relation[child]
        last_size = size
        size = sum(len(children) for children in relation.values())

    return relation
