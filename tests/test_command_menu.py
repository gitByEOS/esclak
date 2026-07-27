from rich.segment import Segment

from clak import Clak
from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak.tui.state import TuiState
from clak.tui.views.command_menu import CommandViewState, render_command


def test_filter_fuzzy_matches_quit_and_marks_characters():
    match = Clak().slash_engine.filter("qi")
    assert len(match) == 1
    assert match[0].name == "/quit"
    assert match[0].label == "/quit"
    assert match[0].matched_indices == (1, 3)


def test_filter_prefers_contiguous_alias_match():
    match = Clak().slash_engine.filter("ex")
    assert match[0].name == "/quit"
    assert match[0].label == "/exit"
    assert match[0].matched_indices == (1, 2)


def test_command_menu_renders_fuzzy_matches_in_yellow():
    match = Clak().slash_engine.filter("qi")
    segments = list(
        render_command(CommandViewState(open=True, matches=match), width=80, height=4)
    )
    yellow = [segment.text for segment in segments if isinstance(segment, Segment) and str(segment.style) == "bold yellow"]
    assert yellow == ["q", "i"]


def test_typing_letters_opens_menu_and_enter_runs_selection():
    state = TuiState()
    for char in "ve":
        state.handle_event(TuiEvent(key=TuiKey("char", char=char)))
    assert state.command_view.open
    assert [item.name for item in state.command_view.matches] == ["/version"]

    outcome = state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert outcome == TuiOutcome.REDRAW
    assert any("clak " in entry.text for entry in state.history_view.entries)


def test_command_escape_clears_direct_query():
    state = TuiState()
    state.handle_event(TuiEvent(key=TuiKey("char", char="q")))
    assert state.command_view.open

    state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert state.input_view.is_empty()
    assert not state.command_view.open
