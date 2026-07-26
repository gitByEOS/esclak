from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TuiOutcome(Enum):
    REDRAW = auto()
    QUIT = auto()


@dataclass(frozen=True)
class TuiKey:
    """与终端库解耦的按键模型。"""

    kind: str
    char: str | None = None
    ctrl: bool = False
    shift: bool = False
    meta: bool = False


@dataclass(frozen=True)
class TuiEvent:
    key: TuiKey | None = None
    paste: str | None = None
    resize_width: int | None = None
    resize_height: int | None = None
