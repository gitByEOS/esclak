from __future__ import annotations

from collections.abc import Callable
from enum import Enum, auto

from clak.runtime.exec_list import ExecList
from clak.runtime.ask import AskAnswer, AskRequest, parse_ask_answer
from clak.runtime.params import MissingScriptInputError, ScriptInputs
from clak.runtime.output import OutputView

AnswerFn = Callable[[AskAnswer], None]


class SessionState(Enum):
    IDLE = auto()
    RUNNING = auto()
    AWAITING_INPUT = auto()
    EXITED = auto()


class Session:
    """一次脚本运行的状态、输入与专属输出视图。"""

    def __init__(
        self,
        output: OutputView,
        inputs: ScriptInputs | None = None,
        fail_on_missing: bool = False,
    ) -> None:
        self.output = output
        self.inputs = inputs or ScriptInputs()
        self.fail_on_missing = fail_on_missing
        self.exec_list = ExecList()
        self._state = SessionState.IDLE
        self._on_exit: Callable[[], None] | None = None
        self._pending_request: AskRequest | None = None
        self._pending_answer: AnswerFn | None = None

    @property
    def pending_request(self) -> AskRequest | None:
        return self._pending_request

    @property
    def is_awaiting_input(self) -> bool:
        return self._state == SessionState.AWAITING_INPUT

    @property
    def is_running(self) -> bool:
        return self._state == SessionState.RUNNING

    def on_exit(self, callback: Callable[[], None] | None) -> None:
        self._on_exit = callback

    def bind_exec_end(self) -> None:
        self.exec_list.set_end_callback(self._notify_finished)

    def _notify_finished(self) -> None:
        if self._state != SessionState.RUNNING:
            return
        self._clear_pending()
        self._exit()

    def cancel(self) -> None:
        if self._state == SessionState.EXITED:
            return
        self._clear_pending()
        self.exec_list.stop()
        self.exec_list.clear()
        self._exit()

    def ask_step(self, request: AskRequest, on_answer: AnswerFn) -> int:
        if self._state == SessionState.EXITED:
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
        return 1

    def provide_input(self, field_id: str, wire: str) -> bool:
        if self._state != SessionState.AWAITING_INPUT:
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
        answer_cb(answer)
        self.exec_list.resume()
        return True

    def run(self) -> None:
        if self._state == SessionState.EXITED:
            return
        self._state = SessionState.RUNNING
        self.exec_list.execute()

    def _clear_pending(self) -> None:
        self._pending_request = None
        self._pending_answer = None

    def _exit(self) -> None:
        if self._state == SessionState.EXITED:
            return
        self._state = SessionState.EXITED
        if self._on_exit:
            self._on_exit()
