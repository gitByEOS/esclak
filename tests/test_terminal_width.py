from types import SimpleNamespace

import pytest
from rich.cells import cell_len
from rich.segment import Segment

from clak import Clak
from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.runtime.slash import SlashMatch
from clak.tui.views.ask import AskViewState, render_ask, truncate_to_width
from clak.tui.views.command_menu import CommandViewState, render_command
from clak.tui.views.footer import render_footer
from clak.tui.views.history import HistoryEntryKind, HistoryView, render_history
from clak.tui.views.input import InputView


def assert_rows_fit(segments, width, height):
    rows = list(Segment.split_lines(segments))
    assert len(rows) == height
    assert all(cell_len("".join(segment.text for segment in row)) == width for row in rows)


@pytest.mark.parametrize("width", [1, 2, 3, 5, 11, 20])
def test_history_footer_and_menu_obey_cell_width(width):
    history = HistoryView()
    history.push(HistoryEntryKind.SYSTEM, "中文日志e\u0301" * 4)
    assert_rows_fit(render_history(history, width, 3), width, 3)
    assert_rows_fit(render_footer("分支中文 · e\u0301脚本聚合", width), width, 1)
    matches = Clak().slash_engine.filter("qi")
    assert_rows_fit(render_command(CommandViewState(open=True, matches=matches), width, 4), width, 4)


@pytest.mark.parametrize("width", [1, 2, 3, 5, 11, 20])
@pytest.mark.parametrize("mode", [AskMode.SINGLE, AskMode.MULTI, AskMode.FILTER])
def test_ask_panel_obeys_width_height_and_cursor_bounds(width, mode):
    request = AskRequest(
        field_id="测试",
        default="",
        prompt="请选择中文e\u0301选项",
        choices=(AskChoice(label="中文选项", value="中"), AskChoice(label="自定义中文", value=None)),
        mode=mode,
    )
    view = AskViewState(selected=1, query="中文e\u0301" * 5)
    draft = InputView()
    draft.set("中文e\u0301" * 5, width)
    cursor = SimpleNamespace(cursor_screen=None)
    assert_rows_fit(render_ask(request, view, draft, width, 6, 4, cursor), width, 6)
    if cursor.cursor_screen is not None:
        column, row = cursor.cursor_screen
        assert 0 <= column < width
        assert 5 <= row < 9


@pytest.mark.parametrize("height", [0, 1, 2, 3, 4, 8])
def test_ask_renders_exact_requested_height(height):
    request = AskRequest(field_id="目标", default="", prompt="选择", choices=(AskChoice(label="中文", value="中"),))
    assert_rows_fit(render_ask(request, AskViewState(), InputView(), 8, height, 0, SimpleNamespace(cursor_screen=None)), 8, height)


def test_ask_truncation_retains_combining_marks():
    assert truncate_to_width("e\u0301中文", 3) == "e\u0301中"


def test_menu_retains_semantic_matching_style():
    matches = Clak().slash_engine.filter("qi")
    segments = list(render_command(CommandViewState(open=True, matches=matches), 20, 4))
    ordinary = next(segment.style for segment in segments if segment.text == "/")
    assert [segment.text for segment in segments if segment.text in ("q", "u", "i", "t") and segment.style != ordinary] == ["q", "i"]


@pytest.mark.parametrize("width", [1, 2, 3, 4, 5, 6, 7, 8, 9, 15])
def test_chinese_menu_keeps_prefix_and_combining_marks_when_cropped(width):
    match = SlashMatch(name="/中文e\u0301", description="中文描述", matched_indices=(1, 3))
    segments = list(render_command(CommandViewState(open=True, matches=[match]), width, 4))
    assert_rows_fit(segments, width, 4)
    rows = list(Segment.split_lines(segments))
    text = "".join(segment.text for segment in rows[2])
    if width == 8:
        assert text == "> /中文e\u0301"
    if width == 4:
        assert text == "> / "
