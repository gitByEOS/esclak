import asyncio
from threading import Event

from clak import ScriptTester
from clak.runtime.progress import StepState
from clak.tui.app import ClakApp
from examples.dev_tools import context as context_module
from examples.dev_tools.app import app
from examples.dev_tools.scripts import verify_release


def test_release_check_uses_session_progress_and_keeps_logs_quiet(monkeypatch):
    monkeypatch.setattr(verify_release, "sleep", lambda seconds: None)
    monkeypatch.setattr(context_module.context, "res_server", "res-staging")
    monkeypatch.setattr(context_module.context, "game_server", "game-prod")
    run = ScriptTester(verify_release.VerifyReleaseScript).run()
    assert run.is_awaiting("outcome")
    snapshots = []
    run.session.set_change_callback(snapshots.append)
    run.provide("outcome", "success")
    assert run.succeeded
    assert "资源服：res-staging" in run.output.text
    assert "后端服：game-prod" in run.output.text
    assert "本地模拟" in run.output.text
    assert len(run.session.progress.steps) == 8
    assert all(step.state == StepState.COMPLETED for step in run.session.progress.steps)
    assert any(snapshot.progress.current == 3 for snapshot in snapshots)
    assert run.output.text.count("发布检查会话已结束") == 1
    assert len(run.output.lines) == 4
    assert "PageUp" not in run.output.text
    assert "6/6" not in run.output.text


def test_release_check_failure_keeps_session_progress_and_error(monkeypatch):
    monkeypatch.setattr(verify_release, "sleep", lambda seconds: None)
    run = ScriptTester(verify_release.VerifyReleaseScript).run({"outcome": "failure"})
    assert run.failed
    assert run.exit_code == 1
    assert "发现不兼容资源" in run.error_text
    assert run.session.progress.steps[-1].state == StepState.FAILED
    assert run.output.text.count("发布检查会话已结束") == 1


def test_release_check_target_is_a_snapshot(monkeypatch):
    monkeypatch.setattr(verify_release, "sleep", lambda seconds: None)
    monkeypatch.setattr(context_module.context, "res_server", "res-dev")
    run = ScriptTester(verify_release.VerifyReleaseScript).run()
    monkeypatch.setattr(context_module.context, "res_server", "res-prod")
    run.provide("outcome", "success")
    assert "资源服：res-dev" in run.output.text
    assert "资源服：res-prod" not in run.output.text


def test_release_check_can_stop_during_fixed_progress(monkeypatch):
    async def run() -> None:
        is_started = Event()
        is_released = Event()

        def wait(seconds: float) -> None:
            is_started.set()
            assert is_released.wait(3)

        monkeypatch.setattr(verify_release, "sleep", wait)
        tui = ClakApp(app)
        async with tui.run_test(size=(80, 18)) as pilot:
            tui.state.input_view.set("/verify-release", 80)
            await pilot.press("enter")
            assert tui.state.is_ask_choosing()
            try:
                await pilot.press("enter")
                assert is_started.is_set()
                data = tui.state.progress_data()
                assert data.progress.current == 1
                assert len(data.progress.steps) == 8
                before = tui.state.history_view.display()
                await pilot.pause(0.15)
                assert tui.state.history_view.display() == before
                await pilot.press("x")
                assert tui.state.input_view.input == "x"
                await pilot.press("ctrl+c")
                assert tui.state.runner is not None
            finally:
                is_released.set()
            await pilot.pause()
            history = tui.state.history_view.display()
            assert tui.state.runner is None
            assert tui.state.progress_data() is None
            assert not tui.state.is_progress_animated()
            assert "发布检查通过" not in history
            assert history.count("发布检查会话已结束") == 1

    asyncio.run(run())
