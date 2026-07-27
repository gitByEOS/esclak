from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from clak.runtime.ask import AskAnswer, AskRequest
from clak.runtime.exec_list import CanDo, StepFunc
from clak.runtime.output import OutputView
from clak.runtime.session import Session


class SlashAction(Enum):
    NONE = auto()
    NEW_SESSION = auto()
    SHOW_STATUS = auto()
    RUN_SCRIPT = auto()
    QUIT = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class SlashMatch:
    """命令菜单中的匹配项。"""

    name: str
    description: str
    matched_indices: tuple[int, ...] = ()
    display_name: str | None = None

    @property
    def label(self) -> str:
        return self.display_name or self.name


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


@dataclass(frozen=True)
class SlashCommand:
    """纯 slash 命令：只分发，不跑脚本。"""

    name: str
    aliases: tuple[str, ...]
    description: str
    handler: SlashHandler

    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


class Script:
    """业务脚本基类，每次执行都会创建一个新实例。"""

    name = ""
    description = ""
    aliases: tuple[str, ...] = ()
    output_view = OutputView

    def __init__(self) -> None:
        self.output = self.output_view()
        self.output.set_prefix(f"[{self.name.removeprefix('/')}] ")
        self._session: Session | None = None

    def on_enter(self, session: Session) -> None:
        self._session = session
        self.output.on_enter(session)

    def on_exit(self) -> None:
        self._session = None
        self.output.on_exit()

    def run(self) -> None:
        raise NotImplementedError

    def add_step(
        self,
        can_do: CanDo,
        run: StepFunc,
        name: str = "empty",
        *args: Any,
    ) -> None:
        """向本次运行的执行队列追加一步，语义同 ExecList.add。"""
        self._session.exec_list.add(can_do, run, name, *args)

    def ask_tool(
        self,
        request: AskRequest,
        on_answer: Callable[[AskAnswer], None],
    ) -> int:
        """请求用户输入，语义同 Session.ask_step。"""
        return self._session.ask_step(request, on_answer)

    def run_steps(self) -> None:
        """绑定完成回调并启动执行队列。"""
        session = self._session
        session.bind_exec_end()
        session.run()


@dataclass(frozen=True)
class ScriptEntry:
    """已注册脚本的元数据与实例工厂。"""

    script_type: type[Script]

    @property
    def name(self) -> str:
        return self.script_type.name

    @property
    def description(self) -> str:
        return self.script_type.description

    @property
    def aliases(self) -> tuple[str, ...]:
        return self.script_type.aliases

    @property
    def script_id(self) -> str:
        return self.name.removeprefix("/")

    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)

    def create(self) -> Script:
        return self.script_type()


SlashEntry = SlashCommand | ScriptEntry
RegisterEntry = SlashCommand | type[Script]
