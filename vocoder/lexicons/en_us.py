from pathlib import Path


def load_en_us() -> list[str]:
    with (Path(__file__).parent / "en_US.txt").open() as f:
        return [word.strip().lower() for word in f]
