from __future__ import annotations

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style


def format_footer(branch: str, uptime_s: int) -> str:
    return f"{branch} · 脚本聚合 · ⏱ {_format_uptime(uptime_s)}"


def _format_uptime(total_s: int) -> str:
    total_m = total_s // 60
    if total_m < 60:
        return f"{total_m}m"
    h, m = divmod(total_m, 60)
    return f"{h}h{m}m"


def render_footer(text: str, width: int) -> RenderResult:
    yield Segment(text[:width].ljust(width), Style(color="bright_black"))
    yield Segment.line()
