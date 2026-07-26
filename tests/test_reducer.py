from clak_py.tui.views.input import InputView
from clak_py.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak_py.tui.state import TuiState


def test_input_view_take_clears():
    c = InputView()
    c.insert_at_cursor("prompt", 80)
    assert c.take() == "prompt"
    assert c.is_empty()


def test_slash_version():
    state = TuiState()
    state.input_view.set("/version", 80)
    outcome = state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert outcome == TuiOutcome.REDRAW
    assert any("0.1.0" in e.text for e in state.history_view.entries)


def test_slash_clear():
    state = TuiState()
    state.input_view.set("/clear", 80)
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert len(state.history_view.entries) == 1
    assert "清空" in state.history_view.entries[0].text


def test_ctrl_c_quit_on_empty():
    state = TuiState()
    outcome = state.handle_event(TuiEvent(key=TuiKey("char", char="c", ctrl=True)))
    assert outcome == TuiOutcome.QUIT
