"""clak 的嵌入式应用入口。"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from clak.commands._registry import builtin_commands
from clak.commands.types import (
    Script,
    ScriptEntry,
    SlashCommand,
    SlashEntry,
    RegisterEntry,
)
from clak.runtime.slash import SlashEngine
from clak.runtime.params import ScriptInputs
from clak.runtime.session import Session

StatusProvider = str | Callable[[], str]


@dataclass(frozen=True)
class FooterViewData:
    """底栏渲染器可用的只读运行上下文。"""

    branch: str
    uptime_seconds: int
    primary: str
    overlay: str
    hint: str


FooterView = Callable[[FooterViewData], str]


class Clak:
    """可嵌入到任意 Python 项目的 clak 应用。"""

    def __init__(
        self,
        *,
        status: StatusProvider = "clak 脚本运行时",
        footer_view: FooterView | None = None,
    ) -> None:
        self._status = _status_provider(status)
        self.footer_view = footer_view or _default_footer_view
        self._commands: list[SlashEntry] = list(builtin_commands(self._status))

    @property
    def commands(self) -> tuple[SlashEntry, ...]:
        """当前应用的全部 slash 入口。"""
        return tuple(self._commands)

    @property
    def slash_engine(self) -> SlashEngine:
        return SlashEngine(self.commands)

    def register(self, *entries: RegisterEntry) -> None:
        """注册脚本或纯 slash 命令。"""
        for entry in entries:
            self._add_entry(_registry_entry(entry))

    def create_script(self, script_id: str) -> Script | None:
        """按脚本标识创建一次运行专属的脚本实例。"""
        for entry in self._commands:
            if isinstance(entry, ScriptEntry) and entry.script_id == script_id:
                return entry.create()
        return None

    def run_line(
        self,
        line: str,
        *,
        script_inputs: ScriptInputs | None = None,
    ):
        """在无头模式执行一行输入。"""
        from clak.runtime.headless import run_line

        return run_line(line, script_inputs=script_inputs, app=self)

    def run_tui(self) -> None:
        """打开此应用自己的交互 TUI。"""
        from clak.tui.app import run_tui

        run_tui(self)

    def run_cli(
        self,
        argv: Sequence[str] | None = None,
        *,
        prog: str | None = None,
    ) -> None:
        """运行绑定到此应用的 ``tui``/``exec`` 命令行入口。"""
        from clak.cli import run_app_cli

        run_app_cli(self, argv=argv, prog=prog)

    def _add_entry(self, entry: SlashEntry) -> None:
        _validate_names(entry)
        existing = {name.lower() for command in self._commands for name in command.all_names()}
        duplicate = next((name for name in entry.all_names() if name.lower() in existing), None)
        if duplicate:
            raise ValueError(f"slash 命令已注册: {duplicate}")
        self._commands.append(entry)


def _status_provider(status: StatusProvider) -> Callable[[], str]:
    if isinstance(status, str):
        return lambda: status
    return status


def _default_footer_view(footer: FooterViewData) -> str:
    return footer.hint


def _registry_entry(entry: RegisterEntry) -> SlashEntry:
    if isinstance(entry, SlashCommand):
        return entry
    if isinstance(entry, type) and issubclass(entry, Script):
        return ScriptEntry(entry)
    raise TypeError("app.register 只接受 SlashCommand 或 Script 子类")


def _validate_names(entry: SlashEntry) -> None:
    names = entry.all_names()
    if not entry.name.startswith("/") or any(not name.startswith("/") for name in names):
        raise ValueError("slash 命令及别名必须以 / 开头")
    if any(len(name) == 1 for name in names):
        raise ValueError("slash 命令名不能为空")
