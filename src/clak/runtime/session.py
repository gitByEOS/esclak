from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from time import monotonic

from clak.runtime.exec_list import ExecList, ExecNotice, ExecNoticeKind
from clak.runtime.progress import ExecProgress, StepProgress, StepState
from clak.runtime.ask import AskAnswer, AskRequest, parse_ask_answer
from clak.runtime.params import MissingScriptInputError, ScriptInputs
from clak.runtime.output import OutputView

AnswerFn = Callable[[AskAnswer], None]


class SessionState(Enum):
    IDLE = auto()
    RUNNING = auto()
    AWAITING_INPUT = auto()
    PAUSED = auto()
    EXITED = auto()


class SessionResult(Enum):
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(frozen=True)
class SessionSnapshot:
    state: SessionState
    progress: ExecProgress
    started_at: float
    finished_at: float | None
    request: AskRequest | None
    result: SessionResult | None


class Session:
    """一次脚本运行的状态、输入与专属输出视图。"""

    def __init__(
        self,
        output: OutputView,
        inputs: ScriptInputs | None = None,
        fail_on_missing: bool = False,
        *,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.output = output
        self.inputs = inputs or ScriptInputs()
        self.fail_on_missing = fail_on_missing
        self._is_cancelled = is_cancelled or (lambda: False)
        self.exec_list = ExecList(is_cancelled=self._is_cancelled)
        self._state = SessionState.IDLE
        self._on_exit: Callable[[], None] | None = None
        self._pending_request: AskRequest | None = None
        self._pending_answer: AnswerFn | None = None
        self._progress = ExecProgress()
        self._started_at = monotonic()
        self._finished_at: float | None = None
        self._result: SessionResult | None = None
        self._on_change: Callable[[SessionSnapshot], None] | None = None
        self.exec_list.set_notify(self._on_exec_notice)

    @property
    def progress(self) -> ExecProgress:
        return self._progress

    @property
    def snapshot(self) -> SessionSnapshot:
        return SessionSnapshot(
            self._state, self._progress, self._started_at,
            self._finished_at, self._pending_request, self._result,
        )

    def set_change_callback(self, callback: Callable[[SessionSnapshot], None] | None) -> None:
        self._on_change = callback

    def _notify_changed(self) -> None:
        if self._on_change:
            self._on_change(self.snapshot)

    def _set_current_step(self, state: StepState) -> None:
        current = self._progress.current
        if current is None:
            return
        steps = list(self._progress.steps)
        steps[current] = StepProgress(steps[current].name, state)
        self._progress = ExecProgress(tuple(steps), current)

    def _on_exec_notice(self, notice: ExecNotice) -> None:
        if self.is_exited:
            return
        if notice.kind == ExecNoticeKind.REGISTERED:
            self._progress = ExecProgress(
                (*self._progress.steps, StepProgress(notice.name, StepState.PENDING)),
                self._progress.current,
            )
        elif notice.kind == ExecNoticeKind.CLEARED:
            self._progress = ExecProgress()
        elif notice.kind == ExecNoticeKind.RESET:
            self._progress = ExecProgress(tuple(
                StepProgress(step.name, StepState.PENDING) for step in self._progress.steps
            ))
        else:
            self._apply_step_notice(notice)
        self._notify_changed()

    def _apply_step_notice(self, notice: ExecNotice) -> None:
        self._progress = ExecProgress(self._progress.steps, notice.index)
        states = {
            ExecNoticeKind.STARTED: StepState.RUNNING,
            ExecNoticeKind.RESUMED: StepState.COMPLETED,
            ExecNoticeKind.SKIPPED: StepState.SKIPPED,
            ExecNoticeKind.FAILED: StepState.FAILED,
        }
        state = states.get(notice.kind)
        if notice.kind == ExecNoticeKind.RETURNED:
            state = StepState.WAITING if notice.result != 0 else StepState.COMPLETED
        self._set_current_step(state)
        if state == StepState.WAITING and not self.is_awaiting_input:
            self._state = SessionState.PAUSED
        elif state == StepState.RUNNING or notice.kind == ExecNoticeKind.RESUMED:
            self._state = SessionState.RUNNING
        elif state == StepState.FAILED:
            self._result = SessionResult.FAILED

    def fail(self) -> None:
        if self.is_exited:
            return
        self._result = SessionResult.FAILED
        self._set_current_step(StepState.FAILED)
        self._notify_changed()

    def finish(self) -> None:
        if self.is_exited:
            return
        self._result = self._result or SessionResult.COMPLETED
        self._clear_pending()
        self._exit()

    def _mark_cancelled_steps(self) -> None:
        self._progress = ExecProgress(tuple(
            StepProgress(step.name, StepState.CANCELLED)
            if step.state in (StepState.PENDING, StepState.RUNNING, StepState.WAITING)
            else step
            for step in self._progress.steps
        ), self._progress.current)

    @property
    def pending_request(self) -> AskRequest | None:
        return self._pending_request

    @property
    def is_awaiting_input(self) -> bool:
        return self._state == SessionState.AWAITING_INPUT

    @property
    def is_running(self) -> bool:
        return self._state == SessionState.RUNNING

    @property
    def is_exited(self) -> bool:
        return self._state == SessionState.EXITED

    def on_exit(self, callback: Callable[[], None] | None) -> None:
        self._on_exit = callback

    def bind_exec_end(self) -> None:
        self.exec_list.set_end_callback(self._notify_finished)

    def _notify_finished(self) -> None:
        if self._state == SessionState.RUNNING:
            self.finish()

    def cancel(self) -> None:
        if self._state == SessionState.EXITED:
            return
        self._result = self._result or SessionResult.CANCELLED
        self._mark_cancelled_steps()
        self._clear_pending()
        self._exit()
        self.exec_list.stop()
        self.exec_list.clear()

    def ask_step(self, request: AskRequest, on_answer: AnswerFn) -> int:
        if self._state == SessionState.EXITED or self._is_cancelled():
            return 0
        wire = self.inputs.resolve_wire(request.field_id, request.default)
        if wire is not None:
            on_answer(parse_ask_answer(request, wire))
            return 0
        if self.fail_on_missing:
            raise MissingScriptInputError(request.field_id, request.prompt)
        self._pending_request = request
        self._pending_answer = on_answer
        self._state = SessionState.AWAITING_INPUT
        self._set_current_step(StepState.WAITING)
        self._notify_changed()
        return 1

    def provide_input(self, field_id: str, wire: str) -> bool:
        if self._state != SessionState.AWAITING_INPUT or self._is_cancelled():
            return False
        if not self._pending_request or self._pending_request.field_id != field_id:
            return False
        request = self._pending_request
        answer_cb = self._pending_answer
        answer = parse_ask_answer(request, wire)
        self.inputs.set(field_id, wire)
        self._clear_pending()
        if not answer_cb:
            return False
        self._state = SessionState.RUNNING
        self._set_current_step(StepState.RUNNING)
        self._notify_changed()
        try:
            answer_cb(answer)
        except Exception:
            self.fail()
            raise
        self.exec_list.resume()
        return True

    def run(self) -> None:
        if self._state == SessionState.EXITED or self._is_cancelled():
            return
        self._state = SessionState.RUNNING
        self._notify_changed()
        self.exec_list.execute()

    def _clear_pending(self) -> None:
        self._pending_request = None
        self._pending_answer = None

    def _exit(self) -> None:
        if self._state == SessionState.EXITED:
            return
        self._state = SessionState.EXITED
        self._finished_at = monotonic()
        self._notify_changed()
        if self._on_exit:
            self._on_exit()
