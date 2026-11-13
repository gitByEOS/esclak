from queue import Queue
from threading import Thread

import pytest

from clak.tui.runner import RunState, RunUpdate, ScriptRunner
from clak.tui.state import TuiState


class TuiDriver:
    """用真实工作线程驱动纯界面状态，避免同步执行回退。"""

    def __init__(self, app) -> None:
        self.state = TuiState(app)
        self._updates: Queue[tuple[ScriptRunner, RunUpdate]] = Queue()
        self._runs: list[tuple[ScriptRunner, Thread]] = []

    def start(self, script_id: str) -> None:
        self.state._start_script(script_id)
        self.wait()

    def wait(self) -> None:
        runner = self.state.take_pending_runner()
        if runner is not None:
            thread = Thread(
                target=runner.run,
                args=(lambda update: self._updates.put((runner, update)),),
                daemon=True,
            )
            self._runs.append((runner, thread))
            thread.start()
        while self.state.runner is not None:
            runner, update = self._updates.get(timeout=3)
            self.state.apply_run_update(runner, update)
            if update.state in (RunState.AWAITING_INPUT, RunState.PAUSED, RunState.FINISHED):
                return

    def close(self) -> None:
        for runner, thread in self._runs:
            runner.cancel()
            thread.join(timeout=3)
            assert not thread.is_alive(), "脚本线程未完成清理"


@pytest.fixture
def tui_driver():
    drivers: list[TuiDriver] = []

    def create(app) -> TuiDriver:
        driver = TuiDriver(app)
        drivers.append(driver)
        return driver

    yield create
    for driver in drivers:
        driver.close()
