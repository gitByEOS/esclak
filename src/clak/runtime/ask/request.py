from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class AskMode(Enum):
    SINGLE = auto()
    MULTI = auto()
    FILTER = auto()


@dataclass(frozen=True)
class AskChoice:
    label: str
    value: str | None = None


@dataclass(frozen=True)
class AskRequest:
    field_id: str
    prompt: str
    default: str
    choices: tuple[AskChoice, ...] = ()
    mode: AskMode = AskMode.SINGLE
