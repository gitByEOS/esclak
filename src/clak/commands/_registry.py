from clak.commands import (
    clear,
    quit,
    status,
    version,
)
from collections.abc import Callable

from clak.commands.types import SlashCommand


def builtin_commands(status_provider: Callable[[], str]) -> tuple[SlashCommand, ...]:
    """返回每个 Clak 应用独享的基础命令。"""
    return (
        clear.COMMAND,
        version.COMMAND,
        status.command(status_provider),
        quit.COMMAND,
    )
