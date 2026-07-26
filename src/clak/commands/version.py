from clak import __version__
from clak.commands.types import (
    SlashAction,
    SlashCommand,
    SlashDispatchResult,
)


def dispatch() -> SlashDispatchResult:
    return SlashDispatchResult(
        action=SlashAction.SHOW_STATUS,
        message=f"clak {__version__}",
        status="已显示版本",
    )


COMMAND = SlashCommand(
    "/version",
    (),
    "显示工具版本",
    handler=dispatch,
)
