from clak_py.tui.views import ask as ask_view
from clak_py.tui.event import TuiEvent, TuiKey
from clak_py.tui.state import TuiState


def test_enter_ask_updates_context_immediately():
    state = TuiState()
    state.input_view.set("/pack-game-res", 80)
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert state.is_ask_choosing()
    assert state.context_line == ask_view.status_hint_ask()


def test_escape_from_ask_choice_cancels_to_input_context():
    state = TuiState()
    state._start_script("pack-game-res")
    state._sync_surface()
    state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert not state.is_ask_choosing()
    assert "脚本聚合 · ⏱" in state.context_line
