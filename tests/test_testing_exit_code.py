import pytest

from clak import AskChoice, AskRequest, Script, ScriptError, ScriptTester


@pytest.mark.parametrize("is_interactive", [False, True])
def test_script_tester_preserves_business_exit_code_and_cleanup(is_interactive):
    cleanup = []

    class FailedScript(Script):
        name = "/failed"
        description = "业务失败"

        def run(self) -> None:
            def fail() -> int:
                raise ScriptError("业务拒绝", exit_code=7)

            if is_interactive:
                self.add_step(
                    True,
                    lambda: self.ask_tool(
                        AskRequest("target", "目标", "prod", (AskChoice("生产", "prod"),)),
                        lambda answer: None,
                    ),
                    "选择目标",
                )
            self.add_step(True, fail, "执行检查")
            self.run_steps()

        def on_exit(self) -> None:
            cleanup.append("清理")
            super().on_exit()

    run = ScriptTester(FailedScript).run()
    if is_interactive:
        assert run.is_awaiting("target")
        run.provide("target", "prod")
    assert run.failed
    assert run.exit_code == 7
    assert run.error_text == "业务拒绝"
    assert cleanup == ["清理"]
