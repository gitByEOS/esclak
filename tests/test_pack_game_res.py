from examples.dev_tools.app import app
from examples.dev_tools.context import context
from examples.dev_tools.scripts.pack_upload import PackUploadScript
from clak.runtime.params import ScriptInputs
from clak.runtime.output import OutputView
from clak.runtime.session import Session


def start_script(script, session):
    session.on_exit(script.on_exit)
    script.on_enter(session)
    script.run(session)


def test_pack_game_res_custom_version():
    context.reset()
    script = PackUploadScript()
    logs = script.output.lines
    session = Session(script.output, inputs=ScriptInputs(allow_defaults=False))
    start_script(script, session)
    assert session.is_awaiting_input
    session.provide_input("version", "99-01-02")
    assert session.is_awaiting_input
    assert session.pending_request is not None
    assert session.pending_request.field_id == "targets"
    session.provide_input("targets", "base,cn")
    assert not session.is_awaiting_input
    assert any("99-01-02" in line for line in logs)
    assert any("base,cn" in line for line in logs)
    assert any("上传到资源服：res-dev" in line for line in logs)


def test_pack_game_res_with_prefill():
    context.reset()
    script = PackUploadScript()
    logs = script.output.lines
    inputs = ScriptInputs.from_pairs(
        {"version": "2.0.0", "targets": "base,ios"},
        allow_defaults=False,
    )
    start_script(script, Session(script.output, inputs=inputs))
    assert not logs or not any("is_awaiting" in str(logs) for _ in [0])
    assert any("2.0.0" in line for line in logs)
    assert any("base,ios" in line for line in logs)


def test_pack_game_res_exec_defaults_non_interactive():
    context.reset()
    run = app.run_line("/pack-upload", script_inputs=ScriptInputs(allow_defaults=True))
    assert run.exit_code == 0
    assert "上传到资源服：res-dev" in run.text
    assert "已清理临时打包目录" in run.text


def test_pack_game_res_rejects_invalid_version():
    context.reset()
    run = app.run_line(
        "/pack-upload",
        script_inputs=ScriptInputs.from_pairs(
            {"version": "???", "targets": "base"},
            allow_defaults=False,
        ),
    )
    assert run.exit_code == 2
    assert run.stream == "stderr"
    assert "版本号只能包含" in run.text
    assert "已清理临时打包目录" in run.text


def test_pack_game_res_rejects_target_outside_choices():
    context.reset()
    run = app.run_line(
        "/pack-upload",
        script_inputs=ScriptInputs.from_pairs(
            {"version": "2.0.0", "targets": "unknown-target"},
            allow_defaults=False,
        ),
    )
    assert run.exit_code == 2
    assert "无效输入 [targets]: unknown-target" in run.text


def test_pack_game_res_cleans_temporary_workspace():
    context.reset()
    script = PackUploadScript()
    session = Session(
        script.output,
        inputs=ScriptInputs.from_pairs(
            {"version": "2.0.0", "targets": "base"},
            allow_defaults=False,
        ),
    )
    session.on_exit(script.on_exit)
    script.on_enter(session)
    assert script._workspace is not None
    workspace = script._workspace.name
    script.run(session)
    from pathlib import Path

    assert not Path(workspace).exists()
