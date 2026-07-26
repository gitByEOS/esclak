import subprocess
import sys

from clak_py.runtime.headless import emit, run_line


def test_exec_version():
    run = run_line("/version")
    assert run.exit_code == 0
    assert "0.1.0" in run.text


def test_exec_version_cli():
    proc = subprocess.run(
        [sys.executable, "-m", "clak_py", "exec", "/version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0
    assert "0.1.0" in proc.stdout


def test_exec_unknown():
    run = run_line("/nope")
    assert run.exit_code == 2
    assert run.stream == "stderr"
