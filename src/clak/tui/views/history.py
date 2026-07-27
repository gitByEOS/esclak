from __future__ import annotations

from enum import Enum, auto

from rich.console import RenderResult
from rich.segment import Segment
from rich.style import Style

from clak.runtime.output import OutputView
ROLE_STYLES: dict[str, tuple[str, str]] = {
    "user": ("You", "cyan"),
    "assistant": ("Assistant", "green"),
    "system": ("System", "yellow"),
    "error": ("Error", "red"),
}


class HistoryEntryKind(Enum):
    USER = auto()
    ASSISTANT = auto()
    SYSTEM = auto()
    ERROR = auto()
    OUTPUT = auto()

    def role_str(self) -> str:
        match self:
            case HistoryEntryKind.USER:
                return "user"
            case HistoryEntryKind.ASSISTANT:
                return "assistant"
            case HistoryEntryKind.SYSTEM:
                return "system"
            case HistoryEntryKind.ERROR:
                return "error"
            case HistoryEntryKind.OUTPUT:
                return "output"


class HistoryEntry:
    __slots__ = ("kind", "text")

    def __init__(self, kind: HistoryEntryKind, text: str) -> None:
        self.kind = kind
        self.text = text


class HistoryView:
    def __init__(self) -> None:
        self.entries: list[HistoryEntry] = []
        self.output_views: list[OutputView] = []
        self.scroll: int = 0

    def push(self, kind: HistoryEntryKind, text: str) -> None:
        self.entries.append(HistoryEntry(kind, text))

    def clear(self) -> None:
        self.entries.clear()
        self.scroll = 0

    def scroll_up(self) -> None:
        self.scroll = max(0, self.scroll - 1)

    def scroll_down(self) -> None:
        self.scroll += 1

    def attach(self, output_view: OutputView) -> None:
        self.output_views.append(output_view)

    def detach(self, output_view: OutputView) -> None:
        if output_view in self.output_views:
            self.output_views.remove(output_view)
            lines = output_view.render_lines()
            if lines:
                self.entries.append(HistoryEntry(HistoryEntryKind.OUTPUT, "\n".join(lines)))

    def display(self) -> str:
        lines: list[str] = []
        for entry in self.entries:
            if entry.kind == HistoryEntryKind.OUTPUT:
                lines.extend(entry.text.split("\n"))
            else:
                label = role_label(entry.kind)
                lines.append(f"{label}: {entry.text}")
        for output_view in self.output_views:
            lines.extend(output_view.render_lines())
        return "\n".join(lines)



def role_label(kind: HistoryEntryKind) -> str:
    role = kind.role_str()
    label, _ = ROLE_STYLES.get(role, (role, "white"))
    return label


def role_style(role: str) -> tuple[str, str]:
    return ROLE_STYLES.get(role, (role, "white"))


def entry_lines(entry: HistoryEntry) -> list[str]:
    if entry.kind == HistoryEntryKind.OUTPUT:
        return entry.text.split("\n")
    role = entry.kind.role_str()
    label, _ = role_style(role)
    prefix = f"{label}: "
    if not entry.text:
        return [prefix]
    result: list[str] = []
    for index, part in enumerate(entry.text.split("\n")):
        if index == 0:
            result.append(prefix + part)
        else:
            result.append("    " + part)
    return result


def render_history(
    history: HistoryView,
    width: int,
    height: int,
) -> RenderResult:
    lines: list[str] = []
    for entry in history.entries:
        lines.extend(entry_lines(entry))
    for output_view in history.output_views:
        lines.extend(output_view.render_lines())
    scroll = history.scroll
    visible = lines[scroll : scroll + height] if lines else [""]
    while len(visible) < height:
        visible.append("")
    for line in visible[:height]:
        yield Segment(line.ljust(width)[:width], Style())
        yield Segment.line()
