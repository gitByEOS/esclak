from __future__ import annotations

import subprocess
import sys

import pytest

from clak import ScriptInputs
from examples.dev_tools.app import app


def test_project_cli_exec_uses_registered_application(capsys):
    with pytest.raises(SystemExit) as raised:
        app.run_cli(
            [
                "exec",
                "/pack-upload",
                "--set",
                "version=1.2.3",
                "--set",
                "targets=base,ios",
            ],
            prog="dev_tools",
        )
    assert raised.value.code == 0
    assert "上传完成" in capsys.readouterr().out


def test_project_module_cli_exec_works_in_subprocess():
    proc = subprocess.run(
        [
            sys.executable,
            "-m",
            "examples.dev_tools",
            "exec",
            "/verify-release",
            "--set",
            "outcome=success",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "发布检查通过" in proc.stdout


def test_release_check_returns_script_failure_code():
    run = app.run_line(
        "/verify-release",
        script_inputs=ScriptInputs.from_pairs(
            {"outcome": "failure"},
            allow_defaults=False,
        ),
    )
    assert run.exit_code == 1
    assert run.stream == "stderr"
    assert "发现不兼容资源" in run.text


def test_release_check_failure_is_shown_in_tui():
    from clak.tui.event import TuiEvent, TuiKey
    from clak.tui.state import TuiState

    state = TuiState(app)
    state._start_script("verify-release")
    state.handle_event(TuiEvent(key=TuiKey("char", char="2")))
    state.after_present()
    assert state.session is None
    assert "发布检查失败" in state.history_view.display()
