from clak.runtime.params import ScriptInputs
from clak.runtime.session import ScriptSession
from clak.scripts.select_server import SERVER_DEFAULT, run as run_select_server


def test_select_server_prefill():
    logs: list[str] = []
    inputs = ScriptInputs.from_pairs({"server": "staging"}, allow_defaults=False)
    run_select_server(ScriptSession(logs.append, inputs=inputs))
    assert any("staging" in line for line in logs)
    assert any("完成" in line for line in logs)


def test_select_server_gate_and_provide():
    logs: list[str] = []
    session = ScriptSession(logs.append, inputs=ScriptInputs(allow_defaults=False))
    run_select_server(session)
    assert session.is_awaiting_input
    assert session.pending_request
    assert session.pending_request.field_id == "server"
    session.provide_input("server", "prod")
    assert not session.is_awaiting_input
    assert any("prod" in line for line in logs)


def test_select_server_exec_default():
    from clak.runtime.headless import run_line

    run = run_line("/select-server", script_inputs=ScriptInputs(allow_defaults=True))
    assert run.exit_code == 0
    assert SERVER_DEFAULT in run.text
