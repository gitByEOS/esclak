from clak import (
    AskAnswer,
    AskChoice,
    AskMode,
    AskRequest,
    Clak,
    HeadlessRun,
    OutputView,
    Script,
    ScriptError,
    ScriptInputs,
    Session,
)
from clak.commands.types import SlashAction, SlashCommand, SlashDispatchResult
from clak.tui.state import TuiState


def test_status_uses_application_provider():
    app = Clak(status=lambda: "发布工具 · staging")
    run = app.run_line("/status")
    assert run.exit_code == 0
    assert run.text == "发布工具 · staging"


def test_footer_view_receives_tui_state():
    received = []

    def render_footer(footer):
        received.append(footer)
        return f"{footer.branch} · {footer.primary}"

    state = TuiState(Clak(footer_view=render_footer))
    assert state.footer_content().endswith("· input")
    assert received[-1].hint == state.footer_line


def test_external_commands_and_scripts_are_instance_local():
    app = Clak()

    def health() -> SlashDispatchResult:
        return SlashDispatchResult(SlashAction.SHOW_STATUS, message="ok")

    app.register(SlashCommand("/health", (), "检查服务", health))
    assert app.run_line("/health").text == "ok"
    assert Clak().run_line("/health").exit_code == 2


def test_session_writes_to_its_output_view():
    output = OutputView()
    session = Session(output)
    output.push("发布完成")
    assert output.lines == ["发布完成"]


def test_script_output_has_a_default_script_name_prefix():
    class DeployScript(Script):
        name = "/deploy"
        description = "发布"

    script = DeployScript()
    script.output.push("开始发布\n发布完成")
    assert script.output.lines == ["[deploy] 开始发布", "[deploy] 发布完成"]


def test_application_registers_script_resource():
    app = Clak()

    class DeployScript(Script):
        name = "/deploy"
        description = "发布"

        def run(self, session: Session) -> None:
            self.output.push("完成")

    app.register(DeployScript)
    assert app.run_line("/deploy").text == "[deploy] 完成"


def test_script_creates_an_independent_output_view_for_each_run():
    scripts: list[Script] = []

    class DeployScript(Script):
        name = "/deploy"
        description = "发布"

        def on_enter(self, session: Session) -> None:
            scripts.append(self)
            self.output.push("进入发布")

        def run(self, session: Session) -> None:
            session.bind_step_end()
            session.step_list.add(True, lambda: self.output.push("发布完成") or 0, "deploy")
            session.run()

    app = Clak()
    app.register(DeployScript)
    assert app.run_line("/deploy").text == "[deploy] 进入发布\n[deploy] 发布完成"
    app.run_line("/deploy")
    assert len(scripts) == 2
    assert scripts[0] is not scripts[1]
    assert scripts[0].output is not scripts[1].output


def test_common_script_types_are_available_from_public_api():
    assert AskAnswer and AskChoice and AskMode and AskRequest
    assert HeadlessRun and ScriptError and ScriptInputs and Session


def test_headless_cleans_up_when_on_enter_fails():
    events: list[str] = []

    class BrokenScript(Script):
        name = "/broken"
        description = "初始化失败"

        def on_enter(self, session: Session) -> None:
            events.append("enter")
            raise ScriptError("无法初始化")

        def on_exit(self) -> None:
            events.append("exit")

    app = Clak()
    app.register(BrokenScript)
    run = app.run_line("/broken")
    assert run.exit_code == 1
    assert run.text == "无法初始化"
    assert events == ["enter", "exit"]
