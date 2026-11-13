from __future__ import annotations

import subprocess
import time
from typing import Literal

from clak.application import Clak, FooterViewData
from clak.runtime.ask import AskRequest
from clak.runtime.output import OutputView
from clak.runtime.session import SessionResult, SessionSnapshot, SessionState
from clak.tui.views.progress import ProgressStatus, ProgressViewData
from clak.tui.runner import RunState, RunUpdate, ScriptRunner
from clak.tui.views import ask as ask_view
from clak.tui.views import footer as footer_view
from clak.tui.views.ask_controller import AskUiBindings, handle_ask_key, sync_view_for_request
from clak.tui.views.ask import AskViewState
from clak.tui.views.command_menu import CommandViewState
from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak.tui.views.history import HistoryEntryKind, HistoryView, role_style
from clak.tui.views.input import InputView
from clak.runtime.slash import SlashAction, SlashTokenKind


class TuiState:
    def __init__(self, app: Clak | None = None) -> None:
        self.app = app or Clak()
        self.slash_engine = self.app.slash_engine
        self.input_view = InputView()
        self.history_view = HistoryView()
        self.command_view = CommandViewState()
        self._input_history: list[str] = []
        self._history_position: int | None = None
        self.terminal_width = 80
        self.terminal_height = 24
        self.ask_view = AskViewState()
        self._ask_field_id: str | None = None
        self.runner: ScriptRunner | None = None
        self._pending_runner: ScriptRunner | None = None
        self.run_state: RunState | None = None
        self._pending_request: AskRequest | None = None
        self._output_view: OutputView | None = None
        self._is_exit_requested = False
        self._session_snapshot: SessionSnapshot | None = None
        self._progress_title = ""
        self.primary: Literal["input", "ask"] = "input"
        self.overlay: Literal["none", "command"] = "none"
        self.started_at = time.monotonic()
        self.branch = _current_branch()
        self.footer_line: str = footer_view.format_footer(self.branch, 0)
        self._sync_surface()
        self.history_view.push(
            HistoryEntryKind.ASSISTANT,
            "clak 就绪；输入字母搜索命令。",
        )

    def uptime_seconds(self) -> int:
        return int(time.monotonic() - self.started_at)

    def tick(self) -> None:
        """每分钟刷新底栏运行时长。"""
        self._sync_surface()

    def progress_data(self, now: float | None = None) -> ProgressViewData | None:
        snapshot = self._session_snapshot
        if snapshot is None:
            return None
        end = snapshot.finished_at
        if end is None:
            end = time.monotonic() if now is None else now
        statuses = {
            SessionResult.COMPLETED: ProgressStatus.COMPLETED,
            SessionResult.FAILED: ProgressStatus.FAILED,
            SessionResult.CANCELLED: ProgressStatus.CANCELLED,
        }
        status = statuses.get(snapshot.result, ProgressStatus.RUNNING)
        if self.run_state == RunState.STOPPING:
            status = ProgressStatus.STOPPING
        elif snapshot.state in (SessionState.AWAITING_INPUT, SessionState.PAUSED):
            status = ProgressStatus.WAITING
        return ProgressViewData(
            self._progress_title, max(0, end - snapshot.started_at), snapshot.progress, status,
        )

    def is_progress_animated(self) -> bool:
        data = self.progress_data()
        return data is not None and data.status in (ProgressStatus.RUNNING, ProgressStatus.STOPPING)

    def script_ask_request(self) -> AskRequest | None:
        return self._pending_request

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

    def take_pending_runner(self) -> ScriptRunner | None:
        runner = self._pending_runner
        self._pending_runner = None
        return runner

    def apply_run_update(self, runner: ScriptRunner, update: RunUpdate) -> TuiOutcome:
        if runner is not self.runner:
            return TuiOutcome.REDRAW
        self._output_view.lines[:] = update.lines
        if update.session is not None:
            self._session_snapshot = update.session
            self._progress_title = update.title or runner.script_id
        if update.state == RunState.FINISHED:
            self.history_view.detach(self._output_view)
            self._output_view = None
            self._pending_request = None
            self.runner = None
            self.run_state = None
            self._session_snapshot = None
            self._progress_title = ""
            if update.error:
                self.history_view.push(HistoryEntryKind.ERROR, update.error)
            if self._is_exit_requested:
                return TuiOutcome.QUIT
        elif update.state is not None and self.run_state != RunState.STOPPING:
            self.run_state = update.state
            self._pending_request = update.request
        self._sync_ask_view()
        self._sync_surface()
        return TuiOutcome.REDRAW

    def request_quit(self) -> TuiOutcome:
        if self.runner is None:
            return TuiOutcome.QUIT
        self._is_exit_requested = True
        return self._cancel_script()

    def role_style(self, role: str) -> tuple[str, str]:
        return role_style(role)

    def footer_content(self) -> str:
        return self.app.footer_view(
            FooterViewData(
                branch=self.branch,
                uptime_seconds=self.uptime_seconds(),
                primary=self.primary,
                overlay=self.overlay,
                hint=self.footer_line,
            )
        )

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
            self.footer_line = self._primary_footer(primary)
        elif primary == "input":
            self.footer_line = self._input_footer()
        if overlay != self.overlay:
            self.overlay = overlay
        if overlay != "none":
            self.footer_line = self._overlay_footer(overlay)
        elif primary == "ask":
            self.footer_line = self._ask_footer()
        elif self.run_state == RunState.STOPPING:
            self.footer_line = "正在停止，等待当前步骤结束"
        elif self.runner is not None:
            self.footer_line = "脚本运行中 · Ctrl+C 停止 · Ctrl+Q 停止后退出"

    def _primary_footer(self, primary: Literal["input", "ask"]) -> str:
        if primary == "input":
            return self._input_footer()
        return self._ask_footer()

    def _overlay_footer(self, overlay: Literal["none", "command"]) -> str:
        if overlay == "command":
            return "命令菜单 · ↑↓ 选择 · Enter 执行 · Tab 补全 · Esc 关闭"
        return ""

    def _input_footer(self) -> str:
        return footer_view.format_footer(self.branch, self.uptime_seconds())

    def _ask_footer(self) -> str:
        return ask_view.status_hint_ask(self.script_ask_request())

    def _set_ask_footer(self, line: str) -> None:
        if self.primary == "ask":
            self.footer_line = line

    def _refresh_input_footer(self) -> None:
        if self.primary == "input" and self.overlay == "none":
            self.footer_line = self._input_footer()

    def _handle_event_impl(self, event: TuiEvent) -> TuiOutcome:
        if event.resize_width is not None:
            self.terminal_width = event.resize_width
            self.terminal_height = event.resize_height or self.terminal_height
            self.input_view.ensure_cursor_visible(self.terminal_width)
            return TuiOutcome.REDRAW

        if event.paste is not None:
            text = event.paste.replace("\r\n", "\n").replace("\r", "\n")
            if self.is_ask_choosing():
                return self._paste_ask(text.replace("\n", ""))
            self.input_view.insert_at_cursor(text, self.terminal_width)
            self._refresh_command_view()
            return TuiOutcome.REDRAW

        if event.key is None:
            return TuiOutcome.REDRAW

        key = event.key
        if key.kind == "char" and key.char == "c" and key.ctrl and self.runner is not None:
            return self._cancel_script()
        if self.is_ask_choosing():
            return self._dispatch_ask_key(key)

        outcome = self._handle_history_key(key)
        if outcome is not None:
            return outcome

        if self.command_view.open:
            outcome = self._handle_command_key(key)
            if outcome is not None:
                return outcome

        outcome = self._handle_input_key(key)
        if outcome is not None:
            return outcome

        return TuiOutcome.REDRAW

    def _paste_ask(self, text: str) -> TuiOutcome:
        if not self.is_ask_typing():
            return TuiOutcome.REDRAW
        if ask_view.is_filter(self.script_ask_request()):
            self.ask_view.query += text
            self.ask_view.selected = 0
        else:
            self.input_view.insert_at_cursor(text, self.terminal_width)
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
            set_footer_line=lambda line: self._set_ask_footer(line),
        )

    def _dispatch_ask_key(self, key: TuiKey) -> TuiOutcome:
        bindings = self._ask_bindings()
        if not bindings:
            return TuiOutcome.REDRAW
        outcome = handle_ask_key(bindings, key)
        self.ask_view = bindings.view
        return outcome if outcome is not None else TuiOutcome.REDRAW

    def _submit_ask_wire(self, wire: str) -> TuiOutcome:
        request = self._pending_request
        if request is None or self.runner is None:
            return TuiOutcome.REDRAW
        self.history_view.push(HistoryEntryKind.USER, wire)
        self.runner.provide_input(request.field_id, wire)
        self._pending_request = None
        self.run_state = RunState.RUNNING
        self.ask_view = AskViewState()
        return TuiOutcome.REDRAW

    def _cancel_script(self) -> TuiOutcome:
        if self.runner is not None and self.run_state != RunState.STOPPING:
            self.runner.cancel()
            self.run_state = RunState.STOPPING
            self._pending_request = None
            self.ask_view = AskViewState()
            self.history_view.push(HistoryEntryKind.SYSTEM, "已请求停止，等待当前步骤结束")
        return TuiOutcome.REDRAW

    def _handle_history_key(self, key: TuiKey) -> TuiOutcome | None:
        is_browsing = self._history_position is not None
        if key.kind == "escape" and is_browsing:
            self._history_position = None
            self.input_view.take()
            self._refresh_command_view()
            return TuiOutcome.REDRAW
        if key.kind not in ("up", "down"):
            return None
        if not is_browsing and (not self.input_view.is_empty() or key.kind == "down"):
            return None
        if not self._input_history:
            return TuiOutcome.REDRAW
        position = len(self._input_history) if not is_browsing else self._history_position
        position = max(0, min(len(self._input_history), position + (-1 if key.kind == "up" else 1)))
        self._history_position = position if position < len(self._input_history) else None
        line = self._input_history[position] if self._history_position is not None else ""
        self.input_view.set(line, self.terminal_width)
        self._refresh_command_view()
        return TuiOutcome.REDRAW

    def _handle_command_key(self, key: TuiKey) -> TuiOutcome | None:
        if key.kind == "escape":
            self.input_view.take()
            self._refresh_command_view()
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
            self._accept_command_selection()
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
        if key.kind == "escape":
            self._history_position = None
            self.input_view.take()
            self._refresh_command_view()
            return TuiOutcome.REDRAW
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
        if self.runner is not None:
            return self._cancel_script()
        if self.input_view.is_empty():
            return TuiOutcome.QUIT
        self._history_position = None
        self.input_view.take()
        self._refresh_command_view()
        self._refresh_input_footer()
        return TuiOutcome.REDRAW

    def _submit_line(self) -> TuiOutcome:
        raw = self.input_view.take()
        line = raw.rstrip()
        self._history_position = None
        self._refresh_command_view()
        if not line.strip():
            self._refresh_input_footer()
            return TuiOutcome.REDRAW
        self._input_history.append(line)
        if line.startswith("/"):
            return self._dispatch_slash_line(line)
        if _is_command_query(line):
            return self._dispatch_slash_line(f"/{line}")
        return self._run_prompt(line)

    def _dispatch_slash_line(self, line: str) -> TuiOutcome:
        result = self.slash_engine.dispatch(line)
        match result.action:
            case SlashAction.QUIT:
                return self.request_quit()
            case SlashAction.RUN_SCRIPT:
                if result.command:
                    self._start_script(result.command)
            case SlashAction.NEW_SESSION:
                self.history_view.clear()
                if self.runner is None:
                    self._session_snapshot = None
                    self._progress_title = ""
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
        if self.runner is not None:
            self.history_view.push(HistoryEntryKind.SYSTEM, "请等待当前脚本结束后再执行")
            return
        self._session_snapshot = None
        self._progress_title = ""
        self.runner = ScriptRunner(self.app, script_id)
        self._pending_runner = self.runner
        self.run_state = RunState.RUNNING
        self._output_view = OutputView()
        self.history_view.attach(self._output_view)

    def _run_prompt(self, prompt: str) -> TuiOutcome:
        self.history_view.push(HistoryEntryKind.USER, prompt)
        self.history_view.push(HistoryEntryKind.SYSTEM, "请使用 / 开头的 slash 命令")
        return TuiOutcome.REDRAW

    def _refresh_command_view(self) -> None:
        self.command_view.open = self._history_position is None and _is_command_query(self.input_view.input)
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


def _is_command_query(text: str) -> bool:
    return bool(text) and (text.startswith("/") or text[0].isalpha())


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
