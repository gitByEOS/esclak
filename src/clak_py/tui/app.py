from __future__ import annotations

from textual import events
from textual.app import App, ComposeResult
from textual.geometry import Offset
from textual.widgets import Static

from clak_py.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak_py.tui.state import TuiState
from clak_py.tui.screen import ClakRenderable

_MODIFIER_ALIASES = frozenset({"meta", "super", "cmd", "hyper", "alt"})
_SPECIAL_KEYS = frozenset(
    {
        "enter",
        "backspace",
        "delete",
        "left",
        "right",
        "home",
        "end",
        "pageup",
        "pagedown",
        "escape",
        "tab",
        "up",
        "down",
    }
)


def _split_textual_key(key: str) -> tuple[tuple[str, ...], str]:
    parts = key.split("+")
    if len(parts) == 1:
        return (), parts[0]
    *modifiers, base = parts
    return tuple(modifiers), base


def _modifier_flags(modifiers: tuple[str, ...]) -> tuple[bool, bool, bool]:
    ctrl = "ctrl" in modifiers
    shift = "shift" in modifiers
    meta = any(m in _MODIFIER_ALIASES for m in modifiers)
    return ctrl, shift, meta


def key_from_textual(event: events.Key) -> TuiKey:
    modifiers, base = _split_textual_key(event.key)
    ctrl, shift, meta = _modifier_flags(modifiers)
    base_id = base.lower()

    if base_id in _SPECIAL_KEYS:
        return TuiKey(base_id, ctrl=ctrl, shift=shift, meta=meta)

    char = event.character
    if char and len(char) == 1 and char.isprintable():
        return TuiKey("char", char=char, ctrl=ctrl, shift=shift, meta=meta)

    if len(base) == 1:
        return TuiKey("char", char=base, ctrl=ctrl, shift=shift, meta=meta)

    return TuiKey("unknown", ctrl=ctrl, shift=shift, meta=meta)


class ClakView(Static):
    can_focus = True

    def __init__(self, state: TuiState) -> None:
        super().__init__()
        self.state = state
        self._renderable = ClakRenderable(state)

    def render(self):
        self._renderable = ClakRenderable(self.state)
        return self._renderable

    def get_content_width(self, container, viewport) -> int:
        return container.size.width

    def get_content_height(self, container, viewport) -> int:
        return container.size.height

    def on_resize(self, event: events.Resize) -> None:
        self.state.handle_event(
            TuiEvent(resize_width=event.size.width, resize_height=event.size.height)
        )
        self.refresh()
        self._update_cursor()

    async def on_key(self, event: events.Key) -> None:
        if event.key == "ctrl+c":
            outcome = self.state.handle_event(
                TuiEvent(key=TuiKey("char", char="c", ctrl=True))
            )
        else:
            outcome = self.state.handle_event(TuiEvent(key=key_from_textual(event)))
        event.stop()
        if outcome == TuiOutcome.QUIT:
            self.app.exit()
            return
        self._refresh_after_state_change()

    def _refresh_after_state_change(self) -> None:
        self.refresh()
        self.state.after_present()
        self._update_cursor()

    def on_mount(self) -> None:
        self.focus()
        self.state.terminal_width = self.size.width
        self.state.terminal_height = self.size.height
        self._update_cursor()
        self.set_interval(60, self._tick)

    def _tick(self) -> None:
        self.state.tick()
        self.refresh()
        self._update_cursor()

    def _update_cursor(self) -> None:
        pos = self._renderable.cursor_screen
        if pos is None:
            self.app.cursor_position = Offset(-1, -1)
            return
        col, row = pos
        x, y, _, _ = self.content_region
        self.app.cursor_position = Offset(x + col, y + row)


class ClakApp(App):
    CSS = """
    Screen {
        background: #0d1117;
    }
    ClakView {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [("ctrl+q", "quit", "退出")]

    def __init__(self) -> None:
        super().__init__()
        self.state = TuiState()

    def compose(self) -> ComposeResult:
        yield ClakView(self.state)

    def action_quit(self) -> None:
        self.exit()


def run_tui() -> None:
    ClakApp().run()
