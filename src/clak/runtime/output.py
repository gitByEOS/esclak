from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clak.runtime.session import Session


class OutputView:
    """一次脚本运行专属的输出视图。"""

    def __init__(self, prefix: str = "") -> None:
        self.lines: list[str] = []
        self.prefix = prefix

    def on_enter(self, session: Session) -> None:
        """视图挂载到 HistoryView 后调用。"""

    def on_exit(self) -> None:
        """视图从 HistoryView 脱离前调用。"""

    def set_prefix(self, prefix: str) -> None:
        self.prefix = prefix

    def push(self, text: str) -> None:
        self.lines.extend(f"{self.prefix}{line}" for line in text.splitlines() or [""])

    def render_lines(self) -> tuple[str, ...]:
        """返回当前要显示在 HistoryView 中的文本行。"""
        return tuple(self.lines)
