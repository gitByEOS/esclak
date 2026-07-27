from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TYPE_CHECKING

from clak.runtime.params import MissingScriptInputError, ScriptInputs
from clak.runtime.errors import ScriptError
from clak.runtime.session import Session
from clak.runtime.slash import (
    SlashAction,
    SlashEngine,
)

if TYPE_CHECKING:
    from clak.application import Clak


class HeadlessError(Exception):
    def __init__(self, message: str, code: int = 2) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class HeadlessRun:
    text: str
    exit_code: int = 0
    stream: str = "stdout"


def run_line(
    line: str,
    *,
    script_inputs: ScriptInputs | None = None,
    app: Clak | None = None,
) -> HeadlessRun:
    if app is None:
        from clak.application import Clak

        app = Clak()
    stripped = line.strip()
    if not stripped:
        raise HeadlessError("输入不能为空", code=2)
    if stripped.startswith("/"):
        return _run_slash(stripped, script_inputs, app)
    return _run_prompt(stripped)


def _run_slash(
    line: str,
    script_inputs: ScriptInputs | None,
    app: Clak,
) -> HeadlessRun:
    engine = app.slash_engine
    result = engine.dispatch(line)

    match result.action:
        case SlashAction.QUIT:
            return HeadlessRun("", 0)
        case SlashAction.UNKNOWN:
            msg = result.message or f"未知命令 {result.command}"
            return HeadlessRun(msg, 2, stream="stderr")
        case SlashAction.RUN_SCRIPT:
            if not result.command:
                return HeadlessRun("缺少脚本名", 2, stream="stderr")
            return _run_script_headless(result.command, script_inputs, app)
        case SlashAction.SHOW_STATUS | SlashAction.NEW_SESSION | SlashAction.NONE:
            if result.message:
                return HeadlessRun(result.message, 0)
            if result.status:
                return HeadlessRun(result.status, 0)
            return HeadlessRun("", 0)


def _run_prompt(prompt: str) -> HeadlessRun:
    body = "请使用 slash 命令，例如 /version"
    return HeadlessRun(body, 0)


def _run_script_headless(
    script_id: str,
    script_inputs: ScriptInputs | None,
    app: Clak,
) -> HeadlessRun:
    script = app.create_script(script_id)
    if not script:
        return HeadlessRun(f"未知脚本: {script_id}", 2, stream="stderr")
    output = script.output
    inputs = script_inputs or ScriptInputs(allow_defaults=True)
    session = Session(output, inputs=inputs, fail_on_missing=not inputs.allow_defaults)
    session.on_exit(script.on_exit)
    try:
        script.on_enter(session)
        script.run()
    except ScriptError as error:
        session.cancel()
        return _failed_script_run(output.render_lines(), str(error), error.exit_code)
    except (MissingScriptInputError, ValueError) as error:
        session.cancel()
        return _failed_script_run(output.render_lines(), str(error), 2)
    if session.is_awaiting_input:
        req = session.pending_request
        field = req.field_id if req else "?"
        session.cancel()
        return _failed_script_run(
            output.render_lines(),
            f"脚本等待输入 [{field}]，请用 --set {field}=... 补齐",
            2,
        )
    return HeadlessRun("\n".join(output.render_lines()), 0)


def _failed_script_run(lines: tuple[str, ...], message: str, code: int) -> HeadlessRun:
    text = "\n".join((*lines, message))
    return HeadlessRun(text, code, stream="stderr")


def emit(run: HeadlessRun) -> int:
    if run.text:
        if run.stream == "stderr":
            print(run.text, file=sys.stderr)
        else:
            print(run.text)
    return run.exit_code
