import pytest
from rich.console import Console
from rich.segment import Segment

from clak.tui.screen import ClakRenderable
from clak.tui.state import TuiState


@pytest.mark.parametrize("width,height", [(1, 1), (2, 2), (8, 3), (12, 4), (20, 5), (80, 24)])
def test_complete_screen_fits_small_terminal(width, height):
    state = TuiState()
    console = Console(width=width, height=height)
    options = console.options.update_dimensions(width, height)
    segments = list(console.render(ClakRenderable(state), options))
    rows = list(Segment.split_lines(segments))
    assert len(rows) == height
    assert all(Segment.get_line_length(row) <= width for row in rows)
