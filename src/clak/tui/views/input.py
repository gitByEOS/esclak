from __future__ import annotations

from typing import TYPE_CHECKING

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style
from wcwidth import wcswidth, wcwidth

from clak.tui import theme

if TYPE_CHECKING:
    from clak.tui.screen import CursorTarget

INPUT_PREFIX = "❯ "
INPUT_MAX_VISIBLE_LINES = 16


def inner_width(term_width: int) -> int:
    return max(1, term_width - max(0, wcswidth(INPUT_PREFIX)))


def prefix_display_width() -> int:
    return max(0, wcswidth(INPUT_PREFIX))


class InputView:
    def __init__(self) -> None:
        self.input = ""
        self.cursor = 0
        self.scroll = 0

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
        byte_index = _char_boundary_at(self.input, self.cursor)
        self.input = self.input[:byte_index] + text + self.input[byte_index:]
        self.cursor += len(text)
        self.ensure_cursor_visible(term_width)

    def delete_before_cursor(self) -> None:
        if self.cursor == 0:
            return
        start = _char_boundary_at(self.input, self.cursor - 1)
        end = _char_boundary_at(self.input, self.cursor)
        self.input = self.input[:start] + self.input[end:]
        self.cursor -= 1

    def delete_after_cursor(self) -> None:
        if self.cursor >= len(self.input):
            return
        start = _char_boundary_at(self.input, self.cursor)
        end = _char_boundary_at(self.input, self.cursor + 1)
        self.input = self.input[:start] + self.input[end:]

    def move_cursor(self, delta: int, term_width: int) -> None:
        count = len(self.input)
        self.cursor = max(0, min(count, self.cursor + delta))
        self.ensure_cursor_visible(term_width)

    def move_cursor_home(self) -> None:
        self.cursor = 0

    def move_cursor_end(self) -> None:
        self.cursor = len(self.input)

    def ensure_cursor_visible(self, term_width: int) -> None:
        width = inner_width(term_width)
        cursor_row = _cursor_wrapped_row(self.input, self.cursor, width)
        visible = _visible_lines(self.input, width)
        if cursor_row >= self.scroll + visible:
            self.scroll = max(0, cursor_row - max(0, visible - 1))
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
    rule = "─" * width
    yield Segment(rule, Style(color=theme.INPUT_RULE))
    yield Segment.line()

    content_h = max(1, height - 2)
    prefix = INPUT_PREFIX

    if input_view.is_empty():
        yield Segment(prefix.ljust(width)[:width], Style(color="bright_black"))
        yield Segment.line()
        for _ in range(content_h - 1):
            yield Segment(" " * width, Style())
            yield Segment.line()
        cursor_target.cursor_screen = (prefix_display_width(), start_y + 1)
    else:
        wrapped = input_view.wrapped_lines(width)
        scroll = input_view.scroll
        visible = wrapped[scroll : scroll + content_h]
        while len(visible) < content_h:
            visible.append("")
        for row_index, line in enumerate(visible):
            display_prefix = prefix if row_index == 0 else "  "
            text = display_prefix + line
            yield Segment(text[:width].ljust(width), Style())
            yield Segment.line()
        pos = input_view.cursor_position(width, content_h)
        if pos:
            col, row = pos
            pcols = prefix_display_width() if row == 0 else 2
            cursor_target.cursor_screen = (pcols + col, start_y + 1 + row)

    yield Segment(rule, Style(color=theme.INPUT_RULE))
    yield Segment.line()


def wrap_input_lines(input_text: str, inner_w: int) -> list[str]:
    max_w = max(1, inner_w)
    lines: list[str] = []
    for raw in input_text.split("\n"):
        if not raw:
            lines.append("")
            continue
        current = ""
        column = 0
        for ch in raw:
            width = max(1, wcwidth(ch) or 0)
            if column + width > max_w and current:
                lines.append(current)
                current = ""
                column = 0
            current += ch
            column += width
        lines.append(current)
    if not lines:
        lines.append("")
    return lines


def _visible_lines(input_text: str, inner_w: int) -> int:
    if not input_text:
        return 1
    total = sum(_wrap_line_count(line, inner_w) for line in input_text.split("\n"))
    return max(1, min(INPUT_MAX_VISIBLE_LINES, total))


def _wrap_line_count(line: str, max_width: int) -> int:
    max_w = max(1, max_width)
    if not line:
        return 1
    lines = 1
    column = 0
    for ch in line:
        width = max(1, wcwidth(ch) or 0)
        if column + width > max_w and column > 0:
            lines += 1
            column = width
        else:
            column += width
    return lines


def _cursor_wrapped_row(input_text: str, char_cursor: int, inner_w: int) -> int:
    wrapped = wrap_input_lines(input_text, inner_w)
    chars_seen = 0
    for row, line in enumerate(wrapped):
        line_char_count = len(line)
        if char_cursor <= chars_seen + line_char_count:
            return row
        chars_seen += line_char_count
        if row + 1 < len(wrapped):
            chars_seen += 1
    return max(0, len(wrapped) - 1)


def _cursor_position(
    input_text: str,
    char_cursor: int,
    inner_w: int,
    max_rows: int,
    scroll_row: int,
) -> tuple[int, int] | None:
    wrapped = wrap_input_lines(input_text, inner_w)
    chars_seen = 0
    for row, line in enumerate(wrapped):
        line_char_count = len(line)
        if char_cursor <= chars_seen + line_char_count:
            offset = char_cursor - chars_seen
            col = sum(max(1, wcwidth(ch) or 0) for ch in line[:offset])
            visible_row = row - scroll_row
            if visible_row >= max_rows:
                return None
            return col, visible_row
        chars_seen += line_char_count
        if row + 1 < len(wrapped):
            chars_seen += 1
    return None


def _char_boundary_at(text: str, char_index: int) -> int:
    if char_index <= 0:
        return 0
    if char_index >= len(text):
        return len(text)
    return len(text[:char_index])
