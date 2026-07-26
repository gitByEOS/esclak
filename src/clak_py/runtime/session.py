from __future__ import annotations

from collections.abc import Callable

from clak_py.runtime.step_list import StepList
from clak_py.runtime.ask import AskAnswer, AskRequest, parse_ask_answer
from clak_py.runtime.params import MissingScriptInputError, ScriptInputs

LogFn = Callable[[str], None]
AnswerFn = Callable[[AskAnswer], None]


class ScriptSession:
    """Exec 无交互；缺参时挂起 gate，由 provide_input 补齐后继续。"""

    def __init__(
        self,
        log: LogFn,
        *,
        inputs: ScriptInputs | None = None,
        fail_on_missing: bool = False,
    ) -> None:
        self.log = log
        self.inputs = inputs or ScriptInputs()
        self.fail_on_missing = fail_on_missing
        self.step_list = StepList()
        self._cancelled = False
        self._running = False
        self._on_finished: Callable[[], None] | None = None
        self._pending_request: AskRequest | None = None
        self._pending_answer: AnswerFn | None = None

    @property
    def pending_request(self) -> AskRequest | None:
        return self._pending_request

    @property
    def is_awaiting_input(self) -> bool:
        return self._pending_request is not None and not self._cancelled

    @property
    def is_running(self) -> bool:
        return self._running and not self._cancelled

    def on_finished(self, callback: Callable[[], None] | None) -> None:
        self._on_finished = callback

    def bind_step_end(self) -> None:
        self.step_list.set_end_callback(self._notify_finished)

    def _notify_finished(self) -> None:
        if self._cancelled:
            return
        self._running = False
        self._clear_pending()
        if self._on_finished:
            self._on_finished()

    def cancel(self) -> None:
        self._cancelled = True
        self._running = False
        self._clear_pending()
        self.step_list.stop()
        self.step_list.clear()

    def ask_step(self, request: AskRequest, on_answer: AnswerFn) -> int:
        if self._cancelled:
            return 0
        wire = self.inputs.resolve_wire(request.field_id, request.default)
        if wire is not None:
            on_answer(parse_ask_answer(request, wire))
            return 0
        if self.fail_on_missing:
            raise MissingScriptInputError(request.field_id, request.prompt)
        self._pending_request = request
        self._pending_answer = on_answer
        return 1

    def provide_input(self, field_id: str, wire: str) -> bool:
        if self._cancelled:
            return False
        self.inputs.set(field_id, wire)
        if not self._pending_request or self._pending_request.field_id != field_id:
            return False
        request = self._pending_request
        answer_cb = self._pending_answer
        self._clear_pending()
        if not answer_cb:
            return False
        answer_cb(parse_ask_answer(request, wire))
        self.step_list.resume()
        self._sync_running()
        return True

    def run(self) -> None:
        if self._cancelled:
            return
        self._running = True
        self.step_list.execute()
        self._sync_running()

    def _clear_pending(self) -> None:
        self._pending_request = None
        self._pending_answer = None

    def _sync_running(self) -> None:
        if self._cancelled:
            self._running = False
            return
        if self.is_awaiting_input or self.step_list.is_waiting:
            return
        if self.step_list.is_finished:
            self._running = False
