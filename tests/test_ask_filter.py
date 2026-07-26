from clak_py.tui.event import TuiEvent, TuiKey
from clak_py.tui.state import TuiState
from clak_py.tui.views import ask as ask_view


def test_filter_typing_narrows_choices():
    state = TuiState()
    state._start_script("select-server")
    request = state.script_ask_request()
    assert ask_view.is_filter(request)
    # 输入 "prod" 应只剩 prod 相关
    for ch in "prod":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    filtered = ask_view.filtered_choices(request, state.ask_view.query)
    labels = {c.value for c in filtered}
    assert labels == {"prod", "prod-cn", "prod-global"}
    assert state.ask_view.selected == 0


def test_filter_enter_submits_selected():
    state = TuiState()
    state._start_script("select-server")
    # 输入 "asia" 缩到 dev-asia / staging-asia
    for ch in "asia":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    state.handle_event(TuiEvent(key=TuiKey("down")))  # 移到 staging-asia
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    state.after_present()
    assert any("staging-asia" in e.text for e in state.history_view.entries)


def test_filter_backspace_restores():
    state = TuiState()
    state._start_script("select-server")
    request = state.script_ask_request()
    for ch in "prod":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    assert len(ask_view.filtered_choices(request, state.ask_view.query)) == 3
    state.handle_event(TuiEvent(key=TuiKey("backspace")))
    state.handle_event(TuiEvent(key=TuiKey("backspace")))
    assert state.ask_view.query == "pr"
    assert state.ask_view.selected == 0


def test_filter_escape_cancels():
    state = TuiState()
    state._start_script("select-server")
    state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert not state.is_ask_choosing()
