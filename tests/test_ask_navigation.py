from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from examples.dev_tools.app import app
from examples.dev_tools.context import context


def test_ask_up_down_preserves_draft_and_context(tui_driver):
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    state.input_view.set("draft", 80)
    hint_before = state.footer_line
    state.handle_event(TuiEvent(key=TuiKey("up")))
    assert state.ask_view.selected == 0
    assert state.input_view.input == "draft"
    assert state.footer_line == hint_before
    state.handle_event(TuiEvent(key=TuiKey("down")))
    assert state.ask_view.selected == 1
    assert state.input_view.input == "draft"
    assert state.footer_line == hint_before


def test_custom_row_can_type_digits(tui_driver):
    """custom 聚焦时输入数字应进输入框，不被 1/2 快捷键拦截。"""
    context.reset()
    driver = tui_driver(app)
    state = driver.state
    driver.start("pack-upload")
    state.handle_event(TuiEvent(key=TuiKey("down")))  # 选中 custom（选项 2）
    assert state.ask_view.selected == 1
    for ch in "2026":
        state.handle_event(TuiEvent(key=TuiKey("char", char=ch)))
    assert state.input_view.input == "2026"
