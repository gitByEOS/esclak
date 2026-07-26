from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto

from clak.runtime.session import ScriptSession


class SlashAction(Enum):
    NONE = auto()
    NEW_SESSION = auto()
    SHOW_STATUS = auto()
    RUN_SCRIPT = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class SlashMatch:
    name: str
    description: str


@dataclass
class SlashDispatchResult:
    action: SlashAction
    message: str | None = None
    status: str | None = None
    command: str | None = None


class SlashTokenKind(Enum):
    NOT_SLASH = auto()
    INCOMPLETE = auto()
    AVAILABLE = auto()
    UNKNOWN = auto()


SlashHandler = Callable[[], SlashDispatchResult]
ScriptRunner = Callable[[ScriptSession], None]


@dataclass(frozen=True)
class SlashCommand:
    """纯 slash 命令：只分发，不跑脚本。"""

    name: str
    aliases: tuple[str, ...]
    description: str
    handler: SlashHandler

    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class ScriptEntry:
    """脚本入口：slash 名 + 脚本 runner。"""

    name: str
    aliases: tuple[str, ...]
    description: str
    script_id: str
    script_run: ScriptRunner

    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


SlashEntry = SlashCommand | ScriptEntry
