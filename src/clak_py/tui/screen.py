from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from rich.console import Console, ConsoleOptions, RenderResult

from clak_py.tui.views import ask as ask_view_mod
from clak_py.tui.views import command_menu as command_view_mod
from clak_py.tui.views import context as context_view_mod
from clak_py.tui.views import history as history_view_mod
from clak_py.tui.views import input as input_view_mod
from clak_py.tui.state import TuiState

CONTEXT_LINE_HEIGHT = 1
INPUT_MIN_HEIGHT = 1
INPUT_BORDER_ROWS = 2


class CursorTarget(Protocol):
    """渲染单元写入光标屏幕坐标的协议。"""

    cursor_screen: tuple[int, int] | None


@dataclass
class ViewLayout:
    history_height: int
    overlay_height: int
    input_height: int


@dataclass
class _CursorHolder:
    cursor_screen: tuple[int, int] | None = None


def compute_layout(area_width: int, area_height: int, state: TuiState) -> ViewLayout:
    width = max(1, area_width)
    height = max(1, area_height)
    request = state.script_ask_request()
    if request:
        content = max(
            ask_view_mod.ASK_PANEL_MIN_ROWS,
            ask_view_mod.panel_row_count(request),
        )
        input_block = content + INPUT_BORDER_ROWS
        overlay_block = 0
    else:
        input_content = max(INPUT_MIN_HEIGHT, state.input_view.visible_lines(width))
        overlay_block = _overlay_block_height(state)
        overlay_block = min(overlay_block + 2, command_view_mod.OVERLAY_MAX_LINES + 2)
        if overlay_block <= 2:
            overlay_block = 0
        input_block = input_content + INPUT_BORDER_ROWS
    while True:
        fixed = input_block + overlay_block + CONTEXT_LINE_HEIGHT
        if fixed < height:
            break
        if overlay_block > 0:
            overlay_block = max(0, overlay_block - 1)
            if overlay_block <= 2:
                overlay_block = 0
            continue
        if input_block > INPUT_MIN_HEIGHT + INPUT_BORDER_ROWS:
            input_block -= 1
            continue
        input_block = INPUT_MIN_HEIGHT + INPUT_BORDER_ROWS
        break
    history_height = max(1, height - input_block - overlay_block - CONTEXT_LINE_HEIGHT)
    return ViewLayout(history_height, overlay_block, input_block)


def _overlay_block_height(state: TuiState) -> int:
    if state.command_view.open:
        return command_view_mod.visible_line_count(state.command_view)
    return 0


class ClakRenderable:
    def __init__(self, state: TuiState) -> None:
        self.state = state
        self._cursor = _CursorHolder()

    @property
    def cursor_screen(self) -> tuple[int, int] | None:
        return self._cursor.cursor_screen

    def __rich_console__(self, console: Console, options: ConsoleOptions) -> RenderResult:
        width = options.max_width
        height = options.max_height or 24
        layout = compute_layout(width, height, self.state)
        y = 0
        self._cursor.cursor_screen = None

        yield from history_view_mod.render_history(
            self.state.history_view, width, layout.history_height
        )
        y += layout.history_height

        if layout.overlay_height > 0:
            yield from command_view_mod.render_command(
                self.state.command_view, width, layout.overlay_height
            )
            y += layout.overlay_height

        input_y = y
        request = self.state.script_ask_request()
        if request:
            yield from ask_view_mod.render_ask(
                request,
                self.state.ask_view,
                self.state.input_view,
                width,
                layout.input_height,
                input_y,
                self._cursor,
            )
        else:
            yield from input_view_mod.render_input(
                self.state.input_view,
                width,
                layout.input_height,
                input_y,
                self._cursor,
            )

        yield from context_view_mod.render_context(
            self.state.context_line, width
        )
