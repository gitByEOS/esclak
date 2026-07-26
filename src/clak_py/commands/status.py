from clak_py.commands.types import (
    SlashAction,
    SlashCommand,
    SlashDispatchResult,
)


def dispatch() -> SlashDispatchResult:
    return SlashDispatchResult(
        action=SlashAction.SHOW_STATUS,
        message="clak-py 脚本聚合",
        status="已显示状态",
    )


COMMAND = SlashCommand(
    "/status",
    ("/context",),
    "软件名与定位",
    handler=dispatch,
)
