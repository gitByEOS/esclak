"""Slash 命令：实现见 commands/*，引擎在此。"""

from __future__ import annotations

from clak.commands._registry import COMMANDS, command_for_token
from clak.commands.types import (
    ScriptEntry,
    SlashAction,
    SlashDispatchResult,
    SlashEntry,
    SlashMatch,
    SlashTokenKind,
)

__all__ = [
    "SlashAction",
    "SlashDispatchResult",
    "SlashEngine",
    "SlashEntry",
    "SlashMatch",
    "SlashTokenKind",
]


class SlashEngine:
    def filter(self, input_text: str) -> list[SlashMatch]:
        token = input_text.split()[0] if input_text.split() else input_text
        if not token.startswith("/"):
            return []
        needle = token.lower()
        matches: list[SlashMatch] = []
        for cmd in COMMANDS:
            names = cmd.all_names()
            if any(name.startswith(needle) or needle.startswith(name) for name in names):
                matches.append(SlashMatch(cmd.name, cmd.description))
        if not matches and input_text.startswith("/"):
            for cmd in COMMANDS:
                matches.append(SlashMatch(cmd.name, cmd.description))
        return matches

    def token_kind(self, token: str) -> SlashTokenKind:
        if not token.startswith("/"):
            return SlashTokenKind.NOT_SLASH
        if command_for_token(token):
            return SlashTokenKind.AVAILABLE
        if token == "/":
            return SlashTokenKind.INCOMPLETE
        return SlashTokenKind.UNKNOWN

    def tab_completion(self, input_text: str, selected: int) -> str | None:
        matches = self.filter(input_text)
        if not matches or selected >= len(matches):
            return None
        return matches[selected].name

    def dispatch(self, line: str) -> SlashDispatchResult:
        token = line.split()[0].lower() if line.split() else line.lower()
        cmd = command_for_token(token)
        if not cmd:
            return SlashDispatchResult(
                action=SlashAction.UNKNOWN,
                command=token,
                message=f"未知命令 {token}",
                status="unknown slash",
            )
        if isinstance(cmd, ScriptEntry):
            return SlashDispatchResult(
                action=SlashAction.RUN_SCRIPT,
                command=cmd.script_id,
                status=cmd.script_id,
            )
        return cmd.handler()
