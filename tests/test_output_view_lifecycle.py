from clak import Clak, OutputView, Script
from clak.runtime.session import Session
from clak.tui.state import TuiState


def test_tui_mounts_and_detaches_script_output_view():
    events: list[str] = []

    class DeployScript(Script):
        name = "/deploy"
        description = "发布"

        def on_enter(self, session: Session) -> None:
            super().on_enter(session)
            events.append("enter")

        def on_exit(self) -> None:
            events.append("exit")
            super().on_exit()

        def run(self) -> None:
            self.output.push("等待发布")
            self._session.bind_exec_end()
            self._session.exec_list.add(True, lambda: 1, "wait")
            self._session.run()

    app = Clak()
    app.register(DeployScript)
    state = TuiState(app)
    state._start_script("deploy")
    assert events == ["enter"]
    assert len(state.history_view.output_views) == 1

    state._cancel_script()
    assert events == ["enter", "exit"]
    assert state.history_view.output_views == []
    assert "[deploy] 等待发布" in state.history_view.display()
