from clak_py import __version__
from clak_py.commands.types import (
    SlashAction,
    SlashCommand,
    SlashDispatchResult,
)


def dispatch() -> SlashDispatchResult:
    return SlashDispatchResult(
        action=SlashAction.SHOW_STATUS,
        message=f"clak-py {__version__}",
        status="已显示版本",
    )


COMMAND = SlashCommand(
    "/version",
    (),
    "显示工具版本",
    handler=dispatch,
)
