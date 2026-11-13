from __future__ import annotations

from rich.cells import chop_cells
from rich.segment import Segment
from rich.style import Style


def fit_line(
    segments: list[Segment], width: int, style: Style | None = None
) -> list[Segment]:
    return Segment.adjust_line_length(segments, max(0, width), style)


def truncate_cells(text: str, width: int) -> str:
    segments = Segment.adjust_line_length([Segment(text)], max(0, width), pad=False)
    return "".join(segment.text for segment in segments)


def wrap_cells(text: str, width: int) -> list[str]:
    # 宽字在单列视口可能产生空首行，保留原文并交给最终裁切约束边界
    return [part for part in chop_cells(text, max(1, width)) if part] or [text]
