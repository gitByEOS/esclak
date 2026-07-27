from clak.tui.views import ask as ask_view
from clak.tui.event import TuiEvent, TuiKey
from clak.tui.state import TuiState
from examples.dev_tools.app import app
from examples.dev_tools.context import context


def test_enter_ask_updates_context_immediately():
    context.reset()
    state = TuiState(app)
    state.input_view.set("/pack-upload", 80)
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert state.is_ask_choosing()
    assert state.footer_line == ask_view.status_hint_ask()


def test_escape_from_ask_choice_cancels_to_input_context():
    context.reset()
    state = TuiState(app)
    state._start_script("pack-upload")
    state._sync_surface()
    state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert not state.is_ask_choosing()
    assert "脚本聚合 · ⏱" in state.footer_line
