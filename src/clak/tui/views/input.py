from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from rich.cells import cell_len
from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style

from clak.tui import theme
from clak.tui.views.text import fit_line, truncate_cells, wrap_cells

if TYPE_CHECKING:
    from clak.tui.screen import CursorTarget

INPUT_PREFIX = "❯ "
INPUT_MAX_VISIBLE_LINES = 16


def _prefix_width(term_width: int) -> int:
    return min(prefix_display_width(), max(0, term_width - 1))


def inner_width(term_width: int) -> int:
    return max(1, term_width - _prefix_width(term_width))


def prefix_display_width() -> int:
    return cell_len(INPUT_PREFIX)


class InputView:
    def __init__(self) -> None:
        self.input = ""
        self.cursor = 0
        self.scroll = 0
        self._term_width = 80

    def is_empty(self) -> bool:
        return not self.input

    def take(self) -> str:
        text = self.input
        self.input = ""
        self.cursor = 0
        self.scroll = 0
        return text

    def set(self, text: str, term_width: int) -> None:
        self.input = text
        self.cursor = len(self.input)
        self.ensure_cursor_visible(term_width)

    def insert_at_cursor(self, text: str, term_width: int) -> None:
        self.cursor = max(0, min(len(self.input), self.cursor))
        self.input = self.input[:self.cursor] + text + self.input[self.cursor:]
        self.cursor += len(text)
        self.ensure_cursor_visible(term_width)

    def delete_before_cursor(self) -> None:
        if self.cursor == 0:
            return
        self.input = self.input[:self.cursor - 1] + self.input[self.cursor:]
        self.cursor -= 1
        self.ensure_cursor_visible(self._term_width)

    def delete_after_cursor(self) -> None:
        if self.cursor >= len(self.input):
            return
        self.input = self.input[:self.cursor] + self.input[self.cursor + 1:]
        self.ensure_cursor_visible(self._term_width)

    def move_cursor(self, delta: int, term_width: int) -> None:
        self.cursor = max(0, min(len(self.input), self.cursor + delta))
        self.ensure_cursor_visible(term_width)

    def move_cursor_home(self) -> None:
        self.cursor = 0
        self.ensure_cursor_visible(self._term_width)

    def move_cursor_end(self) -> None:
        self.cursor = len(self.input)
        self.ensure_cursor_visible(self._term_width)

    def ensure_cursor_visible(self, term_width: int, max_rows: int | None = None) -> None:
        self._term_width = term_width
        width = inner_width(term_width)
        cursor_row = _cursor_wrapped_row(self.input, self.cursor, width)
        total = len(_wrapped_input_lines(self.input, width))
        visible = max(
            1, min(total, INPUT_MAX_VISIBLE_LINES if max_rows is None else max_rows)
        )
        self.scroll = max(0, min(self.scroll, total - visible))
        if cursor_row >= self.scroll + visible:
            self.scroll = cursor_row - visible + 1
        elif cursor_row < self.scroll:
            self.scroll = cursor_row

    def visible_lines(self, term_width: int) -> int:
        return _visible_lines(self.input, inner_width(term_width))

    def wrapped_lines(self, term_width: int) -> list[str]:
        return wrap_input_lines(self.input, inner_width(term_width))

    def cursor_position(
        self, term_width: int, max_rows: int
    ) -> tuple[int, int] | None:
        return _cursor_position(
            self.input, self.cursor, inner_width(term_width), max_rows, self.scroll
        )


def render_input(
    input_view: InputView,
    width: int,
    height: int,
    start_y: int,
    cursor_target: CursorTarget,
) -> RenderResult:
    if height <= 0:
        return
    rule = "─" * max(0, width)
    yield Segment(rule, Style(color=theme.INPUT_RULE))
    yield Segment.line()
    content_h = max(0, height - 2)
    input_view.ensure_cursor_visible(width, content_h)
    wrapped = input_view.wrapped_lines(width)
    prefix_width = _prefix_width(width)
    for row in range(content_h):
        index = input_view.scroll + row
        line = wrapped[index] if index < len(wrapped) else ""
        prefix = (
            truncate_cells(INPUT_PREFIX, prefix_width) if row == 0 else " " * prefix_width
        )
        style = Style(color="bright_black") if input_view.is_empty() else Style()
        yield from fit_line([Segment(prefix + line, style)], width)
        yield Segment.line()
    position = input_view.cursor_position(width, content_h)
    if position is not None and width > 0:
        column, row = position
        cursor_target.cursor_screen = (
            min(width - 1, prefix_width + column), start_y + 1 + row
        )
    if height > 1:
        yield Segment(rule, Style(color=theme.INPUT_RULE))
        yield Segment.line()


@dataclass(frozen=True)
class _InputLine:
    text: str
    start: int


def _wrapped_input_lines(input_text: str, inner_w: int) -> list[_InputLine]:
    lines: list[_InputLine] = []
    offset = 0
    for raw in input_text.split("\n"):
        start = offset
        for part in wrap_cells(raw, inner_w):
            lines.append(_InputLine(part, start))
            start += len(part)
        # 仅原文的真实换行占用一个字符，软换行不改变偏移
        offset += len(raw) + 1
    return lines


def wrap_input_lines(input_text: str, inner_w: int) -> list[str]:
    return [line.text for line in _wrapped_input_lines(input_text, inner_w)]


def _visible_lines(input_text: str, inner_w: int) -> int:
    return min(INPUT_MAX_VISIBLE_LINES, len(_wrapped_input_lines(input_text, inner_w)))


def _cursor_wrapped_row(input_text: str, char_cursor: int, inner_w: int) -> int:
    cursor = max(0, min(len(input_text), char_cursor))
    wrapped = _wrapped_input_lines(input_text, inner_w)
    return next(
        row for row in range(len(wrapped) - 1, -1, -1) if wrapped[row].start <= cursor
    )


def _cursor_position(
    input_text: str,
    char_cursor: int,
    inner_w: int,
    max_rows: int,
    scroll_row: int,
) -> tuple[int, int] | None:
    wrapped = _wrapped_input_lines(input_text, inner_w)
    row = _cursor_wrapped_row(input_text, char_cursor, inner_w)
    visible_row = row - scroll_row
    if not 0 <= visible_row < max_rows:
        return None
    line = wrapped[row]
    offset = max(0, min(len(line.text), char_cursor - line.start))
    column = min(max(0, inner_w - 1), cell_len(line.text[:offset]))
    return column, visible_row
