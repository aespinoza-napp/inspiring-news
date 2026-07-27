from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:

    name: str

    description: str

    keywords: list[str]