from __future__ import annotations

import subprocess
import time
from typing import Literal

from clak.commands._registry import run_script
from clak.runtime.ask import AskRequest
from clak.runtime.params import ScriptInputs
from clak.runtime.session import ScriptSession
from clak.tui.views import ask as ask_view
from clak.tui.views import context as context_view
from clak.tui.views.ask_controller import AskUiBindings, handle_ask_key, sync_view_for_request
from clak.tui.views.ask import AskViewState
from clak.tui.views.command_menu import CommandViewState
from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak.tui.views.history import HistoryEntryKind, HistoryView, role_style
from clak.tui.views.input import InputView
from clak.runtime.slash import (
    SlashAction,
    SlashEngine,
    SlashTokenKind,
)


class TuiState:
    def __init__(self) -> None:
        self.slash_engine = SlashEngine()
        self.input_view = InputView()
        self.history_view = HistoryView()
        self.command_view = CommandViewState()
        self.terminal_width = 80
        self.terminal_height = 24
        self.ask_view = AskViewState()
        self._ask_field_id: str | None = None
        self._deferred_ask_wire: str | None = None
        self.script_session: ScriptSession | None = None
        self.primary: Literal["input", "ask"] = "input"
        self.overlay: Literal["none", "command"] = "none"
        self.started_at = time.monotonic()
        self.branch = _current_branch()
        self.context_line: str = context_view.format_context(self.branch, 0)
        self._sync_surface()
        self.history_view.push(
            HistoryEntryKind.ASSISTANT,
            "clak 就绪；输入 / 查看命令。",
        )

    def uptime_seconds(self) -> int:
        return int(time.monotonic() - self.started_at)

    def tick(self) -> None:
        """每秒由定时器触发，刷新 context_line 中的运行时长。"""
        self._sync_surface()

    def script_ask_request(self) -> AskRequest | None:
        if not self.script_session or not self.script_session.is_awaiting_input:
            return None
        return self.script_session.pending_request

    def is_ask_choosing(self) -> bool:
        return self.script_ask_request() is not None

    def is_ask_typing(self) -> bool:
        request = self.script_ask_request()
        if not request:
            return False
        if ask_view.is_filter(request):
            return True
        custom = ask_view.custom_choice_index(request)
        return custom is not None and self.ask_view.selected == custom

    def after_present(self) -> None:
        wire = self._deferred_ask_wire
        if not wire or not self.script_session:
            return
        request = self.script_session.pending_request
        if not request:
            self._deferred_ask_wire = None
            return
        self.script_session.provide_input(request.field_id, wire)
        self._deferred_ask_wire = None
        self._sync_ask_view()
        self._sync_surface()

    def role_style(self, role: str) -> tuple[str, str]:
        return role_style(role)

    def handle_event(self, event: TuiEvent) -> TuiOutcome:
        outcome = self._handle_event_impl(event)
        self._sync_ask_view()
        self._sync_surface()
        return outcome

    def _sync_ask_view(self) -> None:
        pending = self.script_ask_request()
        self.ask_view, self._ask_field_id = sync_view_for_request(
            pending, self._ask_field_id, self.ask_view
        )

    def _sync_surface(self) -> None:
        primary: Literal["input", "ask"] = "ask" if self.script_ask_request() else "input"
        if self.command_view.open:
            overlay: Literal["none", "command"] = "command"
        else:
            overlay = "none"
        if primary != self.primary:
            self.primary = primary
            self.context_line = self._primary_context(primary)
        elif primary == "input":
            self.context_line = self._input_context()
        if overlay != self.overlay:
            self.overlay = overlay
        if overlay != "none":
            self.context_line = self._overlay_context(overlay)
        elif primary == "ask":
            self.context_line = self._ask_context()

    def _primary_context(self, primary: Literal["input", "ask"]) -> str:
        if primary == "input":
            return self._input_context()
        return self._ask_context()

    def _overlay_context(self, overlay: Literal["none", "command"]) -> str:
        if overlay == "command":
            return "命令菜单 · ↑↓ 选择 · Tab 补全 · Esc 关闭"
        return ""

    def _input_context(self) -> str:
        return context_view.format_context(self.branch, self.uptime_seconds())

    def _ask_context(self) -> str:
        return ask_view.status_hint_ask(self.script_ask_request())

    def _set_ask_context(self, line: str) -> None:
        if self.primary == "ask":
            self.context_line = line

    def _refresh_input_context(self) -> None:
        if self.primary == "input" and self.overlay == "none":
            self.context_line = self._input_context()

    def _handle_event_impl(self, event: TuiEvent) -> TuiOutcome:
        if event.resize_width is not None:
            self.terminal_width = event.resize_width
            self.terminal_height = event.resize_height or self.terminal_height
            self.input_view.ensure_cursor_visible(self.terminal_width)
            return TuiOutcome.REDRAW

        if event.paste is not None:
            if self.is_ask_typing():
                text = event.paste.replace("\n", "")
                if ask_view.is_filter(self.script_ask_request()):
                    self.ask_view.query += text
                    self.ask_view.selected = 0
                else:
                    self.input_view.insert_at_cursor(text, self.terminal_width)
                return TuiOutcome.REDRAW
            self.input_view.insert_at_cursor(event.paste, self.terminal_width)
            self._refresh_command_view()
            return TuiOutcome.REDRAW

        if event.key is None:
            return TuiOutcome.REDRAW

        key = event.key
        if self.is_ask_choosing():
            return self._dispatch_ask_key(key)

        if self.command_view.open:
            outcome = self._handle_command_key(key)
            if outcome is not None:
                return outcome

        outcome = self._handle_input_key(key)
        if outcome is not None:
            return outcome

        return TuiOutcome.REDRAW

    def _ask_bindings(self) -> AskUiBindings | None:
        pending = self.script_ask_request()
        if not pending:
            return None
        return AskUiBindings(
            view=self.ask_view,
            input_view=self.input_view,
            terminal_width=self.terminal_width,
            pending=pending,
            submit_wire=self._submit_ask_wire,
            cancel_script=self._cancel_script,
            set_context_line=lambda line: self._set_ask_context(line),
        )

    def _dispatch_ask_key(self, key: TuiKey) -> TuiOutcome:
        bindings = self._ask_bindings()
        if not bindings:
            return TuiOutcome.REDRAW
        outcome = handle_ask_key(bindings, key)
        self.ask_view = bindings.view
        return outcome if outcome is not None else TuiOutcome.REDRAW

    def _submit_ask_wire(self, wire: str) -> TuiOutcome:
        self.history_view.push(HistoryEntryKind.USER, wire)
        self._deferred_ask_wire = wire
        self.ask_view = AskViewState()
        return TuiOutcome.REDRAW

    def _cancel_script(self) -> TuiOutcome:
        if self.script_session:
            self.script_session.cancel()
            self.script_session = None
        self._deferred_ask_wire = None
        self.ask_view = AskViewState()
        self.history_view.push(HistoryEntryKind.SYSTEM, "已中断脚本，返回主界面")
        return TuiOutcome.REDRAW

    def _handle_command_key(self, key: TuiKey) -> TuiOutcome | None:
        if key.kind == "escape":
            self.command_view.open = False
            return TuiOutcome.REDRAW
        if key.kind == "up":
            self._command_move(-1)
            return TuiOutcome.REDRAW
        if key.kind == "down":
            self._command_move(1)
            return TuiOutcome.REDRAW
        if key.kind == "char" and key.char == "p" and key.ctrl:
            self._command_move(-1)
            return TuiOutcome.REDRAW
        if key.kind == "char" and key.char == "n" and key.ctrl:
            self._command_move(1)
            return TuiOutcome.REDRAW
        if key.kind == "enter":
            self._accept_command_selection()
            return self._submit_line()
        if key.kind == "tab":
            name = self.slash_engine.tab_completion(
                self.input_view.input, self.command_view.selected
            )
            if name:
                self.input_view.set(name, self.terminal_width)
                self._refresh_command_view()
            return TuiOutcome.REDRAW
        return None

    def _command_move(self, delta: int) -> None:
        if not self.command_view.matches:
            return
        if delta < 0:
            self.command_view.selected = (
                len(self.command_view.matches) - 1
                if self.command_view.selected == 0
                else self.command_view.selected - 1
            )
        else:
            self.command_view.selected = (self.command_view.selected + 1) % len(
                self.command_view.matches
            )

    def _handle_input_key(self, key: TuiKey) -> TuiOutcome | None:
        if key.kind == "char" and key.char == "c" and key.ctrl:
            return self._handle_ctrl_c()
        if key.kind == "enter" and not self.command_view.open:
            return self._submit_line()
        if key.kind == "backspace":
            self.input_view.delete_before_cursor()
            self._refresh_command_view()
            return TuiOutcome.REDRAW
        if key.kind == "delete":
            self.input_view.delete_after_cursor()
            self._refresh_command_view()
            return TuiOutcome.REDRAW
        if key.kind == "left":
            self.input_view.move_cursor(-1, self.terminal_width)
            return TuiOutcome.REDRAW
        if key.kind == "right":
            self.input_view.move_cursor(1, self.terminal_width)
            return TuiOutcome.REDRAW
        if key.kind in ("home",) or (key.kind == "char" and key.char == "a" and key.ctrl):
            self.input_view.move_cursor_home()
            return TuiOutcome.REDRAW
        if key.kind in ("end",) or (key.kind == "char" and key.char == "e" and key.ctrl):
            self.input_view.move_cursor_end()
            return TuiOutcome.REDRAW
        if key.kind == "pageup":
            self.history_view.scroll_up()
            return TuiOutcome.REDRAW
        if key.kind == "pagedown":
            self.history_view.scroll_down()
            return TuiOutcome.REDRAW
        if key.kind == "char" and key.char and not key.ctrl:
            self.input_view.insert_at_cursor(key.char, self.terminal_width)
            self._refresh_command_view()
            return TuiOutcome.REDRAW
        return None

    def _handle_ctrl_c(self) -> TuiOutcome:
        if self.input_view.is_empty():
            return TuiOutcome.QUIT
        self.input_view.take()
        self._refresh_command_view()
        self._refresh_input_context()
        return TuiOutcome.REDRAW

    def _submit_line(self) -> TuiOutcome:
        raw = self.input_view.take()
        line = raw.rstrip()
        self._refresh_command_view()
        if not line.strip():
            self._refresh_input_context()
            return TuiOutcome.REDRAW
        if line.startswith("/"):
            return self._dispatch_slash_line(line)
        return self._run_prompt(line)

    def _dispatch_slash_line(self, line: str) -> TuiOutcome:
        result = self.slash_engine.dispatch(line)
        match result.action:
            case SlashAction.QUIT:
                return TuiOutcome.QUIT
            case SlashAction.RUN_SCRIPT:
                if result.command:
                    self._start_script(result.command)
            case SlashAction.NEW_SESSION:
                self.history_view.clear()
            case SlashAction.SHOW_STATUS | SlashAction.NONE:
                pass
            case SlashAction.UNKNOWN:
                pass
        if result.message:
            kind = (
                HistoryEntryKind.ERROR
                if result.action == SlashAction.UNKNOWN
                else HistoryEntryKind.SYSTEM
            )
            self.history_view.push(kind, result.message)
        return TuiOutcome.REDRAW

    def _start_script(self, script_id: str) -> None:
        def log(message: str) -> None:
            self.history_view.push(HistoryEntryKind.SYSTEM, message)

        session = ScriptSession(
            log,
            inputs=ScriptInputs(allow_defaults=False),
        )
        session.on_finished(lambda: self._clear_script_session(session))
        self.script_session = session
        try:
            run_script(session, script_id)
        except ValueError as error:
            self.history_view.push(HistoryEntryKind.ERROR, str(error))
            self.script_session = None
            return
        session._sync_running()
        if self.script_ask_request():
            self.ask_view, self._ask_field_id = sync_view_for_request(
                self.script_ask_request(), self._ask_field_id, self.ask_view
            )

    def _clear_script_session(self, session: ScriptSession) -> None:
        if self.script_session is session:
            self.script_session = None

    def _run_prompt(self, prompt: str) -> TuiOutcome:
        self.history_view.push(HistoryEntryKind.USER, prompt)
        self.history_view.push(HistoryEntryKind.SYSTEM, "请使用 / 开头的 slash 命令")
        return TuiOutcome.REDRAW

    def _refresh_command_view(self) -> None:
        self.command_view.open = self.input_view.input.startswith("/")
        if not self.command_view.open:
            self.command_view.selected = 0
            self.command_view.matches.clear()
            return
        self.command_view.matches = self.slash_engine.filter(self.input_view.input)
        if not self.command_view.matches:
            self.command_view.selected = 0
        elif self.command_view.selected >= len(self.command_view.matches):
            self.command_view.selected = len(self.command_view.matches) - 1

    def _accept_command_selection(self) -> None:
        if not self.command_view.open or not self.command_view.matches:
            return
        selected = self.command_view.matches[self.command_view.selected].name
        token = self.input_view.input.split()[0] if self.input_view.input.split() else ""
        if token == selected:
            return
        rest = self.input_view.input[len(token) :].lstrip()
        new_input = selected if not rest else f"{selected} {rest}"
        self.input_view.set(new_input, self.terminal_width)

    def slash_token_kind(self) -> SlashTokenKind:
        token = self.input_view.input.split()[0] if self.input_view.input.split() else ""
        return self.slash_token_kind_for(token)

    def slash_token_kind_for(self, token: str) -> SlashTokenKind:
        return self.slash_engine.token_kind(token)


def _current_branch() -> str:
    """读取当前 git 分支名，detached 或非 git 仓库时退化到 clak。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        name = result.stdout.strip()
        if name and name != "HEAD":
            return name
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        return result.stdout.strip() or "clak"
    except (subprocess.SubprocessError, OSError):
        return "clak"

