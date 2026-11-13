"""执行队列的只读步骤快照。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class StepState(Enum):
    PENDING = auto()
    RUNNING = auto()
    WAITING = auto()
    COMPLETED = auto()
    SKIPPED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(frozen=True)
class StepProgress:
    name: str
    state: StepState


@dataclass(frozen=True)
class ExecProgress:
    steps: tuple[StepProgress, ...] = ()
    current: int | None = None
