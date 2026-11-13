import asyncio
from threading import Event

import pytest
from textual import events

from clak import AskChoice, AskRequest, Clak, Script
from clak.tui.app import ClakApp, ClakView
from clak.tui.runner import RunState


@pytest.mark.parametrize("is_asking", [False, True])
def test_ctrl_q_waits_for_safe_cleanup(is_asking):
    async def run() -> None:
        is_started = Event()
        is_released = Event()
        cleanup: list[str] = []

        class WaitingScript(Script):
            name = "/waiting"
            description = "等待任务"

            def run(self) -> None:
                def execute() -> int:
                    is_started.set()
                    if is_asking:
                        return self.ask_tool(
                            AskRequest("target", "目标", "prod", (AskChoice("生产", "prod"),)),
                            lambda answer: None,
                        )
                    assert is_released.wait(3)
                    return 0

                self.add_step(True, execute, "execute")
                self.run_steps()

            def on_exit(self) -> None:
                cleanup.append("完成")
                super().on_exit()

        registry = Clak()
        registry.register(WaitingScript)
        app = ClakApp(registry)
        async with app.run_test(size=(80, 24)) as pilot:
            app.state.input_view.set("/waiting", 80)
            await pilot.press("enter")
            assert is_started.is_set()
            try:
                await pilot.press("ctrl+q")
                if not is_asking:
                    assert app.state.run_state == RunState.STOPPING
                    assert cleanup == []
                    assert app.is_running
            finally:
                is_released.set()
            await pilot.pause()
        assert cleanup == ["完成"]

    asyncio.run(run())


def test_real_paste_and_answer_resume_the_same_script():
    async def run() -> None:
        received: list[str] = []

        class AskScript(Script):
            name = "/ask"
            description = "提问"

            def run(self) -> None:
                self.add_step(
                    True,
                    lambda: self.ask_tool(
                        AskRequest("version", "版本", "1", (AskChoice("自定义", None),)),
                        lambda answer: received.append(answer.text),
                    ),
                    "ask",
                )
                self.run_steps()

        registry = Clak()
        registry.register(AskScript)
        app = ClakApp(registry)
        async with app.run_test(size=(80, 24)) as pilot:
            app.state.input_view.set("/ask", 80)
            await pilot.press("enter")
            assert app.state.is_ask_choosing()
            app.query_one(ClakView).post_message(events.Paste("2.0.0"))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert received == ["2.0.0"]
            assert app.state.runner is None

    asyncio.run(run())
