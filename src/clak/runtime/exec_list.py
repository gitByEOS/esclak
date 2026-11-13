"""执行队列：任务返回 0 继续，非 0 挂起，生命周期通知交给会话处理。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

StepDelay = int | float
CanDo = bool | Callable[[], bool]
StepFunc = Callable[..., StepDelay]


class ExecState(Enum):
    WAITING = auto()
    RUNNING = auto()


class ExecNoticeKind(Enum):
    REGISTERED = auto()
    STARTED = auto()
    RETURNED = auto()
    RESUMED = auto()
    SKIPPED = auto()
    FAILED = auto()
    RESET = auto()
    CLEARED = auto()


@dataclass(frozen=True)
class ExecNotice:
    kind: ExecNoticeKind
    index: int = 0
    name: str = ""
    result: StepDelay = 0


@dataclass
class ExecEvent:
    name: str
    can_do: CanDo
    run: StepFunc
    args: tuple[Any, ...] = ()


class ExecList:
    """只执行并通知发生的事实，不保存会话进度。"""

    def __init__(self, *, is_cancelled: Callable[[], bool] | None = None) -> None:
        self._is_cancelled = is_cancelled or (lambda: False)
        self._steps: list[ExecEvent] = []
        self._index = 0
        self._state = ExecState.WAITING
        self._execute_time: StepDelay = 0
        self._end_callback: Callable[[], None] | None = None
        self._notify: Callable[[ExecNotice], None] | None = None

    def set_notify(self, notify: Callable[[ExecNotice], None]) -> None:
        self._notify = notify

    def _emit(self, kind: ExecNoticeKind, index: int = 0, result: StepDelay = 0) -> None:
        if self._notify:
            name = self._steps[index].name if index < len(self._steps) else ""
            self._notify(ExecNotice(kind, index, name, result))

    def set_end_callback(self, callback: Callable[[], None] | None) -> None:
        self._end_callback = callback

    def add(self, can_do: CanDo, run: StepFunc, name: str = "empty", *args: Any) -> None:
        if not isinstance(can_do, bool) and not callable(can_do):
            raise TypeError("can_do 必须是 bool 或 callable")
        if not callable(run):
            raise TypeError("run 必须是 callable")
        self._steps.append(ExecEvent(name=name, can_do=can_do, run=run, args=args))
        self._emit(ExecNoticeKind.REGISTERED, len(self._steps) - 1)

    def clear(self) -> ExecList:
        self._steps.clear()
        self.reset()
        self._emit(ExecNoticeKind.CLEARED)
        return self

    def reset(self) -> ExecList:
        self._state = ExecState.WAITING
        self._index = 0
        self._execute_time = 0
        self._emit(ExecNoticeKind.RESET)
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
        try:
            delay = self._run_from(self._index)
        finally:
            self._state = ExecState.WAITING
        if delay == 0 and self._index >= len(self._steps) and not self._is_cancelled():
            self._finish(delay)

    def resume(self) -> None:
        if self._state != ExecState.WAITING or self._is_cancelled():
            return
        if self._index > 0:
            self._emit(ExecNoticeKind.RESUMED, self._index - 1)
        self.execute()

    def _run_from(self, begin: int) -> StepDelay:
        delay: StepDelay = 0
        index = begin
        while index < len(self._steps) and self._state == ExecState.RUNNING:
            if self._is_cancelled():
                break
            delay = self._execute_step(index)
            if self._is_cancelled() or self._state != ExecState.RUNNING:
                break
            self._execute_time += delay
            index += 1
            self._index = index
            if delay != 0:
                break
        return delay

    def _execute_step(self, index: int) -> StepDelay:
        event = self._steps[index]
        self._emit(ExecNoticeKind.STARTED, index)
        try:
            is_allowed = self._should_run(event.can_do)
            if self._is_cancelled():
                return 0
            if not is_allowed:
                self._emit(ExecNoticeKind.SKIPPED, index)
                return 0
            result = event.run(*event.args) or 0
        except Exception:
            self._emit(ExecNoticeKind.FAILED, index)
            raise
        if self._state == ExecState.RUNNING:
            self._emit(ExecNoticeKind.RETURNED, index, result)
        return result

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
        return bool(can_do()) if callable(can_do) else bool(can_do)
