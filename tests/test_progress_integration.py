import asyncio
from threading import Event

import pytest
from rich.console import Console
from rich.segment import Segment

from clak import AskChoice, AskRequest, Clak, OutputView, Script, Session
from clak.runtime.progress import StepState
from clak.runtime.session import SessionResult
from clak.tui.app import ClakApp, ScriptUpdated
from clak.tui.event import TuiEvent, TuiKey
from clak.tui.runner import RunUpdate, ScriptRunner
from clak.tui.screen import ClakRenderable, compute_layout
from clak.tui.views.progress import ProgressStatus


def test_finished_session_snapshot_survives_but_display_is_cleared(tui_driver):
    class WaitScript(Script):
        name = "/wait"
        description = "等待检查"

        def run(self) -> None:
            self.add_step(True, lambda: 1, "等待外部结果")
            self.run_steps()

    registry = Clak()
    registry.register(WaitScript)
    driver = tui_driver(registry)
    driver.start("wait")
    assert driver.state.progress_data().status == ProgressStatus.WAITING
    driver.state._cancel_script()
    driver.wait()
    assert driver.state.progress_data() is None
    assert not driver.state.is_progress_animated()
    assert compute_layout(80, 24, driver.state).progress_height == 0
    driver.state.input_view.set("/clear", 80)
    driver.state.handle_event(TuiEvent(key=TuiKey("enter")))
    assert driver.state.progress_data() is None


def test_output_message_does_not_replace_session_snapshot_message():
    session = Session(OutputView())
    runner = ScriptRunner(Clak(), "test")
    state_message = ScriptUpdated(runner, RunUpdate(None, (), session=session.snapshot))
    output_message = ScriptUpdated(runner, RunUpdate(None, ("日志",)))
    assert not state_message.can_replace(output_message)
    assert not output_message.can_replace(state_message)


@pytest.mark.parametrize("width,height", [(1, 1), (2, 2), (8, 3), (12, 5), (20, 10), (80, 24)])
def test_fixed_progress_layout_fits_with_question_and_menu(tui_driver, width, height):
    class AskScript(Script):
        name = "/ask"
        description = "发布检查"

        def run(self) -> None:
            self.add_step(
                True,
                lambda: self.ask_tool(
                    AskRequest("target", "目标", "prod", (AskChoice("生产", "prod"),)),
                    lambda answer: None,
                ),
                "选择目标",
            )
            self.add_step(True, lambda: 0, "验证目标")
            self.run_steps()

    registry = Clak()
    registry.register(AskScript)
    driver = tui_driver(registry)
    driver.start("ask")
    state = driver.state
    console = Console(width=width, height=height)
    options = console.options.update_dimensions(width, height)
    rendered = ClakRenderable(state)
    rows = list(Segment.split_lines(console.render(rendered, options)))
    assert len(rows) == height
    assert all(Segment.get_line_length(row) <= width for row in rows)
    layout = compute_layout(width, height, state)
    assert sum((layout.history_height, layout.progress_height, layout.overlay_height, layout.input_height, 1)) == height
    if rendered.cursor_screen is not None:
        column, row = rendered.cursor_screen
        assert 0 <= column < width
        assert 0 <= row < height


@pytest.mark.parametrize("width,height", [(80, 24), (80, 11), (80, 10), (80, 5), (8, 24)])
def test_complete_screen_keeps_five_steps_or_title_only(tui_driver, width, height):
    class ProgressScript(Script):
        name = "/progress-window"
        description = "发布检查"

        def run(self) -> None:
            for index in range(10):
                self.add_step(True, (lambda: 1) if index == 4 else (lambda: 0), f"检查{index + 1}")
            self.run_steps()

    registry = Clak()
    registry.register(ProgressScript)
    driver = tui_driver(registry)
    driver.start("progress-window")
    state = driver.state
    history = state.history_view.display()
    console = Console(width=width, height=height)
    options = console.options.update_dimensions(width, height)
    rows = list(Segment.split_lines(console.render(ClakRenderable(state), options)))
    assert len(rows) == height
    assert all(Segment.get_line_length(row) <= width for row in rows)
    step_rows = [
        row for row in rows
        if "".join(segment.text for segment in row).startswith(("  └ ", "    ✔ ", "    ◼ ", "    ◻ "))
    ]
    assert len(step_rows) in (0, 5)
    layout = compute_layout(width, height, state)
    assert len(step_rows) == (5 if layout.progress_height >= 6 else 0)
    if width == 80 and step_rows:
        text = "\n".join("".join(segment.text for segment in row).rstrip() for row in rows)
        assert "step 5/10" in text
        assert "… +2 completed" in text
        names = [segment for row in step_rows for segment in row if "检查" in segment.text]
        assert [segment.text for segment in names] == [f"检查{index}" for index in range(3, 8)]
        assert [bool(segment.style.strike) for segment in names] == [True, True, False, False, False]
    assert state.history_view.display() == history


def test_live_animation_changes_style_without_appending_history():
    async def run() -> None:
        is_started = Event()
        is_released = Event()

        class SlowScript(Script):
            name = "/slow-progress"
            description = "检查发布"

            def run(self) -> None:
                def wait() -> int:
                    is_started.set()
                    assert is_released.wait(3)
                    return 0

                self.add_step(True, wait, "检查配置")
                self.run_steps()

        registry = Clak()
        registry.register(SlowScript)
        app = ClakApp(registry)
        async with app.run_test(size=(80, 24)) as pilot:
            from clak.tui import theme
            from clak.tui.app import ClakView
            view = app.query_one(ClakView)
            assert view._animation_timer._interval == theme.PROGRESS_ANIMATION_INTERVAL_SECONDS
            assert theme.PROGRESS_ANIMATION_INTERVAL_SECONDS == 0.22
            app.state.input_view.set("/slow-progress", 80)
            try:
                await pilot.press("enter")
                assert is_started.is_set()
                assert app.state.is_progress_animated()
                history = app.state.history_view.display()
                before = app.state.progress_data().elapsed_seconds
                await pilot.pause(0.15)
                assert app.state.progress_data().elapsed_seconds > before
                assert app.state.history_view.display() == history
                assert app.state.progress_data().progress.current == 0
            finally:
                is_released.set()
            await pilot.pause()
            assert not app.state.is_progress_animated()
            assert app.state.progress_data() is None
            assert compute_layout(80, 24, app.state).progress_height == 0

    asyncio.run(run())


def test_session_completion_wakes_runner_waiting_for_external_result():
    from threading import Thread
    from clak.tui.runner import RunState

    session = Session(OutputView())
    session.bind_exec_end()
    session.exec_list.add(True, lambda: 1, "等待外部结果")
    session.run()
    runner = ScriptRunner(Clak(), "test")
    is_paused = Event()

    def forward(snapshot) -> None:
        runner.notify_session(snapshot)

    session.set_change_callback(forward)
    worker = Thread(
        target=runner._wait_for_input,
        args=(session, lambda update: is_paused.set() if update.state == RunState.PAUSED else None),
    )
    worker.start()
    try:
        assert is_paused.wait(1)
        session.exec_list.resume()
        worker.join(timeout=1)
        assert not worker.is_alive()
    finally:
        runner.cancel()
        worker.join(timeout=2)


@pytest.mark.parametrize("result", list(SessionResult))
def test_all_terminal_results_clear_display_without_losing_snapshot_or_history(result):
    from clak.runtime.session import SessionSnapshot, SessionState
    from clak.tui.runner import RunState
    from clak.tui.state import TuiState

    state = TuiState()
    state._start_script("checks")
    runner = state.take_pending_runner()
    session = Session(OutputView())
    session.exec_list.add(True, lambda: 1, "检查资源")
    session.run()
    state.apply_run_update(runner, RunUpdate(None, ("检查已开始",), session=session.snapshot, title="发布检查"))
    assert state.progress_data() is not None
    if result == SessionResult.CANCELLED:
        state._cancel_script()
        assert state.progress_data().status == ProgressStatus.STOPPING
    snapshot = SessionSnapshot(
        SessionState.EXITED, session.progress, session.snapshot.started_at,
        session.snapshot.started_at + 1, None, result,
    )
    error = "检查失败" if result == SessionResult.FAILED else None
    state.apply_run_update(runner, RunUpdate(RunState.FINISHED, ("业务输出",), error=error, session=snapshot))
    assert state.progress_data() is None
    assert not state.is_progress_animated()
    assert compute_layout(80, 24, state).progress_height == 0
    assert state.history_view.output_views == []
    assert "业务输出" in state.history_view.display()
    assert ("检查失败" in state.history_view.display()) == bool(error)
    assert snapshot.progress.steps[0].name == "检查资源"
    assert snapshot.result == result
    state.apply_run_update(runner, RunUpdate(None, ("迟到",), session=snapshot))
    assert state.progress_data() is None
    assert "迟到" not in state.history_view.display()
    state._start_script("next")
    next_runner = state.take_pending_runner()
    next_session = Session(OutputView())
    state.apply_run_update(next_runner, RunUpdate(None, (), session=next_session.snapshot, title="下一任务"))
    assert state.progress_data().title == "下一任务"
    next_runner.cancel()


def test_answer_failure_belongs_to_waiting_step():
    session = Session(OutputView())

    def fail(answer) -> None:
        raise ValueError("输入不合法")

    session.exec_list.add(
        True,
        lambda: session.ask_step(AskRequest("target", "目标", "prod", (AskChoice("生产", "prod"),)), fail),
        "选择目标",
    )
    session.run()
    with pytest.raises(ValueError, match="输入不合法"):
        session.provide_input("target", "prod")
    assert session.progress.steps[0].state == StepState.FAILED
    assert session.snapshot.result == SessionResult.FAILED
