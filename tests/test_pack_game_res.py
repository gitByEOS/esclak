from examples.dev_tools.app import app
from examples.dev_tools.context import context
from examples.dev_tools.scripts.pack_upload import PackUploadScript
from clak.runtime.params import ScriptInputs
from clak.testing import ScriptTester


def test_pack_game_res_custom_version():
    context.reset()
    run = ScriptTester(PackUploadScript).run()
    assert run.is_awaiting("version")
    run.provide("version", "99-01-02")
    assert run.is_awaiting("targets")
    run.provide("targets", "base,cn")
    assert run.succeeded
    assert run.output.contains("99-01-02")
    assert run.output.contains("base,cn")
    assert run.output.contains("上传到资源服：res-dev")


def test_pack_game_res_with_prefill():
    context.reset()
    run = ScriptTester(PackUploadScript).run(inputs={"version": "2.0.0", "targets": "base,ios"})
    assert run.succeeded
    assert run.output.contains("2.0.0")
    assert run.output.contains("base,ios")


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
    run = ScriptTester(PackUploadScript).run(inputs={"version": "2.0.0", "targets": "base"})
    assert run.succeeded
    assert run.script._workspace is None
    assert run.output.contains("已清理临时打包目录")
