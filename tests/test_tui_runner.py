from queue import Queue
from threading import Event, Thread, get_ident

import pytest

from clak import AskChoice, AskRequest, Clak, Script, Session
from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak.tui.runner import RunState, RunUpdate, ScriptRunner


def test_lifecycle_and_answer_callbacks_share_one_worker_thread(tui_driver):
    callbacks: list[tuple[str, int]] = []

    class DeployScript(Script):
        name = "/deploy"
        description = "发布"

        def on_enter(self, session: Session) -> None:
            super().on_enter(session)
            callbacks.append(("进入", get_ident()))

        def run(self) -> None:
            callbacks.append(("运行", get_ident()))

            def ask() -> int:
                return self.ask_tool(
                    AskRequest("target", "目标", "prod", (AskChoice("生产", "prod"),)),
                    lambda answer: callbacks.append(("回答", get_ident())),
                )

            self.add_step(True, ask, "ask")
            self.run_steps()

        def on_exit(self) -> None:
            callbacks.append(("退出", get_ident()))
            self.output.push("资源已清理")
            super().on_exit()

    app = Clak()
    app.register(DeployScript)
    driver = tui_driver(app)
    driver.start("deploy")
    driver.state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert not driver.state.is_ask_choosing()
    driver.state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert [name for name, _ in callbacks] == ["进入", "运行", "回答", "退出"]
    assert len({thread_id for _, thread_id in callbacks}) == 1
    assert callbacks[0][1] != get_ident()
    assert "资源已清理" in driver.state.history_view.display()


def test_cancel_waits_for_step_and_does_not_start_another_script():
    is_started = Event()
    is_released = Event()
    order: list[str] = []

    class SlowScript(Script):
        name = "/slow"
        description = "耗时任务"

        def run(self) -> None:
            def execute() -> int:
                order.append("开始")
                is_started.set()
                assert is_released.wait(3)
                order.append("当前步骤结束")
                return 0

            self.add_step(True, execute, "execute")
            self.add_step(True, lambda: order.append("不应执行") or 0, "after")
            self.run_steps()

        def on_exit(self) -> None:
            order.append("清理")
            super().on_exit()

    from clak.tui.state import TuiState

    app = Clak()
    app.register(SlowScript)
    state = TuiState(app)
    state._start_script("slow")
    runner = state.take_pending_runner()
    updates: Queue[RunUpdate] = Queue()
    thread = Thread(target=runner.run, args=(updates.put,))
    thread.start()
    try:
        assert is_started.wait(1)
        outcome = state.handle_event(TuiEvent(key=TuiKey("char", char="c", ctrl=True)))
        assert outcome == TuiOutcome.REDRAW
        assert state.run_state == RunState.STOPPING
        assert state.runner is runner
        assert order == ["开始"]
        state._start_script("slow")
        assert state.take_pending_runner() is None
        assert state.request_quit() == TuiOutcome.REDRAW
    finally:
        is_released.set()
        thread.join(timeout=3)
    assert not thread.is_alive()
    assert order == ["开始", "当前步骤结束", "清理"]
    while not updates.empty():
        outcome = state.apply_run_update(runner, updates.get_nowait())
    assert outcome == TuiOutcome.QUIT
    assert state.runner is None


@pytest.mark.parametrize("phase", ["on_enter", "run", "on_exit"])
def test_unexpected_errors_are_reported_and_cleanup_runs_once(phase):
    cleanup: list[str] = []

    class FailedScript(Script):
        name = "/failed"
        description = "失败任务"

        def on_enter(self, session: Session) -> None:
            super().on_enter(session)
            if phase == "on_enter":
                raise RuntimeError("初始化失败")

        def run(self) -> None:
            if phase == "run":
                raise RuntimeError("执行失败")

        def on_exit(self) -> None:
            cleanup.append("清理")
            super().on_exit()
            if phase == "on_exit":
                raise RuntimeError("退出失败")

    app = Clak()
    app.register(FailedScript)
    updates: list[RunUpdate] = []
    ScriptRunner(app, "failed").run(updates.append)
    assert cleanup == ["清理"]
    assert updates[-1].state == RunState.FINISHED
    assert "失败" in updates[-1].error


def test_session_cleanup_failure_does_not_skip_script_cleanup():
    cleanup: list[str] = []

    class FailedCleanupScript(Script):
        name = "/failed-cleanup"
        description = "清理失败"

        def on_enter(self, session: Session) -> None:
            super().on_enter(session)

            def fail() -> None:
                raise RuntimeError("订阅清理失败")

            session.on_exit(fail)

        def run(self) -> None:
            self.output.push("执行完成")

        def on_exit(self) -> None:
            cleanup.append("脚本清理")
            super().on_exit()

    app = Clak()
    app.register(FailedCleanupScript)
    updates: list[RunUpdate] = []
    ScriptRunner(app, "failed-cleanup").run(updates.append)
    assert cleanup == ["脚本清理"]
    assert updates[-1].state == RunState.FINISHED
    assert "订阅清理失败" in updates[-1].error


def test_output_render_failure_still_finishes_run():
    from clak import OutputView

    class BrokenOutput(OutputView):
        def render_lines(self) -> tuple[str, ...]:
            raise RuntimeError("输出无法渲染")

    class BrokenScript(Script):
        name = "/broken-output"
        description = "输出失败"
        output_view = BrokenOutput

        def run(self) -> None:
            self.output.push("内容")

    app = Clak()
    app.register(BrokenScript)
    updates: list[RunUpdate] = []
    ScriptRunner(app, "broken-output").run(updates.append)
    assert updates[-1].state == RunState.FINISHED
    assert "输出无法渲染" in updates[-1].error


def test_ctrl_c_cancels_even_when_custom_ask_has_a_draft(tui_driver):
    class AskScript(Script):
        name = "/ask"
        description = "提问"

        def run(self) -> None:
            self.add_step(
                True,
                lambda: self.ask_tool(
                    AskRequest("text", "内容", "", (AskChoice("自定义", None),)),
                    lambda answer: None,
                ),
                "ask",
            )
            self.run_steps()

    app = Clak()
    app.register(AskScript)
    driver = tui_driver(app)
    driver.start("ask")
    driver.state.input_view.set("草稿", 80)
    driver.state.handle_event(TuiEvent(key=TuiKey("char", char="c", ctrl=True)))
    assert driver.state.run_state == RunState.STOPPING
    driver.wait()
    assert driver.state.runner is None


def test_output_notification_preserves_pending_question(tui_driver):
    scripts: list[Script] = []

    class AskScript(Script):
        name = "/ask-output"
        description = "提问与日志"

        def run(self) -> None:
            scripts.append(self)
            self.add_step(
                True,
                lambda: self.ask_tool(
                    AskRequest("target", "目标", "prod", (AskChoice("生产", "prod"),)),
                    lambda answer: None,
                ),
                "ask",
            )
            self.run_steps()

    app = Clak()
    app.register(AskScript)
    driver = tui_driver(app)
    driver.start("ask-output")
    scripts[0].output.push("外部日志")
    runner, update = driver._updates.get(timeout=1)
    driver.state.apply_run_update(runner, update)
    assert driver.state.is_ask_choosing()
    assert "外部日志" in driver.state.history_view.display()
    driver.state.handle_event(TuiEvent(key=TuiKey("enter")))
    driver.wait()
    assert driver.state.runner is None


def test_stale_run_updates_do_not_change_current_state():
    from clak.tui.state import TuiState

    state = TuiState()
    state._start_script("first")
    active = state.runner
    stale = ScriptRunner(state.app, "stale")
    outcome = state.apply_run_update(stale, RunUpdate(RunState.FINISHED, ("过期",)))
    assert outcome == TuiOutcome.REDRAW
    assert state.runner is active
    assert "过期" not in state.history_view.display()
    active.cancel()
