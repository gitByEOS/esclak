"""多步脚本执行列表：步骤返回 0 继续，非 0 挂起。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

StepDelay = int | float
CanDo = bool | Callable[[], bool]
StepFunc = Callable[..., StepDelay]


class StepState(Enum):
    WAITING = auto()
    RUNNING = auto()


@dataclass
class StepEvent:
    name: str
    can_do: CanDo
    run: StepFunc
    args: tuple[Any, ...] = ()


class StepList:
    """多步脚本：run 返回 0 同步继续，非 0 暂停直至 resume。"""

    def __init__(self) -> None:
        self._steps: list[StepEvent] = []
        self._index = 0
        self._state = StepState.WAITING
        self._execute_time: StepDelay = 0
        self._end_callback: Callable[[], None] | None = None
        self._delay_runner: Callable[[StepDelay, Callable[[], None]], None] | None = None
        self.debug_mode = False

    def set_end_callback(self, callback: Callable[[], None] | None) -> None:
        self._end_callback = callback

    def set_delay_runner(
        self, runner: Callable[[StepDelay, Callable[[], None]], None] | None
    ) -> None:
        self._delay_runner = runner

    def add(
        self,
        can_do: CanDo,
        run: StepFunc,
        name: str = "empty",
        *args: Any,
    ) -> None:
        if not self._is_valid_step(can_do, run):
            return
        self._steps.append(StepEvent(name=name, can_do=can_do, run=run, args=args))

    def clear(self) -> StepList:
        self._steps.clear()
        self.stop()
        self.reset()
        return self

    def reset(self) -> StepList:
        self._state = StepState.WAITING
        self._index = 0
        self._execute_time = 0
        return self

    def stop(self) -> None:
        self._state = StepState.WAITING

    @property
    def is_waiting(self) -> bool:
        return self._state == StepState.WAITING and self._index < len(self._steps)

    @property
    def is_finished(self) -> bool:
        return self._index >= len(self._steps) and self._state == StepState.WAITING

    def execute(self) -> None:
        if self._state == StepState.RUNNING:
            return
        self._state = StepState.RUNNING
        delay = self._run_from(self._index)
        if delay > 0 and self._index < len(self._steps):
            self._state = StepState.WAITING
            self._later(delay, self.resume)
            return
        self._state = StepState.WAITING
        if self._index >= len(self._steps):
            self._finish(delay)

    def resume(self) -> None:
        if self._state != StepState.WAITING:
            return
        self.execute()

    def redo(self) -> None:
        if self._state != StepState.WAITING or self._index == 0:
            return
        self._index -= 1
        self.execute()

    def _run_from(self, begin: int) -> StepDelay:
        delay: StepDelay = 0
        for i in range(begin, len(self._steps)):
            event = self._steps[i]
            if not self._should_run(event.can_do):
                self._index = i + 1
                continue
            delay = event.run(*event.args)
            delay = delay or 0
            self._execute_time += delay
            self._index = i + 1
            if delay != 0:
                break
        return delay

    def _finish(self, delay: StepDelay) -> None:
        if not self._end_callback:
            return
        if delay > 0:
            self._later(delay, self._end_callback)
        else:
            self._end_callback()

    def _later(self, delay: StepDelay, func: Callable[[], None]) -> None:
        if delay == 0:
            func()
            return
        if self._delay_runner:
            self._delay_runner(delay, func)

    @staticmethod
    def _is_valid_step(can_do: CanDo, run: StepFunc) -> bool:
        if not (isinstance(can_do, bool) or callable(can_do)):
            return False
        return callable(run)

    @staticmethod
    def _should_run(can_do: CanDo) -> bool:
        if callable(can_do):
            return bool(can_do())
        return bool(can_do)
