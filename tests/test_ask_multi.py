from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.tui.event import TuiEvent, TuiKey
from examples.dev_tools.app import app
from examples.dev_tools.context import context


def test_multi_ask_space_toggles_and_enter_submits(tui_driver):
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert state.runner
    assert state.script_ask_request().field_id == "targets"
    assert state.ask_view.toggled == frozenset({0, 3})
    state.handle_event(TuiEvent(key=TuiKey("down")))
    state.handle_event(TuiEvent(key=TuiKey("char", char=" ")))
    assert 1 in state.ask_view.toggled
    state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert state.runner is None
