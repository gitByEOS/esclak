from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.tui.event import TuiEvent, TuiKey
from clak.tui.state import TuiState


def test_multi_ask_space_toggles_and_enter_submits():
    state = TuiState()
    state._start_script("pack-game-res")
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert state.script_session
    assert state.script_session.pending_request
    assert state.script_session.pending_request.field_id == "targets"
    assert state.ask_view.toggled == frozenset({0, 3})
    state.handle_event(TuiEvent(key=TuiKey("down")))
    state.handle_event(TuiEvent(key=TuiKey("char", char=" ")))
    assert 1 in state.ask_view.toggled
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert any("base,ios,cn" in entry.text for entry in state.history_view.entries)
