from __future__ import annotations

from dataclasses import dataclass, field

from rich.cells import cell_len
from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style

from clak.runtime.slash import SlashMatch, SlashTokenKind
from clak.tui import theme
from clak.tui.views.text import fit_line, truncate_cells

OVERLAY_MAX_LINES = 10


@dataclass
class CommandViewState:
    open: bool = False
    selected: int = 0
    matches: list[SlashMatch] = field(default_factory=list)


def visible_line_count(state: CommandViewState) -> int:
    if not state.open:
        return 0
    return min(OVERLAY_MAX_LINES, max(1, len(state.matches)) + 1)


def slash_token_style(kind: SlashTokenKind) -> Style:
    match kind:
        case SlashTokenKind.AVAILABLE:
            return Style(color=theme.SLASH_COMPLETE)
        case SlashTokenKind.UNKNOWN:
            return Style(color=theme.SLASH_UNKNOWN)
        case SlashTokenKind.INCOMPLETE:
            return Style(color=theme.SLASH_TYPING)
        case _:
            return Style()


def render_command(
    state: CommandViewState,
    width: int,
    height: int,
) -> RenderResult:
    title = "命令"
    body_lines = ["Slash 命令"]
    if not state.matches:
        body_lines.append("  (no matches)")
    else:
        for index, item in enumerate(state.matches):
            mark = ">" if index == state.selected else " "
            body_lines.append((mark, item))
    border = f"─ {title} " + "─" * max(0, width - cell_len(title) - 3)
    inner_h = max(0, height - 2)
    rows = [border] + body_lines[:inner_h] + ["─" * width]
    for row in rows[:height]:
        if isinstance(row, tuple):
            mark, item = row
            yield from _render_match_row(mark, item, width)
        else:
            yield from fit_line([Segment(row, Style())], width)
        yield Segment.line()


def _render_match_row(mark: str, item: SlashMatch, width: int) -> RenderResult:
    if width <= 0:
        return
    is_selected = mark == ">"
    base_style = (
        Style(color=theme.MENU_SELECTED, bold=True)
        if is_selected
        else Style(color=theme.MENU_NORMAL)
    )
    highlight_style = base_style + Style(color=theme.COMMAND_MATCH)
    text = truncate_cells(f"{mark} {item.label} — {item.description}", width)
    matched = {index + 2 for index in item.matched_indices}
    segments = [
        Segment(char, highlight_style if index in matched else base_style)
        for index, char in enumerate(text)
    ]
    yield from fit_line(segments, width, base_style)
