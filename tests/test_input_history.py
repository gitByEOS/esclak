import asyncio

from clak.tui.app import ClakApp
from clak.tui.event import TuiEvent, TuiKey
from clak.tui.state import TuiState


def press(state, kind, char=None):
    return state.handle_event(TuiEvent(key=TuiKey(kind, char=char)))


def execute(state, line):
    state.input_view.set(line, 80)
    press(state, "enter")


def test_arrows_recall_executed_lines_and_do_not_execute_until_enter():
    state = TuiState()
    execute(state, "/version")
    execute(state, "/status")
    before = len(state.history_view.entries)
    press(state, "up")
    assert state.input_view.input == "/status"
    assert not state.command_view.open
    press(state, "up")
    assert state.input_view.input == "/version"
    press(state, "up")
    assert state.input_view.input == "/version"
    press(state, "down")
    assert state.input_view.input == "/status"
    assert len(state.history_view.entries) == before
    press(state, "enter")
    assert len(state.history_view.entries) == before + 1
    assert state.input_view.input == ""


def test_down_after_latest_returns_empty_and_escape_cancels_history():
    state = TuiState()
    execute(state, "/version")
    press(state, "up")
    press(state, "down")
    assert state.input_view.is_empty()
    press(state, "up")
    press(state, "escape")
    assert state.input_view.is_empty()
    assert not state.command_view.open
    press(state, "up")
    assert state.input_view.input == "/version"


def test_no_history_does_not_change_input():
    state = TuiState()
    press(state, "up")
    press(state, "down")
    assert state.input_view.is_empty()


def test_menu_navigation_stays_available_when_typing_new_command():
    state = TuiState()
    execute(state, "/version")
    press(state, "char", "s")
    assert state.command_view.open
    before = state.input_view.input
    press(state, "down")
    press(state, "up")
    assert state.input_view.input == before
    assert state.command_view.open


def test_recalled_line_can_be_edited_without_changing_saved_history():
    state = TuiState()
    execute(state, "/version")
    press(state, "up")
    press(state, "backspace")
    assert state.input_view.input == "/versio"
    press(state, "escape")
    press(state, "up")
    assert state.input_view.input == "/version"


def test_fuzzy_selection_records_actual_command_and_empty_is_not_recorded():
    state = TuiState()
    press(state, "enter")
    press(state, "char", "v")
    press(state, "char", "e")
    press(state, "enter")
    press(state, "up")
    assert state.input_view.input == "/version"
    press(state, "up")
    assert state.input_view.input == "/version"


def test_history_is_local_to_application_and_clear_keeps_execution_history():
    state = TuiState()
    execute(state, "/version")
    execute(state, "/clear")
    press(state, "up")
    assert state.input_view.input == "/clear"
    press(state, "up")
    assert state.input_view.input == "/version"
    fresh = TuiState()
    press(fresh, "up")
    assert fresh.input_view.is_empty()


def test_ask_answers_do_not_enter_command_history_or_change_ask_navigation(tui_driver):
    from examples.dev_tools.app import app

    driver = tui_driver(app)
    state = driver.state
    execute(state, "/version")
    driver.start("pack-upload")
    press(state, "down")
    assert state.ask_view.selected == 1
    assert state.input_view.is_empty()
    press(state, "up")
    assert state.ask_view.selected == 0
    press(state, "enter")
    driver.wait()
    state._cancel_script()
    driver.wait()
    press(state, "up")
    assert state.input_view.input == "/version"


def test_history_navigation_does_not_restore_unsubmitted_draft():
    state = TuiState()
    execute(state, "/version")
    state.input_view.set("草稿", 80)
    press(state, "escape")
    press(state, "up")
    assert state.input_view.input == "/version"
    press(state, "escape")
    assert state.input_view.input == ""


def test_real_tui_arrows_recall_and_escape_clears():
    async def run():
        app = ClakApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("/", "v", "e", "r", "s", "i", "o", "n", "enter")
            await pilot.press("up")
            assert app.state.input_view.input == "/version"
            await pilot.press("escape")
            assert app.state.input_view.is_empty()
            await pilot.press("up", "enter")
            assert app.state.input_view.is_empty()
            assert sum(entry.text.startswith("clak ") and "就绪" not in entry.text for entry in app.state.history_view.entries) == 2

    asyncio.run(run())
