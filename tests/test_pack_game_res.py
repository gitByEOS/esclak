from clak_py.scripts.pack_game_res import default_pack_version, run as run_pack_game_res
from clak_py.runtime.params import ScriptInputs
from clak_py.runtime.session import ScriptSession


def test_pack_game_res_custom_version():
    logs: list[str] = []
    session = ScriptSession(logs.append, inputs=ScriptInputs(allow_defaults=False))
    run_pack_game_res(session)
    assert session.is_awaiting_input
    session.provide_input("version", "99-01-02")
    assert session.is_awaiting_input
    assert session.pending_request is not None
    assert session.pending_request.field_id == "targets"
    session.provide_input("targets", "base,cn")
    assert not session.is_awaiting_input
    assert any("99-01-02" in line for line in logs)
    assert any("base,cn" in line for line in logs)
    assert any("全部结束" in line for line in logs)


def test_pack_game_res_with_prefill():
    logs: list[str] = []
    inputs = ScriptInputs.from_pairs(
        {"version": "2.0.0", "targets": "base,ios"},
        allow_defaults=False,
    )
    run_pack_game_res(ScriptSession(logs.append, inputs=inputs))
    assert not logs or not any("is_awaiting" in str(logs) for _ in [0])
    assert any("2.0.0" in line for line in logs)
    assert any("base,ios" in line for line in logs)


def test_pack_game_res_exec_defaults_non_interactive():
    from clak_py.runtime.headless import run_line

    run = run_line("/pack-game-res", script_inputs=ScriptInputs(allow_defaults=True))
    assert run.exit_code == 0
    assert "全部结束" in run.text
