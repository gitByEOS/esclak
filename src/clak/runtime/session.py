from __future__ import annotations

from collections.abc import Callable

from clak.runtime.step_list import StepList
from clak.runtime.ask import AskAnswer, AskRequest, parse_ask_answer
from clak.runtime.params import MissingScriptInputError, ScriptInputs
from clak.runtime.output import OutputView

AnswerFn = Callable[[AskAnswer], None]


class Session:
    """一次脚本运行的状态、输入与专属输出视图。"""

    def __init__(
        self,
        output_view: OutputView,
        inputs: ScriptInputs | None = None,
        fail_on_missing: bool = False,
    ) -> None:
        self.output_view = output_view
        self.inputs = inputs or ScriptInputs()
        self.fail_on_missing = fail_on_missing
        self.step_list = StepList()
        self._cancelled = False
        self._running = False
        self._on_exit: Callable[[], None] | None = None
        self._exited = False
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

    def on_exit(self, callback: Callable[[], None] | None) -> None:
        self._on_exit = callback

    def bind_step_end(self) -> None:
        self.step_list.set_end_callback(self._notify_finished)

    def _notify_finished(self) -> None:
        if self._cancelled:
            return
        self._running = False
        self._clear_pending()
        self._exit()

    def cancel(self) -> None:
        self._cancelled = True
        self._running = False
        self._clear_pending()
        self.step_list.stop()
        self.step_list.clear()
        self._exit()

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
        if not self._pending_request or self._pending_request.field_id != field_id:
            return False
        request = self._pending_request
        answer_cb = self._pending_answer
        answer = parse_ask_answer(request, wire)
        self.inputs.set(field_id, wire)
        self._clear_pending()
        if not answer_cb:
            return False
        answer_cb(answer)
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

    def _exit(self) -> None:
        if self._exited:
            return
        self._exited = True
        if self._on_exit:
            self._on_exit()

    def _sync_running(self) -> None:
        if self._cancelled:
            self._running = False
            return
        if self.is_awaiting_input or self.step_list.is_waiting:
            return
        if self.step_list.is_finished:
            self._running = False
