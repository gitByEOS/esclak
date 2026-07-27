"""执行队列：任务返回 0 继续，非 0 挂起。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

StepDelay = int | float
CanDo = bool | Callable[[], bool]
StepFunc = Callable[..., StepDelay]


class ExecState(Enum):
    WAITING = auto()
    RUNNING = auto()


@dataclass
class ExecEvent:
    name: str
    can_do: CanDo
    run: StepFunc
    args: tuple[Any, ...] = ()


class ExecList:
    """顺序执行队列：任务返回 0 同步继续，非 0 挂起直至 resume。"""

    def __init__(self) -> None:
        self._steps: list[ExecEvent] = []
        self._index = 0
        self._state = ExecState.WAITING
        self._execute_time: StepDelay = 0
        self._end_callback: Callable[[], None] | None = None

    def set_end_callback(self, callback: Callable[[], None] | None) -> None:
        self._end_callback = callback

    def add(
        self,
        can_do: CanDo,
        run: StepFunc,
        name: str = "empty",
        *args: Any,
    ) -> None:
        if not isinstance(can_do, bool) and not callable(can_do):
            raise TypeError("can_do 必须是 bool 或 callable")
        if not callable(run):
            raise TypeError("run 必须是 callable")
        self._steps.append(ExecEvent(name=name, can_do=can_do, run=run, args=args))

    def clear(self) -> ExecList:
        self._steps.clear()
        self.stop()
        self.reset()
        return self

    def reset(self) -> ExecList:
        self._state = ExecState.WAITING
        self._index = 0
        self._execute_time = 0
        return self

    def stop(self) -> None:
        self._state = ExecState.WAITING

    @property
    def is_waiting(self) -> bool:
        return self._state == ExecState.WAITING and self._index < len(self._steps)

    @property
    def is_finished(self) -> bool:
        return self._index >= len(self._steps) and self._state == ExecState.WAITING

    def execute(self) -> None:
        if self._state == ExecState.RUNNING:
            return
        self._state = ExecState.RUNNING
        delay = self._run_from(self._index)
        if delay != 0:
            self._state = ExecState.WAITING
            return
        self._state = ExecState.WAITING
        if self._index >= len(self._steps):
            self._finish(delay)

    def resume(self) -> None:
        if self._state != ExecState.WAITING:
            return
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
        raise RuntimeError("delay step requires delay_runner, but none registered")

    @staticmethod
    def _should_run(can_do: CanDo) -> bool:
        if callable(can_do):
            return bool(can_do())
        return bool(can_do)
