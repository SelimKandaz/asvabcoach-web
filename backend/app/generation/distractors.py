from __future__ import annotations

from random import Random


def shuffle_unique_choices(options: list[str], *, seed: str) -> dict[str, str]:
    unique: list[str] = []
    for option in options:
        if option not in unique:
            unique.append(option)
    while len(unique) < 4:
        unique.append(f"Option {len(unique) + 1}")
    rng = Random(seed)
    rng.shuffle(unique)
    return {label: unique[index] for index, label in enumerate(["A", "B", "C", "D"])}
