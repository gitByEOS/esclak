from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.tui.event import TuiEvent, TuiKey
from clak.tui.state import TuiState
from examples.dev_tools.app import app
from examples.dev_tools.context import context


def test_multi_ask_space_toggles_and_enter_submits():
    context.reset()
    state = TuiState(app)
    state._start_script("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert state.session
    assert state.session.pending_request
    assert state.session.pending_request.field_id == "targets"
    assert state.ask_view.toggled == frozenset({0, 3})
    state.handle_event(TuiEvent(key=TuiKey("down")))
    state.handle_event(TuiEvent(key=TuiKey("char", char=" ")))
    assert 1 in state.ask_view.toggled
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert state.session is None
