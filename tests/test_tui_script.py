from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from examples.dev_tools.app import app
from examples.dev_tools.context import context


def test_tui_pack_game_res_ask_and_default(tui_driver):
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    assert state.is_ask_choosing()
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert state.is_ask_choosing()
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert not state.is_ask_choosing()
    assert state.runner is None
    assert state.history_view.output_views == []


def test_tui_pack_game_res_type_version(tui_driver):
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    assert state.is_ask_typing()
    state.input_view.set("9.9.9", 80)
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert state.is_ask_choosing()
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert state.runner is None


def test_tui_esc_from_type_mode(tui_driver):
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    state.input_view.set("draft", 80)
    outcome = state.handle_event(TuiEvent(key=TuiKey("escape")))
    assert outcome == TuiOutcome.REDRAW
    assert state.ask_view.selected == 0
    assert not state.input_view.is_empty()


def test_tui_invalid_custom_version_shows_error_and_cleans_up(tui_driver):
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    state.input_view.set("???", 80)
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    history = state.history_view.display()
    assert state.runner is None
    assert "版本号只能包含" in history
    assert "已清理临时打包目录" in history
