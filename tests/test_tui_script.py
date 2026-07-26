from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak.tui.state import TuiState


def test_tui_pack_game_res_ask_and_default():
    state = TuiState()
    state._start_script("pack-game-res")
    assert state.is_ask_choosing()
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert state.is_ask_choosing()
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert not state.is_ask_choosing()
    assert any("全部结束" in entry.text for entry in state.history_view.entries)


def test_tui_pack_game_res_type_version():
    state = TuiState()
    state._start_script("pack-game-res")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    assert state.is_ask_typing()
    state.input_view.set("9.9.9", 80)
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert state.is_ask_choosing()
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert any("9.9.9" in entry.text for entry in state.history_view.entries)


def test_tui_esc_from_type_mode():
    state = TuiState()
    state._start_script("pack-game-res")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    state.input_view.set("draft", 80)
    outcome = state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert outcome == TuiOutcome.REDRAW
    assert state.ask_view.selected == 0
    assert not state.input_view.is_empty()
