from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from clak.runtime.session import Session


class OutputView:
    """一次脚本运行专属的输出视图。"""

    def __init__(self, prefix: str = "") -> None:
        self.lines: list[str] = []
        self.prefix = prefix
        self._on_change: Callable[[], None] | None = None

    def on_enter(self, session: Session) -> None:
        """脚本进入会话时调用。"""

    def on_exit(self) -> None:
        """脚本安全退出会话时调用。"""

    def set_prefix(self, prefix: str) -> None:
        self.prefix = prefix

    def set_change_callback(self, callback: Callable[[], None] | None) -> None:
        """输出变化后通知展示端；回调在写入线程执行。"""
        self._on_change = callback

    def push(self, text: str) -> None:
        self.lines.extend(f"{self.prefix}{line}" for line in text.splitlines() or [""])
        self.notify_changed()

    def notify_changed(self) -> None:
        """自定义视图修改内容后，主动发送刷新通知。"""
        if self._on_change:
            self._on_change()

    def render_lines(self) -> tuple[str, ...]:
        """返回当前要显示在 HistoryView 中的文本行。"""
        return tuple(self.lines)
