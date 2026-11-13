"""隔离脚本执行与界面状态，仅通过不可变事件交换数据。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from queue import Queue
from threading import Event

from clak.application import Clak
from clak.runtime.ask import AskRequest
from clak.runtime.params import ScriptInputs
from clak.runtime.session import Session, SessionSnapshot, SessionState


class RunState(Enum):
    RUNNING = auto()
    AWAITING_INPUT = auto()
    PAUSED = auto()
    STOPPING = auto()
    FINISHED = auto()


@dataclass(frozen=True)
class RunUpdate:
    state: RunState | None
    lines: tuple[str, ...]
    request: AskRequest | None = None
    error: str | None = None
    session: SessionSnapshot | None = None
    title: str = ""


@dataclass(frozen=True)
class RunAnswer:
    field_id: str
    wire: str


_SESSION_CHANGED = object()


class ScriptRunner:
    def __init__(self, app: Clak, script_id: str) -> None:
        self.app = app
        self.script_id = script_id
        self._cancelled = Event()
        self._answers: Queue[RunAnswer | object | None] = Queue()

    def notify_session(self, snapshot: SessionSnapshot) -> None:
        if snapshot.state == SessionState.EXITED:
            self._answers.put(_SESSION_CHANGED)

    def provide_input(self, field_id: str, wire: str) -> None:
        self._answers.put(RunAnswer(field_id, wire))

    def cancel(self) -> None:
        self._cancelled.set()
        self._answers.put(None)

    def run(self, publish: Callable[[RunUpdate], None]) -> None:
        script = None
        session = None
        errors: list[str] = []
        try:
            script = self.app.create_script(self.script_id)
            if script is None:
                raise ValueError(f"未知脚本: {self.script_id}")
            output = script.output
            output.set_change_callback(
                lambda: publish(RunUpdate(None, output.render_lines()))
            )
            session = Session(
                output,
                inputs=ScriptInputs(allow_defaults=False),
                is_cancelled=self._cancelled.is_set,
            )
            def forward(snapshot: SessionSnapshot) -> None:
                publish(RunUpdate(
                    None, output.render_lines(), session=snapshot, title=script.description,
                ))
                self.notify_session(snapshot)

            session.set_change_callback(forward)
            script.on_enter(session)
            if not self._cancelled.is_set():
                script.run()
            self._wait_for_input(session, publish)
            if not self._cancelled.is_set():
                session.finish()
        except Exception as error:
            errors.append(str(error) or type(error).__name__)
            if session is not None:
                session.set_change_callback(None)
                session.fail()
        finally:
            cleanup = []
            if session is not None:
                session.set_change_callback(None)
                cleanup.append(session.cancel)
            if script is not None:
                cleanup.append(script.on_exit)
            for finish in cleanup:
                try:
                    finish()
                except Exception as error:
                    errors.append(f"清理失败：{str(error) or type(error).__name__}")
            lines: tuple[str, ...] = ()
            if script is not None:
                script.output.set_change_callback(None)
                try:
                    lines = script.output.render_lines()
                except Exception as error:
                    errors.append(f"输出失败：{str(error) or type(error).__name__}")
            publish(RunUpdate(
                RunState.FINISHED, lines, error="\n".join(errors) or None,
                session=session.snapshot if session is not None else None,
                title=script.description if script is not None else self.script_id,
            ))

    def _wait_for_input(
        self, session: Session, publish: Callable[[RunUpdate], None]
    ) -> None:
        while not session.is_exited and not self._cancelled.is_set():
            request = session.pending_request
            if session.snapshot.state == SessionState.IDLE and request is None:
                return
            state = RunState.AWAITING_INPUT if request else RunState.PAUSED
            publish(RunUpdate(state, session.output.render_lines(), request=request))
            answer = self._answers.get()
            if answer is None or self._cancelled.is_set():
                return
            if answer is _SESSION_CHANGED:
                continue
            if request is not None:
                session.provide_input(answer.field_id, answer.wire)
