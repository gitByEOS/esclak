from clak.runtime.params import ScriptInputs
from clak.runtime.session import Session
from clak.tui.state import TuiState
from examples.dev_tools.app import app
from examples.dev_tools.context import context
from examples.dev_tools.scripts.select_game_server import SelectGameServerScript
from examples.dev_tools.scripts.select_res_server import SelectResServerScript


def test_select_server_prefill():
    context.reset()
    script = SelectResServerScript()
    logs = script.output.lines
    inputs = ScriptInputs.from_pairs({"res_server": "res-staging"}, allow_defaults=False)
    script.run(Session(script.output, inputs=inputs))
    assert context.res_server == "res-staging"
    assert any("res-staging" in line for line in logs)


def test_select_server_gate_and_provide():
    context.reset()
    script = SelectResServerScript()
    logs = script.output.lines
    session = Session(script.output, inputs=ScriptInputs(allow_defaults=False))
    script.run(session)
    assert session.is_awaiting_input
    assert session.pending_request
    assert session.pending_request.field_id == "res_server"
    session.provide_input("res_server", "res-prod")
    assert not session.is_awaiting_input
    assert any("res-prod" in line for line in logs)


def test_select_server_updates_status_and_footer():
    context.reset()
    run = app.run_line("/select-res-server", script_inputs=ScriptInputs.from_pairs({"res_server": "res-prod"}, allow_defaults=False))
    assert run.exit_code == 0
    assert app.run_line("/status").text == "当前资源服：res-prod"
    game = SelectGameServerScript()
    game.run(Session(game.output, inputs=ScriptInputs.from_pairs({"game_server": "game-prod"}, allow_defaults=False)))
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
