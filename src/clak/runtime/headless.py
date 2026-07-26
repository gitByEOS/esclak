from __future__ import annotations

import sys
from dataclasses import dataclass

from clak.commands._registry import run_script
from clak.runtime.params import MissingScriptInputError, ScriptInputs
from clak.runtime.session import ScriptSession
from clak.runtime.slash import (
    SlashAction,
    SlashEngine,
)


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
) -> HeadlessRun:
    stripped = line.strip()
    if not stripped:
        raise HeadlessError("输入不能为空", code=2)
    if stripped.startswith("/"):
        return _run_slash(stripped, script_inputs)
    return _run_prompt(stripped)


def _run_slash(
    line: str,
    script_inputs: ScriptInputs | None,
) -> HeadlessRun:
    engine = SlashEngine()
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
            return _run_script_headless(result.command, script_inputs)
        case SlashAction.SHOW_STATUS | SlashAction.NEW_SESSION | SlashAction.NONE:
            if result.message:
                return HeadlessRun(result.message, 0)
            if result.status:
                return HeadlessRun(result.status, 0)
            return HeadlessRun("", 0)


def _run_prompt(prompt: str) -> HeadlessRun:
    body = "请使用 slash 命令，例如 /pack-game-res"
    return HeadlessRun(body, 0)


def _run_script_headless(
    script_id: str,
    script_inputs: ScriptInputs | None,
) -> HeadlessRun:
    lines: list[str] = []
    inputs = script_inputs or ScriptInputs(allow_defaults=True)
    session = ScriptSession(lines.append, inputs=inputs, fail_on_missing=not inputs.allow_defaults)
    try:
        run_script(session, script_id)
    except ValueError as error:
        return HeadlessRun(str(error), 2, stream="stderr")
    except MissingScriptInputError as error:
        return HeadlessRun(str(error), 2, stream="stderr")
    if session.is_awaiting_input:
        req = session.pending_request
        field = req.field_id if req else "?"
        return HeadlessRun(
            f"脚本等待输入 [{field}]，请用 --set {field}=... 补齐",
            2,
            stream="stderr",
        )
    return HeadlessRun("\n".join(lines), 0)


def emit(run: HeadlessRun) -> int:
    if run.text:
        if run.stream == "stderr":
            print(run.text, file=sys.stderr)
        else:
            print(run.text)
    return run.exit_code
