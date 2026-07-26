from clak_py.commands.types import (
    SlashAction,
    SlashCommand,
    SlashDispatchResult,
)


def dispatch() -> SlashDispatchResult:
    return SlashDispatchResult(action=SlashAction.QUIT, status="再见")


COMMAND = SlashCommand(
    "/quit",
    ("/exit",),
    "退出 TUI",
    handler=dispatch,
)
