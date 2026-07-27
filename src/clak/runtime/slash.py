"""Slash 命令：实现见 commands/*，引擎在此。"""

from __future__ import annotations

from collections.abc import Iterable
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
    def __init__(self, commands: Iterable[SlashEntry]) -> None:
        self._commands = tuple(commands)

    def filter(self, input_text: str) -> list[SlashMatch]:
        token = input_text.split()[0] if input_text.split() else input_text
        if not token:
            return []
        query = token.removeprefix("/")
        matches: list[tuple[tuple[int, int], int, SlashMatch]] = []
        for command_index, cmd in enumerate(self._commands):
            candidates: list[tuple[tuple[int, int], int, SlashMatch]] = []
            for name_index, name in enumerate(cmd.all_names()):
                indices = _subsequence_indices(query, name.removeprefix("/"))
                if indices is None:
                    continue
                offset = len(name) - len(name.removeprefix("/"))
                candidates.append(
                    (
                        _match_score(indices),
                        name_index,
                        SlashMatch(
                            cmd.name,
                            cmd.description,
                            matched_indices=tuple(index + offset for index in indices),
                            display_name=name,
                        ),
                    )
                )
            if candidates:
                score, _, match = min(candidates, key=lambda candidate: candidate[:2])
                matches.append((score, command_index, match))
        matches.sort(key=lambda item: item[:2])
        return [match for _, _, match in matches]

    def token_kind(self, token: str) -> SlashTokenKind:
        if not token.startswith("/"):
            return SlashTokenKind.NOT_SLASH
        if self._command_for_token(token):
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
        cmd = self._command_for_token(token)
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

    def _command_for_token(self, token: str) -> SlashEntry | None:
        needle = token.lower()
        for command in self._commands:
            if needle in command.all_names():
                return command
        return None


def _subsequence_indices(query: str, target: str) -> tuple[int, ...] | None:
    """返回 query 在 target 中按序匹配的字符位置。"""
    if not query:
        return ()
    target_lower = target.lower()
    indices: list[int] = []
    start = 0
    for char in query.lower():
        index = target_lower.find(char, start)
        if index == -1:
            return None
        indices.append(index)
        start = index + 1
    return tuple(indices)


def _match_score(indices: tuple[int, ...]) -> tuple[int, int]:
    """优先连续命中，再优先更靠前的命中。"""
    gaps = sum(right - left - 1 for left, right in zip(indices, indices[1:]))
    return gaps, indices[0] if indices else 0
