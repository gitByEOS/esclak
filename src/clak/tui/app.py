from __future__ import annotations

from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.geometry import Offset
from textual.message import Message
from textual.widgets import Static

from clak.application import Clak
from clak.tui import theme
from clak.tui.event import TuiEvent, TuiKey, TuiOutcome
from clak.tui.state import TuiState
from clak.tui.screen import ClakRenderable
from clak.tui.runner import RunUpdate, ScriptRunner

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


class ScriptUpdated(Message):
    def __init__(self, runner: ScriptRunner, update: RunUpdate) -> None:
        super().__init__()
        self.runner = runner
        self.update = update

    def can_replace(self, message: Message) -> bool:
        return (
            isinstance(message, ScriptUpdated)
            and message.runner is self.runner
            and message.update.state == self.update.state
            and (message.update.session is None) == (self.update.session is None)
        )


class ClakView(Static):
    can_focus = True

    def __init__(self, state: TuiState) -> None:
        super().__init__()
        self.state = state
        self._renderable = ClakRenderable(state)
        self._animation_timer = None

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
        self._present_outcome(outcome)

    def on_paste(self, event: events.Paste) -> None:
        outcome = self.state.handle_event(TuiEvent(paste=event.text))
        event.stop()
        self._present_outcome(outcome)

    def on_script_updated(self, message: ScriptUpdated) -> None:
        self._present_outcome(self.state.apply_run_update(message.runner, message.update))

    def _present_outcome(self, outcome: TuiOutcome) -> None:
        if outcome == TuiOutcome.QUIT:
            self.app.exit()
            return
        self._refresh_after_state_change()

    def _refresh_after_state_change(self) -> None:
        runner = self.state.take_pending_runner()
        if runner is not None:
            self.run_worker(
                lambda: runner.run(
                    lambda update: self.post_message(ScriptUpdated(runner, update))
                ),
                thread=True,
                name=f"script:{runner.script_id}",
            )
        self._sync_animation()
        self.refresh()
        self.call_after_refresh(self._update_cursor)

    def _sync_animation(self) -> None:
        if self._animation_timer is None:
            return
        if self.state.is_progress_animated():
            self._animation_timer.resume()
        else:
            self._animation_timer.pause()

    def _animate_progress(self) -> None:
        self._sync_animation()
        if self.state.is_progress_animated():
            self.refresh()
            self.call_after_refresh(self._update_cursor)

    def on_unmount(self) -> None:
        if self.state.runner is not None:
            self.state.runner.cancel()

    def on_mount(self) -> None:
        self.focus()
        self.state.terminal_width = self.size.width
        self.state.terminal_height = self.size.height
        self._update_cursor()
        self.set_interval(60, self._tick)
        self._animation_timer = self.set_interval(
            theme.PROGRESS_ANIMATION_INTERVAL_SECONDS, self._animate_progress, pause=True
        )

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
    ClakView {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [Binding("ctrl+q", "quit", "退出", priority=True)]

    def __init__(self, app: Clak | None = None) -> None:
        super().__init__(ansi_color=True)
        self.state = TuiState(app)

    def compose(self) -> ComposeResult:
        yield ClakView(self.state)

    def action_quit(self) -> None:
        outcome = self.state.request_quit()
        self.query_one(ClakView)._present_outcome(outcome)


def run_tui(app: Clak | None = None) -> None:
    ClakApp(app).run()
