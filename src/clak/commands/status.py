from collections.abc import Callable

from clak.commands.types import (
    SlashAction,
    SlashCommand,
    SlashDispatchResult,
)


def command(status: Callable[[], str]) -> SlashCommand:
    """创建绑定到应用状态提供器的 /status 命令。"""

    def dispatch() -> SlashDispatchResult:
        return SlashDispatchResult(
            action=SlashAction.SHOW_STATUS,
            message=status(),
            status="已显示状态",
        )

    return SlashCommand(
        "/status",
        ("/context",),
        "显示应用状态",
        handler=dispatch,
    )
