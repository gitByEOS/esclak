from clak_py.commands import (
    clear,
    quit,
    status,
    version,
)
from clak_py.commands.types import ScriptEntry, SlashCommand, SlashEntry
from clak_py.runtime.session import ScriptSession
from clak_py.scripts._registry import all_scripts

_BUILTINS: tuple[SlashCommand, ...] = (
    clear.COMMAND,
    version.COMMAND,
    status.COMMAND,
    quit.COMMAND,
)

COMMANDS: tuple[SlashEntry, ...] = _BUILTINS + all_scripts()


def command_for_token(token: str) -> SlashEntry | None:
    needle = token.lower()
    for cmd in COMMANDS:
        if needle in cmd.all_names():
            return cmd
    return None


def script_command(script_id: str) -> ScriptEntry | None:
    for cmd in all_scripts():
        if cmd.script_id == script_id:
            return cmd
    return None


def run_script(session: ScriptSession, script_id: str) -> None:
    cmd = script_command(script_id)
    if not cmd:
        raise ValueError(f"未知脚本: {script_id}")
    cmd.script_run(session)
