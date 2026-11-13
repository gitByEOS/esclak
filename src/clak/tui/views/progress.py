from __future__ import annotations

from dataclasses import dataclass
from bisect import bisect_right
from enum import Enum, auto

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style
from textual.color import Color

from clak.runtime.progress import ExecProgress, StepProgress, StepState
from clak.tui import theme
from clak.tui.views.text import fit_line


class ProgressStatus(Enum):
    RUNNING = auto()
    WAITING = auto()
    STOPPING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()


@dataclass(frozen=True)
class ProgressViewData:
    title: str
    elapsed_seconds: float
    progress: ExecProgress
    status: ProgressStatus


_STEP_LIMIT = 5
_SPINNER = ("·", "✢", "✶", "✳", "✻")
_ANIMATED = {ProgressStatus.RUNNING, ProgressStatus.STOPPING}
_FINISHED_STEPS = {StepState.COMPLETED, StepState.SKIPPED}
_PULSE_COLORS = tuple(Color.parse(color) for color in theme.PROGRESS_PULSE_PALETTE)
_STATUS = {
    ProgressStatus.WAITING: ("◼", "等待输入", theme.PROGRESS_CANCELLED),
    ProgressStatus.COMPLETED: ("✔", "已完成", theme.PROGRESS_COMPLETED),
    ProgressStatus.FAILED: ("✘", "失败", theme.PROGRESS_FAILED),
    ProgressStatus.CANCELLED: ("⏹", "已停止", theme.PROGRESS_CANCELLED),
}
_STEPS = {
    StepState.PENDING: ("◻", theme.PROGRESS_PENDING),
    StepState.RUNNING: ("◼", theme.PROGRESS_CURRENT),
    StepState.WAITING: ("◼", theme.PROGRESS_CANCELLED),
    StepState.COMPLETED: ("✔", theme.PROGRESS_COMPLETED),
    StepState.SKIPPED: ("−", theme.PROGRESS_PENDING),
    StepState.FAILED: ("✘", theme.PROGRESS_FAILED),
    StepState.CANCELLED: ("⏹", theme.PROGRESS_CANCELLED),
}


def progress_height(data: ProgressViewData | None) -> int:
    if data is None:
        return 0
    count = len(data.progress.steps)
    return 1 + min(_STEP_LIMIT, count) + int(count > _STEP_LIMIT)


def _animation_frame(elapsed: float) -> int:
    phase = max(0.0, elapsed) % theme.PROGRESS_PULSE_PERIOD_SECONDS
    boundaries = tuple(
        index * theme.PROGRESS_ANIMATION_INTERVAL_SECONDS
        for index in range(1, len(theme.PROGRESS_PULSE_FRAMES))
    )
    return theme.PROGRESS_PULSE_FRAMES[bisect_right(boundaries, phase)]


def _animation_style(frame: int) -> Style:
    return Style(color=_PULSE_COLORS[frame].rich_color)


def _heading(data: ProgressViewData) -> tuple[str, str, Style]:
    if data.status in _ANIMATED:
        frame = _animation_frame(data.elapsed_seconds)
        label = "正在停止" if data.status is ProgressStatus.STOPPING else ""
        return _SPINNER[frame], label, _animation_style(frame)
    mark, label, color = _STATUS[data.status]
    return mark, label, Style(color=color)


def _step_count(progress: ExecProgress) -> str:
    count = len(progress.steps)
    if not count:
        return ""
    if progress.current is not None:
        return f"step {progress.current + 1}/{count}"
    if all(step.state in _FINISHED_STEPS for step in progress.steps):
        return f"step {count}/{count}"
    return ""


def _single_line(text: str) -> str:
    return " ".join(text.splitlines())


def _title(data: ProgressViewData, mark: str, label: str, style: Style) -> list[Segment]:
    name = _single_line(data.title)
    count = _step_count(data.progress)
    if data.status in _ANIMATED:
        name += "…"
    if label and not count.startswith(label):
        name += f" · {label}"
    details = [f"{int(max(0.0, data.elapsed_seconds))}s"]
    if count:
        details.append(count)
    closing = " ）" if count else "）"
    title_style = style if data.status in _ANIMATED else Style(color=theme.PROGRESS_TEXT)
    return [
        Segment(f"{mark} ", style),
        Segment(name, title_style),
        Segment(f"（{' · '.join(details)}{closing}", Style(color=theme.PROGRESS_PENDING)),
    ]


def _window(progress: ExecProgress, limit: int) -> tuple[int, int]:
    count = len(progress.steps)
    focus = progress.current
    if focus is None:
        is_finished = count and all(
            step.state in _FINISHED_STEPS for step in progress.steps
        )
        focus = count - 1 if is_finished else 0
    start = max(0, min(focus - limit // 2, count - limit))
    return start, min(count, start + limit)


def _visible_step_count(count: int, height: int) -> int:
    visible = min(_STEP_LIMIT, count)
    return visible if height >= visible + 1 else 0


def _hidden_text(progress: ExecProgress, start: int, end: int) -> str:
    hidden = (*progress.steps[:start], *progress.steps[end:])
    if not hidden:
        return ""
    completed = sum(step.state == StepState.COMPLETED for step in hidden)
    return f"… +{completed} completed" if completed else "…"


def _step_row(step: StepProgress, *, is_first: bool) -> list[Segment]:
    mark, color = _STEPS[step.state]
    marker_style = Style(color=color)
    is_completed = step.state == StepState.COMPLETED
    name_style = Style(
        color=theme.PROGRESS_PENDING if is_completed else theme.PROGRESS_TEXT,
        strike=is_completed,
        bold=step.state == StepState.RUNNING,
    )
    return [
        Segment("  └ " if is_first else "    ", Style(color=theme.PROGRESS_PENDING)),
        Segment(f"{mark} ", marker_style),
        Segment(_single_line(step.name), name_style),
    ]


def _rows(data: ProgressViewData, height: int) -> list[list[Segment]]:
    mark, label, style = _heading(data)
    rows = [_title(data, mark, label, style)]
    count = len(data.progress.steps)
    visible = _visible_step_count(count, height)
    start, end = _window(data.progress, visible) if visible else (0, 0)
    for index in range(start, end):
        rows.append(_step_row(data.progress.steps[index], is_first=index == start))
    hidden = _hidden_text(data.progress, start, end)
    if hidden:
        hint = Segment(hidden, Style(color=theme.PROGRESS_PENDING))
        if visible and len(rows) < height:
            rows.append([Segment("    "), hint])
        else:
            rows[0].extend([Segment(" · "), hint])
    return rows


def render_progress(
    data: ProgressViewData | None, width: int, height: int
) -> RenderResult:
    if data is None or width <= 0 or height <= 0:
        return
    rows = _rows(data, height)
    rows.extend([] for _ in range(height - len(rows)))
    for row in rows[:height]:
        yield from fit_line(row, width)
        yield Segment.line()
