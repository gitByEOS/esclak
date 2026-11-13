from types import SimpleNamespace

import pytest
from rich.cells import cell_len
from rich.segment import Segment

from clak.tui.views.input import InputView, render_input, wrap_input_lines


def test_soft_wrap_preserves_original_cursor_offsets():
    view = InputView()
    view.set("abcdefgh", 6)
    view.move_cursor(-3, 6)
    assert view.wrapped_lines(6) == ["abcd", "efgh"]
    assert view.cursor_position(6, 3) == (1, 1)
    view.move_cursor(-1, 6)
    assert view.cursor_position(6, 3) == (0, 1)


def test_hard_and_soft_wraps_have_distinct_offsets():
    view = InputView()
    view.set("abcde\nxy", 6)
    assert view.wrapped_lines(6) == ["abcd", "e", "xy"]
    view.move_cursor(-1, 6)
    assert view.cursor_position(6, 4) == (1, 2)
    view.move_cursor(-2, 6)
    assert view.cursor_position(6, 4) == (1, 1)
    view.move_cursor(1, 6)
    assert view.cursor_position(6, 4) == (0, 2)


def test_wrap_preserves_whitespace_and_combining_characters():
    assert wrap_input_lines("e\u0301e\u0301中 ", 4) == ["e\u0301e\u0301中", " "]
    assert wrap_input_lines(" ab  cd ", 4) == [" ab ", " cd "]
    view = InputView()
    view.set("e\u0301中x", 8)
    view.move_cursor(-1, 8)
    assert view.cursor_position(8, 2) == (3, 0)


def test_empty_and_trailing_hard_newlines_keep_rows():
    assert wrap_input_lines("", 4) == [""]
    assert wrap_input_lines("中\n\n", 4) == ["中", "", ""]


def test_delete_home_and_end_restore_cursor_visibility():
    view = InputView()
    view.set("a" * 100, 6)
    assert view.scroll > 0
    view.move_cursor_home()
    assert view.scroll == 0
    assert view.cursor_position(6, 16) == (0, 0)
    view.move_cursor_end()
    assert view.scroll > 0
    for _ in range(70):
        view.delete_before_cursor()
    assert view.scroll == 0
    assert view.cursor_position(6, 16) == (2, 7)


def test_delete_after_cursor_clamps_scroll_to_remaining_rows():
    view = InputView()
    view.set("a" * 100, 6)
    view.move_cursor(-90, 6)
    for _ in range(90):
        view.delete_after_cursor()
    assert view.input == "a" * 10
    assert view.scroll == 0
    assert view.cursor_position(6, 16) == (2, 2)


@pytest.mark.parametrize("width", [1, 2, 3, 4, 7])
@pytest.mark.parametrize("text", ["", "中文组合e\u0301", "a" * 20, "中\n文"])
def test_input_render_and_cursor_stay_inside_narrow_viewport(width, text):
    view = InputView()
    view.set(text, width)
    cursor = SimpleNamespace(cursor_screen=None)
    segments = list(render_input(view, width, 4, 7, cursor))
    rows = list(Segment.split_lines(segments))
    assert len(rows) == 4
    assert all(cell_len("".join(segment.text for segment in row)) == width for row in rows)
    assert cursor.cursor_screen is not None
    column, row = cursor.cursor_screen
    assert 0 <= column < width
    assert 8 <= row < 10


def test_cursor_position_excludes_rows_above_viewport():
    view = InputView()
    view.set("abc\ndef", 10)
    view.cursor = 0
    view.scroll = 1
    assert view.cursor_position(10, 1) is None


def test_input_mutation_interfaces_keep_existing_return_values():
    view = InputView()
    assert view.set("你好", 12) is None
    assert view.move_cursor(-1, 12) is None
    assert view.insert_at_cursor("e\u0301", 12) is None
    assert view.take() == "你e\u0301好"
    assert view.is_empty()
    assert view.cursor == view.scroll == 0
