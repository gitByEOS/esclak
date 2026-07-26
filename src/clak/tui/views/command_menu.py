from __future__ import annotations

from dataclasses import dataclass, field

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style

from clak.runtime.slash import SlashMatch, SlashTokenKind
from clak.tui import theme

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
            body_lines.append(f"{mark} {item.name} — {item.description}")
    border = f"─ {title} " + "─" * max(0, width - len(title) - 4)
    inner_h = max(0, height - 2)
    rows = [border] + body_lines[:inner_h] + ["─" * width]
    for row in rows[:height]:
        yield Segment(row[:width].ljust(width), Style())
        yield Segment.line()
