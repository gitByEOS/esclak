from rich.segment import Segment

from clak.runtime.output import OutputView
from clak.tui.views.history import HistoryEntryKind, HistoryView, render_history


def rendered_rows(history: HistoryView, width: int, height: int) -> list[str]:
    return [
        "".join(segment.text for segment in line).rstrip()
        for line in Segment.split_lines(render_history(history, width, height))
    ]


def history_with_lines(count: int) -> HistoryView:
    history = HistoryView()
    for index in range(count):
        history.push(HistoryEntryKind.OUTPUT, f"日志{index}")
    return history


def test_history_follows_tail_by_default():
    history = history_with_lines(6)
    assert rendered_rows(history, 12, 3) == ["日志3", "日志4", "日志5"]
    history.push(HistoryEntryKind.OUTPUT, "日志6")
    assert rendered_rows(history, 12, 3) == ["日志4", "日志5", "日志6"]
    assert history.scroll == 0


def test_history_pages_by_last_viewport_and_clamps_both_ends():
    history = history_with_lines(8)
    rendered_rows(history, 12, 3)
    history.scroll_up()
    assert history.scroll == 3
    assert rendered_rows(history, 12, 3) == ["日志2", "日志3", "日志4"]
    history.scroll_up()
    assert rendered_rows(history, 12, 3) == ["日志0", "日志1", "日志2"]
    assert history.scroll == 5
    history.scroll_up()
    assert history.scroll == 5
    history.scroll_down()
    assert rendered_rows(history, 12, 3) == ["日志3", "日志4", "日志5"]
    history.scroll_down()
    history.scroll_down()
    assert history.scroll == 0


def test_history_counts_wrapped_display_rows():
    history = HistoryView()
    history.push(HistoryEntryKind.OUTPUT, "一二三四五六")
    assert rendered_rows(history, 4, 2) == ["三四", "五六"]
    history.scroll_up()
    assert rendered_rows(history, 4, 2) == ["一二", "三四"]
    assert history.scroll == 1


def test_history_preserves_reading_position_when_lines_arrive():
    history = history_with_lines(8)
    rendered_rows(history, 12, 3)
    history.scroll_up()
    before = rendered_rows(history, 12, 3)
    history.push(HistoryEntryKind.OUTPUT, "甲乙丙丁戊己庚")
    assert rendered_rows(history, 12, 3) == before
    assert history.scroll == 5


def test_history_preserves_reading_position_for_attached_output():
    history = history_with_lines(7)
    output = OutputView()
    output.push("第一行")
    history.attach(output)
    rendered_rows(history, 12, 3)
    history.scroll_up()
    before = rendered_rows(history, 12, 3)
    output.push("第二行\n第三行")
    assert rendered_rows(history, 12, 3) == before
    assert history.scroll == 5
    history.detach(output)
    assert rendered_rows(history, 12, 3) == before
    assert history.output_views == []
    assert history.display().endswith("第一行\n第二行\n第三行")


def test_history_resize_clamps_offset_without_empty_viewport():
    history = HistoryView()
    history.push(HistoryEntryKind.OUTPUT, "abcdefghijklmnopqrst")
    rendered_rows(history, 2, 3)
    history.scroll_up()
    assert rendered_rows(history, 10, 3) == ["abcdefghij", "klmnopqrst", ""]
    assert history.scroll == 0


def test_history_clear_restores_tail_and_resets_render_baseline():
    history = history_with_lines(10)
    rendered_rows(history, 12, 3)
    history.scroll_up()
    history.clear()
    assert history.scroll == 0
    assert rendered_rows(history, 12, 3) == ["", "", ""]
    history.push(HistoryEntryKind.OUTPUT, "新的日志")
    assert rendered_rows(history, 12, 3) == ["新的日志", "", ""]


def test_history_display_keeps_public_role_and_output_semantics():
    history = HistoryView()
    history.push(HistoryEntryKind.USER, "你好")
    output = OutputView(prefix="[运行] ")
    output.push("输出")
    history.attach(output)
    assert history.display() == "You: 你好\n[运行] 输出"
    history.detach(output)
    assert history.display() == "You: 你好\n[运行] 输出"
