from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style
from wcwidth import wcswidth

from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.tui import theme
from clak.tui.views.input import InputView

if TYPE_CHECKING:
    from clak.tui.screen import CursorTarget

TYPE_ROW_GAP = " "
ASK_PANEL_MIN_ROWS = 4
FILTER_WINDOW = 8


@dataclass
class AskViewState:
    selected: int = 0
    toggled: frozenset[int] = field(default_factory=frozenset)
    query: str = ""


def is_multi(request: AskRequest) -> bool:
    return request.mode == AskMode.MULTI


def is_filter(request: AskRequest) -> bool:
    return request.mode == AskMode.FILTER


def init_for_request(request: AskRequest) -> AskViewState:
    if is_filter(request):
        return AskViewState(selected=0, query="")
    if is_multi(request):
        return AskViewState(selected=0, toggled=frozenset(indices_from_default(request)))
    return AskViewState()


def indices_from_default(request: AskRequest) -> list[int]:
    tokens = {part.strip() for part in request.default.split(",") if part.strip()}
    indices: list[int] = []
    for index, choice in enumerate(request.choices):
        token = (choice.value or choice.label).strip()
        if token in tokens:
            indices.append(index)
    return indices


def encode_multi_answer(request: AskRequest, toggled: frozenset[int]) -> str:
    if not toggled:
        return request.default
    parts: list[str] = []
    for index in sorted(toggled):
        choice = request.choices[index]
        parts.append((choice.value or choice.label).strip())
    return ",".join(parts)


def toggle_index(state: AskViewState, index: int) -> AskViewState:
    if index in state.toggled:
        new_toggled = frozenset(i for i in state.toggled if i != index)
    else:
        new_toggled = frozenset((*state.toggled, index))
    return AskViewState(selected=state.selected, toggled=new_toggled)


def custom_choice_index(request: AskRequest) -> int | None:
    if is_filter(request):
        return None
    for index, choice in enumerate(request.choices):
        if choice.value is None:
            return index
    return None


def option_label(choice: AskChoice, index: int) -> str:
    text = choice.label.strip()
    if not text and choice.value is None:
        text = "自定义"
    if not text:
        return f"{index + 1}."
    return f"{index + 1}. {text}"


def option_prefix(index: int, selected: int) -> str:
    mark = "›" if index == selected else " "
    return f" {mark} "


def type_row_head(
    choice: AskChoice,
    index: int,
    selected: int,
    _type_row_index: int,
) -> str:
    return option_prefix(index, selected) + option_label(choice, index) + TYPE_ROW_GAP


def panel_row_count(request: AskRequest) -> int:
    if is_filter(request):
        # prompt + query 行 + 候选窗口
        return 2 + min(len(request.choices), FILTER_WINDOW)
    return 1 + len(request.choices)


def status_hint_ask(request: AskRequest | None = None) -> str:
    if request and is_filter(request):
        return "输入过滤 · ↑↓ 选择 · Enter 确认 · Esc 中断"
    if request and is_multi(request):
        return "↑↓ 移动 · 空格 切换 · Enter 确认 · Esc 中断"
    return "↑↓ 选择 · Enter 确认 · 1/2 · Esc 回到上一项"


def multi_check_prefix(index: int, toggled: frozenset[int], selected: int) -> str:
    mark = "›" if index == selected else " "
    box = "x" if index in toggled else " "
    return f" {mark}[{box}] "


def truncate_to_width(text: str, max_cols: int) -> str:
    if max_cols <= 0:
        return ""
    cols = 0
    out: list[str] = []
    for ch in text:
        w = max(1, wcswidth(ch) or 0)
        if cols + w > max_cols:
            break
        out.append(ch)
        cols += w
    return "".join(out)


def inline_draft_text(input_view: InputView) -> str:
    return input_view.input.replace("\n", "")


def subsequence_match(query: str, target: str) -> bool:
    """fzf 式：query 字符按序出现在 target 中即命中。"""
    if not query:
        return True
    target_lower = target.lower()
    pos = 0
    for ch in query.lower():
        pos = target_lower.find(ch, pos)
        if pos == -1:
            return False
        pos += 1
    return True


def filtered_choices(request: AskRequest, query: str) -> list[AskChoice]:
    if not query:
        return list(request.choices)
    return [
        choice
        for choice in request.choices
        if subsequence_match(query, choice.label or choice.value or "")
    ]


def filter_window(filtered: list[AskChoice], selected: int) -> tuple[int, list[AskChoice]]:
    """返回 (offset, visible)，让 selected 尽量停在窗口中段。"""
    if len(filtered) <= FILTER_WINDOW:
        return 0, filtered
    half = FILTER_WINDOW // 2
    offset = max(0, min(selected - half, len(filtered) - FILTER_WINDOW))
    return offset, filtered[offset : offset + FILTER_WINDOW]


def render_ask(
    request: AskRequest,
    ask_view: AskViewState,
    input_view: InputView,
    width: int,
    height: int,
    start_y: int,
    cursor_target: CursorTarget,
) -> RenderResult:
    title = "─ Ask " + "─" * max(0, width - 6)
    yield Segment(title[:width], Style(color=theme.ASK_RULE))
    yield Segment.line()

    content_h = max(1, height - 2)
    if is_filter(request):
        yield from _render_filter(request, ask_view, width, content_h, start_y, cursor_target)
    else:
        yield from _render_single_multi(
            request, ask_view, input_view, width, content_h, start_y, cursor_target
        )

    while True:
        yield Segment(" " * width, Style())
        yield Segment.line()
        content_h -= 1
        if content_h <= 0:
            break

    yield Segment("─" * width, Style(color=theme.ASK_RULE))
    yield Segment.line()


def _render_filter(
    request: AskRequest,
    ask_view: AskViewState,
    width: int,
    content_h: int,
    start_y: int,
    cursor_target: CursorTarget,
) -> RenderResult:
    row = 0
    if row < content_h:
        yield Segment(request.prompt[:width].ljust(width), Style(bold=True))
        yield Segment.line()
        row += 1

    query = ask_view.query
    query_line = f"> {query}"
    if row < content_h:
        cols = wcswidth(query_line)
        yield Segment(query_line[:width].ljust(width), Style(color=theme.ASK_ACCENT))
        yield Segment.line()
        cursor_target.cursor_screen = (min(cols, width), start_y + 1 + row)
        row += 1

    filtered = filtered_choices(request, query)
    selected = ask_view.selected
    if not filtered:
        if row < content_h:
            yield Segment("  无匹配项", Style(color="dark_orange3"))
            yield Segment.line()
        return
    if selected >= len(filtered):
        selected = len(filtered) - 1
    offset, visible = filter_window(filtered, selected)

    for i, choice in enumerate(visible):
        if row >= content_h:
            break
        actual = offset + i
        is_focused = actual == selected
        prefix = option_prefix(actual, selected)
        label = choice.label.strip() or (choice.value or "")
        text = prefix + label
        style = (
            Style(color=theme.ASK_ACCENT, bold=True)
            if is_focused
            else Style(color=theme.MENU_NORMAL)
        )
        yield Segment(text[:width].ljust(width), style)
        yield Segment.line()
        row += 1


def _render_single_multi(
    request: AskRequest,
    ask_view: AskViewState,
    input_view: InputView,
    width: int,
    content_h: int,
    start_y: int,
    cursor_target: CursorTarget,
) -> RenderResult:
    row = 0
    selected = ask_view.selected
    type_row_index = custom_choice_index(request)
    multi = is_multi(request)

    if row < content_h:
        yield Segment(request.prompt[:width].ljust(width), Style(bold=True))
        yield Segment.line()
        row += 1

    for index, choice in enumerate(request.choices):
        if row >= content_h:
            break
        is_custom_row = (
            not multi and type_row_index is not None and index == type_row_index
        )
        is_focused = index == selected

        if is_custom_row:
            head = type_row_head(choice, index, selected, type_row_index)
            head_cols = wcswidth(head)
            inner_w = max(1, width - head_cols)
            typed = truncate_to_width(inline_draft_text(input_view), inner_w)
            line = head + typed
            style = (
                Style(color=theme.ASK_ACCENT, bold=True)
                if is_focused
                else Style(color="bright_black")
            )
            yield Segment(line[:width].ljust(width), style)
            yield Segment.line()
            if is_focused:
                draft = inline_draft_text(input_view)
                cursor = min(input_view.cursor, len(draft))
                col = wcswidth(draft[:cursor])
                cursor_target.cursor_screen = (head_cols + col, start_y + 1 + row)
            row += 1
            continue

        if multi:
            prefix = multi_check_prefix(index, ask_view.toggled, selected)
            label = choice.label.strip() or (choice.value or "")
        else:
            prefix = option_prefix(index, selected)
            label = option_label(choice, index)
        text = prefix + label
        style = (
            Style(color=theme.ASK_ACCENT, bold=True)
            if is_focused
            else Style(color=theme.MENU_NORMAL)
        )
        yield Segment(text[:width].ljust(width), style)
        yield Segment.line()
        row += 1
