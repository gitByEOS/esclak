from dataclasses import FrozenInstanceError, replace

import pytest
from rich.cells import cell_len
from rich.segment import Segment

from clak.runtime.progress import ExecProgress, StepProgress, StepState
from clak.tui.views.progress import (
    ProgressStatus,
    ProgressViewData,
    progress_height,
    render_progress,
)


def progress_data(current=2, count=8, status=ProgressStatus.RUNNING, elapsed=3.0):
    steps = tuple(
        StepProgress(
            f"检查{index + 1}",
            StepState.COMPLETED if current is not None and index < current else
            StepState.RUNNING if index == current else StepState.PENDING,
        )
        for index in range(count)
    )
    return ProgressViewData("发布检查", elapsed, ExecProgress(steps, current), status)


def rendered_rows(data, width=80, height=None):
    if height is None:
        height = progress_height(data)
    return list(Segment.split_lines(render_progress(data, width, height)))


def row_text(row):
    return "".join(segment.text for segment in row).rstrip()


def test_progress_view_data_is_frozen_and_none_has_no_output():
    data = progress_data()
    with pytest.raises(FrozenInstanceError):
        data.title = "其他名称"
    assert progress_height(None) == 0
    assert list(render_progress(None, 80, 10)) == []


@pytest.mark.parametrize("status", [ProgressStatus.RUNNING, ProgressStatus.STOPPING])
def test_nine_frames_hold_for_022_seconds_and_repeat_after_198(status):
    sequence = "·✢✶✳✻✳✶✢·"
    for cycle in range(3):
        for frame, mark in enumerate(sequence):
            start = cycle * 1.98 + frame * 0.22
            first = rendered_rows(progress_data(status=status, elapsed=start + 0.001))[0]
            assert row_text(first).startswith(mark)
            for offset in (0.11, 0.219):
                row = rendered_rows(progress_data(status=status, elapsed=start + offset))[0]
                assert row[:2] == first[:2]
    for elapsed in (1.76, 1.87, 1.979, 1.98, 2.09):
        assert row_text(rendered_rows(progress_data(status=status, elapsed=elapsed))[0]).startswith("·")


def test_animation_timing_has_nine_frames_including_final_hold():
    from clak.tui import theme

    assert theme.PROGRESS_PULSE_FRAMES == (0, 1, 2, 3, 4, 3, 2, 1, 0)
    assert theme.PROGRESS_PULSE_PERIOD_SECONDS == pytest.approx(1.98)
    assert theme.PROGRESS_ANIMATION_INTERVAL_SECONDS == 0.22


def test_exact_frame_boundaries_do_not_skip_or_advance_early():
    marks = "·✢✶✳✻✳✶✢·"
    for frame, expected in enumerate(marks):
        elapsed = frame * 0.22
        assert row_text(rendered_rows(progress_data(elapsed=elapsed))[0]).startswith(expected)
        assert row_text(rendered_rows(progress_data(elapsed=elapsed + 0.22 - 0.000001))[0]).startswith(expected)
    assert row_text(rendered_rows(progress_data(elapsed=-1))[0]).startswith("·")


def test_current_marker_and_name_do_not_animate():
    first = rendered_rows(progress_data(elapsed=0))[3]
    for frame in range(27):
        row = rendered_rows(progress_data(elapsed=frame * 0.22))[3]
        assert row == first
        assert next(segment for segment in row if "检查3" in segment.text).style.bold


@pytest.mark.parametrize(
    ("status", "mark", "label"),
    [
        (ProgressStatus.WAITING, "◼", "等待输入"),
        (ProgressStatus.COMPLETED, "✔", "已完成"),
        (ProgressStatus.FAILED, "✘", "失败"),
        (ProgressStatus.CANCELLED, "⏹", "已停止"),
    ],
)
def test_static_status_keeps_fixed_mark_and_label(status, mark, label):
    first = rendered_rows(progress_data(status=status, elapsed=0))
    later = rendered_rows(progress_data(status=status, elapsed=2.1))
    assert row_text(first[0]).startswith(mark)
    assert row_text(later[0]).startswith(mark)
    assert label in row_text(first[0])
    assert first[3] == later[3]


def test_title_counts_current_as_one_based_and_stopping_is_explicit():
    data = progress_data()
    assert "发布检查…（3s · step 3/8 ）" in row_text(rendered_rows(data)[0])
    stopping = replace(data, status=ProgressStatus.STOPPING)
    assert "正在停止" in row_text(rendered_rows(stopping)[0])


def test_empty_queue_never_fabricates_a_step_count():
    data = progress_data(current=None, count=0)
    assert progress_height(data) == 1
    assert row_text(rendered_rows(data)[0]) == "✻ 发布检查…（3s）"


def test_no_current_only_reports_full_count_when_all_steps_are_done():
    data = progress_data(current=None, count=3, status=ProgressStatus.COMPLETED)
    completed = replace(data, progress=ExecProgress(tuple(
        StepProgress(step.name, StepState.COMPLETED) for step in data.progress.steps
    )))
    assert "step 3/3" in row_text(rendered_rows(completed)[0])
    assert "step" not in row_text(rendered_rows(data)[0])
    assert "3/3" not in row_text(rendered_rows(data)[0])


@pytest.mark.parametrize(
    ("current", "visible", "summary"),
    [
        (0, [1, 2, 3, 4, 5], "…"),
        (4, [3, 4, 5, 6, 7], "… +2 completed"),
        (9, [6, 7, 8, 9, 10], "… +5 completed"),
    ],
)
def test_five_step_window_reports_only_hidden_completed_count(current, visible, summary):
    data = progress_data(current=current, count=10)
    rows = [row_text(row) for row in rendered_rows(data)]
    assert progress_height(data) == len(rows) == 7
    assert [row.split("检查")[1] for row in rows[1:-1]] == [str(index) for index in visible]
    assert rows[-1] == f"    {summary}"


@pytest.mark.parametrize("count", range(6))
def test_height_has_no_omission_row_when_every_step_fits(count):
    data = progress_data(current=0 if count else None, count=count)
    assert progress_height(data) == count + 1
    rows = rendered_rows(data)
    assert len(rows) == count + 1
    assert all(not row_text(row).startswith("…") for row in rows[1:])


@pytest.mark.parametrize("height", [1, 2, 3, 4, 5])
def test_short_view_keeps_summary_without_partial_step_list(height):
    data = progress_data(current=5, count=10)
    rows = [row_text(row) for row in rendered_rows(data, height=height)]
    assert len(rows) == height
    assert "step 6/10" in rows[0]
    assert "… +5 completed" in rows[0]
    assert all(not row for row in rows[1:])


def test_six_rows_keep_all_five_steps_and_put_summary_in_title():
    rows = [row_text(row) for row in rendered_rows(progress_data(current=5, count=10), height=6)]
    assert len(rows) == 6
    assert "… +3 completed" in rows[0]
    assert [row.split("检查")[1] for row in rows[1:]] == ["4", "5", "6", "7", "8"]


@pytest.mark.parametrize(
    ("state", "mark"),
    [
        (StepState.PENDING, "◻"),
        (StepState.RUNNING, "◼"),
        (StepState.WAITING, "◼"),
        (StepState.COMPLETED, "✔"),
        (StepState.SKIPPED, "−"),
        (StepState.FAILED, "✘"),
        (StepState.CANCELLED, "⏹"),
    ],
)
def test_every_step_state_has_its_own_symbol(state, mark):
    data = ProgressViewData(
        "执行", 0,
        ExecProgress((StepProgress("中文 deploy é", state),), 0),
        ProgressStatus.RUNNING,
    )
    rows = rendered_rows(data)
    assert row_text(rows[1]) == f"  └ {mark} 中文 deploy é"


@pytest.mark.parametrize("status", list(ProgressStatus))
@pytest.mark.parametrize("width", [1, 2, 8, 80])
@pytest.mark.parametrize("height", [0, 1, 3, 10])
def test_progress_never_exceeds_cell_width_or_height(status, width, height):
    data = progress_data(status=status)
    data = replace(data, title="中文 English é" * 6, progress=ExecProgress(tuple(
        StepProgress("中文 English é" * 6, step.state) for step in data.progress.steps
    ), data.progress.current))
    rows = rendered_rows(data, width, height)
    assert len(rows) == height
    assert all(cell_len("".join(segment.text for segment in row)) == width for row in rows)
    assert all(
        segment.style is None or segment.style.bgcolor is None
        for row in rows for segment in row
    )


@pytest.mark.parametrize("width", [0, -1])
def test_nonpositive_width_has_no_output(width):
    assert list(render_progress(progress_data(), width, 3)) == []


@pytest.mark.parametrize("state", list(StepState))
def test_only_completed_names_have_strikethrough(state):
    data = ProgressViewData(
        "发布", 0, ExecProgress((StepProgress("检查中文 é", state),), 0),
        ProgressStatus.RUNNING,
    )
    row = rendered_rows(data)[1]
    name = next(segment for segment in row if "检查中文" in segment.text)
    mark = next(segment for segment in row if segment.text.strip() and "检查中文" not in segment.text)
    assert bool(name.style.strike) == (state == StepState.COMPLETED)
    assert not mark.style.strike


def test_hidden_summary_counts_completed_on_both_sides_but_not_other_states():
    states = (
        StepState.COMPLETED, StepState.SKIPPED, StepState.COMPLETED,
        StepState.PENDING, StepState.RUNNING, StepState.COMPLETED,
        StepState.PENDING, StepState.FAILED, StepState.CANCELLED, StepState.COMPLETED,
    )
    data = ProgressViewData(
        "发布", 0,
        ExecProgress(tuple(StepProgress(f"检查{index}", state) for index, state in enumerate(states)), 4),
        ProgressStatus.RUNNING,
    )
    rows = [row_text(row) for row in rendered_rows(data)]
    assert rows[-1] == "    … +2 completed"


@pytest.mark.parametrize("count", [6, 8, 10, 30])
def test_window_always_has_five_unique_steps_and_includes_current(count):
    for current in range(count):
        rows = [row_text(row) for row in rendered_rows(progress_data(current=current, count=count))]
        step_rows = rows[1:-1]
        assert len(step_rows) == len(set(step_rows)) == 5
        assert any(row.endswith(f"检查{current + 1}") for row in step_rows)
        assert rows[-1].startswith("    …")
        assert "未显示" not in rows[-1]


def test_all_completed_hidden_steps_are_counted_and_visible_names_are_struck():
    progress = ExecProgress(tuple(StepProgress(f"检查{index}", StepState.COMPLETED) for index in range(8)), 7)
    data = ProgressViewData("发布", 2, progress, ProgressStatus.COMPLETED)
    rows = rendered_rows(data)
    assert row_text(rows[-1]) == "    … +3 completed"
    for row in rows[1:-1]:
        assert next(segment for segment in row if "检查" in segment.text).style.strike


@pytest.mark.parametrize("hidden_state", [StepState.PENDING, StepState.SKIPPED, StepState.FAILED, StepState.CANCELLED])
def test_hidden_noncompleted_steps_use_plain_ellipsis(hidden_state):
    steps = tuple(
        StepProgress(f"检查{index}", StepState.RUNNING if index == 2 else hidden_state)
        for index in range(8)
    )
    data = ProgressViewData("发布", 0, ExecProgress(steps, 2), ProgressStatus.RUNNING)
    assert row_text(rendered_rows(data)[-1]) == "    …"


@pytest.mark.parametrize("status", [ProgressStatus.FAILED, ProgressStatus.CANCELLED, ProgressStatus.STOPPING])
def test_terminal_and_stopping_windows_keep_five_items_and_same_hidden_count(status):
    data = progress_data(current=6, count=10, status=status)
    rows = [row_text(row) for row in rendered_rows(data)]
    assert len(rows[1:-1]) == 5
    assert "step 7/10" in rows[0]
    assert rows[-1] == "    … +4 completed"


def test_completed_name_keeps_strikethrough_after_chinese_crop():
    data = ProgressViewData(
        "发布", 0, ExecProgress((StepProgress("中文内容很长", StepState.COMPLETED),), 0),
        ProgressStatus.COMPLETED,
    )
    row = rendered_rows(data, width=8)[1]
    assert any(segment.style.strike for segment in row if segment.text.strip() and segment.text != "  ✔ ")
    assert cell_len("".join(segment.text for segment in row)) == 8


def test_title_metadata_and_name_are_independent_segments():
    title = rendered_rows(progress_data(elapsed=1))[0]
    name = next(segment for segment in title if "发布检查" in segment.text)
    metadata = next(segment for segment in title if "step" in segment.text)
    assert name is not metadata
    assert "step" not in name.text
    assert "发布检查" not in metadata.text


def test_tree_and_ellipsis_align_with_marker_column():
    rows = [row_text(row) for row in rendered_rows(progress_data())]
    assert rows[1].startswith("  └ ✔ ")
    assert rows[2].startswith("    ✔ ")
    assert rows[3].startswith("    ◼ ")
    assert rows[-1] == "    …"
    assert cell_len(rows[1].split("✔", 1)[0]) == cell_len(rows[-1].split("…", 1)[0]) == 4
    assert cell_len(rows[3].split("◼", 1)[0]) == 4


def test_multiline_names_cannot_escape_row_boundaries():
    data = ProgressViewData(
        "发布\n检查", 0,
        ExecProgress((StepProgress("中文\nEnglish", StepState.RUNNING),), 0),
        ProgressStatus.RUNNING,
    )
    rows = rendered_rows(data)
    assert len(rows) == 2
    assert "发布 检查" in row_text(rows[0])
    assert "中文 English" in row_text(rows[1])
