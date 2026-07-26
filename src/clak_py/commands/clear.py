from clak_py.commands.types import (
    SlashAction,
    SlashCommand,
    SlashDispatchResult,
)


def dispatch() -> SlashDispatchResult:
    return SlashDispatchResult(
        action=SlashAction.NEW_SESSION,
        message="已清空 history",
        status="Session cleared",
    )


COMMAND = SlashCommand(
    "/clear",
    ("/new",),
    "清空 history",
    handler=dispatch,
)
