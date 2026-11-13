import asyncio
from threading import Event, Timer

from textual import events

from clak import Clak, Script
from clak.tui.app import ClakApp, ClakView


def test_paste_reaches_main_input_without_submitting():
    async def run() -> None:
        app = ClakApp()
        async with app.run_test(size=(80, 24)) as pilot:
            app.query_one(ClakView).post_message(events.Paste("/status"))
            await pilot.pause()
            assert app.state.input_view.input == "/status"
            assert len(app.state.history_view.entries) == 1

    asyncio.run(run())


def test_paste_preserves_text_and_normalizes_newlines():
    from clak.tui.event import TuiEvent
    from clak.tui.state import TuiState

    state = TuiState()
    state.input_view.set("前后", 80)
    state.input_view.move_cursor(-1, 80)
    state.handle_event(TuiEvent(paste="中\r\n文\r"))
    assert state.input_view.input == "前中\n文\n后"


def test_paste_targets_only_the_active_ask_input(tui_driver):
    from clak import AskChoice, AskMode, AskRequest
    from clak.tui.event import TuiEvent, TuiKey

    class AskScript(Script):
        name = "/ask"
        description = "提问"

        def run(self) -> None:
            self.add_step(
                True,
                lambda: self.ask_tool(
                    AskRequest(
                        "target", "目标", "prod",
                        (AskChoice("生产", "prod"), AskChoice("其他", None)),
                    ),
                    lambda answer: None,
                ),
                "ask",
            )
            self.run_steps()

    registry = Clak()
    registry.register(AskScript)
    driver = tui_driver(registry)
    driver.start("ask")
    state = driver.state
    state.handle_event(TuiEvent(paste="不应写入"))
    assert state.input_view.input == ""
    state.handle_event(TuiEvent(key=TuiKey("down")))
    state.handle_event(TuiEvent(paste="中\r\n文"))
    assert state.input_view.input == "中文"
    state._cancel_script()
    driver.wait()

    class FilterScript(Script):
        name = "/filter"
        description = "过滤"

        def run(self) -> None:
            self.add_step(
                True,
                lambda: self.ask_tool(
                    AskRequest(
                        "filter", "筛选", "prod",
                        (AskChoice("生产", "prod"),), AskMode.FILTER,
                    ),
                    lambda answer: None,
                ),
                "filter",
            )
            self.run_steps()

    registry.register(FilterScript)
    driver.start("filter")
    state.handle_event(TuiEvent(paste="生\r\n产"))
    assert state.ask_view.query == "生产"
    assert state.input_view.input == "中文"


def test_slow_script_keeps_interface_responsive_and_refreshes_output():
    async def run() -> None:
        is_started = Event()
        is_released = Event()
        is_timer_called = Event()

        class SlowScript(Script):
            name = "/slow"
            description = "耗时任务"

            def run(self) -> None:
                def execute() -> int:
                    self.output.push("任务已开始")
                    is_started.set()
                    assert is_released.wait(2)
                    self.output.push("任务已完成")
                    return 0

                self.add_step(True, execute, "execute")
                self.run_steps()

        registry = Clak()
        registry.register(SlowScript)
        app = ClakApp(registry)
        async with app.run_test(size=(80, 24)) as pilot:
            app.state.input_view.set("/slow", 80)
            app.set_timer(0.05, is_timer_called.set)
            watchdog = Timer(2, is_released.set)
            watchdog.start()
            try:
                await pilot.press("enter")
                assert is_started.is_set()
                assert not is_released.is_set()
                await pilot.pause(0.06)
                assert is_timer_called.is_set()
                assert "任务已开始" in app.state.history_view.display()
                assert "任务已完成" not in app.state.history_view.display()
                await pilot.press("x")
                assert app.state.input_view.input == "x"
            finally:
                is_released.set()
                watchdog.cancel()
            await pilot.pause()

    asyncio.run(run())
