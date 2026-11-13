from __future__ import annotations

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style

from clak.tui.views.text import fit_line


def format_footer(branch: str, uptime_s: int) -> str:
    return f"{branch} · 脚本聚合 · ⏱ {_format_uptime(uptime_s)}"


def _format_uptime(total_s: int) -> str:
    total_m = total_s // 60
    if total_m < 60:
        return f"{total_m}m"
    h, m = divmod(total_m, 60)
    return f"{h}h{m}m"


def render_footer(text: str, width: int) -> RenderResult:
    yield from fit_line([Segment(text, Style(color="bright_black"))], width)
    yield Segment.line()
