from clak.tui.event import TuiEvent, TuiKey
from clak.tui.state import TuiState
from clak.tui.views import ask as ask_view
from examples.dev_tools.app import app
from examples.dev_tools.context import context


def test_filter_typing_narrows_choices():
    context.reset()
    state = TuiState(app)
    state._start_script("select-res-server")
    request = state.script_ask_request()
    assert ask_view.is_filter(request)
    # 输入 "prod" 应只剩生产资源服
    for ch in "prod":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    filtered = ask_view.filtered_choices(request, state.ask_view.query)
    labels = {c.value for c in filtered}
    assert labels == {"res-prod"}
    assert state.ask_view.selected == 0


def test_filter_enter_submits_selected():
    context.reset()
    state = TuiState(app)
    state._start_script("select-res-server")
    for ch in "staging":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert context.res_server == "res-staging"


def test_filter_backspace_restores():
    context.reset()
    state = TuiState(app)
    state._start_script("select-res-server")
    request = state.script_ask_request()
    for ch in "prod":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    assert len(ask_view.filtered_choices(request, state.ask_view.query)) == 1
    state.handle_event(TuiEvent(key=TuiKey("backspace")))
    state.handle_event(TuiEvent(key=TuiKey("backspace")))
    assert state.ask_view.query == "pr"
    assert state.ask_view.selected == 0


def test_filter_escape_cancels():
    context.reset()
    state = TuiState(app)
    state._start_script("select-res-server")
    state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert not state.is_ask_choosing()
