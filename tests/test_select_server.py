from clak.runtime.params import ScriptInputs
from clak.testing import ScriptTester
from clak.tui.state import TuiState
from examples.dev_tools.app import app
from examples.dev_tools.context import context
from examples.dev_tools.scripts.select_game_server import SelectGameServerScript
from examples.dev_tools.scripts.select_res_server import SelectResServerScript


def test_select_server_prefill():
    context.reset()
    run = ScriptTester(SelectResServerScript).run(inputs={"res_server": "res-staging"})
    assert run.succeeded
    assert context.res_server == "res-staging"
    assert run.output.contains("res-staging")


def test_select_server_gate_and_provide():
    context.reset()
    run = ScriptTester(SelectResServerScript).run()
    assert run.is_awaiting("res_server")
    run.provide("res_server", "res-prod")
    assert run.succeeded
    assert run.output.contains("res-prod")


def test_select_server_updates_status_and_footer():
    context.reset()
    run = app.run_line("/select-res-server", script_inputs=ScriptInputs.from_pairs({"res_server": "res-prod"}, allow_defaults=False))
    assert run.exit_code == 0
    assert app.run_line("/status").text == "当前资源服：res-prod"
    game = ScriptTester(SelectGameServerScript).run(inputs={"game_server": "game-prod"})
    assert game.succeeded
    assert TuiState(app).footer_content().endswith("当前后端服：game-prod")


def test_select_server_rejects_value_outside_choices():
    context.reset()
    run = app.run_line(
        "/select-res-server",
        script_inputs=ScriptInputs.from_pairs(
            {"res_server": "totally-not-a-server"},
            allow_defaults=False,
        ),
    )
    assert run.exit_code == 2
    assert run.stream == "stderr"
    assert "无效输入 [res_server]" in run.text
    assert context.res_server == "res-dev"
