from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from clak.runtime.ask import AskMode, AskRequest
from clak.tui.views import ask as ask_view
from clak.tui.views.ask import AskViewState, encode_multi_answer
from clak.tui.event import TuiKey, TuiOutcome
from clak.tui.views.input import InputView


@dataclass
class AskUiBindings:
    view: AskViewState
    input_view: InputView
    terminal_width: int
    pending: AskRequest
    submit_wire: Callable[[str], TuiOutcome]
    cancel_script: Callable[[], TuiOutcome]
    set_context_line: Callable[[str], None]


def sync_view_for_request(
    pending: AskRequest | None,
    field_id: str | None,
    view: AskViewState,
) -> tuple[AskViewState, str | None]:
    if not pending:
        return ask_view.AskViewState(), None
    if pending.field_id == field_id:
        return view, field_id
    return ask_view.init_for_request(pending), pending.field_id


def handle_ask_key(bindings: AskUiBindings, key: TuiKey) -> TuiOutcome | None:
    if bindings.pending.mode == AskMode.FILTER:
        return _handle_filter(bindings, key)
    if bindings.pending.mode == AskMode.MULTI:
        return _handle_multi(bindings, key)
    return _handle_single(bindings, key)


def _handle_filter(bindings: AskUiBindings, key: TuiKey) -> TuiOutcome | None:
    view = bindings.view
    request = bindings.pending
    if key.kind == "escape":
        return bindings.cancel_script()
    if key.kind == "char" and key.char == "c" and key.ctrl:
        return bindings.cancel_script()
    if key.kind == "up":
        view.selected = max(0, view.selected - 1)
        return TuiOutcome.REDRAW
    if key.kind == "down":
        filtered = ask_view.filtered_choices(request, view.query)
        view.selected = min(max(0, len(filtered) - 1), view.selected + 1)
        return TuiOutcome.REDRAW
    if key.kind == "enter":
        filtered = ask_view.filtered_choices(request, view.query)
        if not filtered:
            bindings.set_context_line("无匹配项")
            return TuiOutcome.REDRAW
        idx = min(view.selected, len(filtered) - 1)
        choice = filtered[idx]
        return bindings.submit_wire(choice.value or choice.label)
    if key.kind == "backspace":
        if view.query:
            view.query = view.query[:-1]
            view.selected = 0
        return TuiOutcome.REDRAW
    if key.kind == "char" and key.char and not key.ctrl and "\n" not in key.char:
        view.query += key.char
        view.selected = 0
        return TuiOutcome.REDRAW
    return TuiOutcome.REDRAW


def _handle_single(bindings: AskUiBindings, key: TuiKey) -> TuiOutcome | None:
    request = bindings.pending
    view = bindings.view
    choice_count = len(request.choices)
    custom = ask_view.custom_choice_index(request)
    if choice_count == 0:
        return None
    if key.kind == "up":
        view.selected = max(0, view.selected - 1)
        return TuiOutcome.REDRAW
    if key.kind == "down":
        view.selected = min(choice_count - 1, view.selected + 1)
        return TuiOutcome.REDRAW
    if key.kind == "escape":
        if custom is not None and view.selected == custom:
            view.selected = 0
            return TuiOutcome.REDRAW
        return bindings.cancel_script()
    if key.kind == "char" and key.char == "c" and key.ctrl:
        if not _is_custom_focused(request, view):
            return bindings.cancel_script()
        return None
    if _is_custom_focused(request, view):
        return _handle_custom_input(bindings, key)
    if key.kind == "char" and key.char in "12" and not key.ctrl:
        index = int(key.char) - 1
        if index < choice_count:
            return _activate_choice(bindings, index)
    if key.kind == "enter":
        return _activate_choice(bindings, view.selected)
    if key.kind == "char" and key.char and not key.ctrl:
        return TuiOutcome.REDRAW
    return None


def _handle_multi(bindings: AskUiBindings, key: TuiKey) -> TuiOutcome | None:
    request = bindings.pending
    view = bindings.view
    choice_count = len(request.choices)
    if choice_count == 0:
        return None
    if key.kind == "up":
        view.selected = max(0, view.selected - 1)
        return TuiOutcome.REDRAW
    if key.kind == "down":
        view.selected = min(choice_count - 1, view.selected + 1)
        return TuiOutcome.REDRAW
    if key.kind == "escape":
        return bindings.cancel_script()
    if key.kind == "char" and key.char == "c" and key.ctrl:
        return bindings.cancel_script()
    if key.kind == "char" and key.char == " ":
        bindings.view = ask_view.toggle_index(view, view.selected)
        return TuiOutcome.REDRAW
    if key.kind == "enter":
        wire = encode_multi_answer(request, view.toggled)
        return bindings.submit_wire(wire)
    return TuiOutcome.REDRAW


def _handle_custom_input(bindings: AskUiBindings, key: TuiKey) -> TuiOutcome | None:
    if key.kind == "char" and key.char == "c" and key.ctrl:
        if bindings.input_view.is_empty():
            return bindings.cancel_script()
        bindings.input_view.take()
        return TuiOutcome.REDRAW
    if key.kind == "enter":
        line = ask_view.inline_draft_text(bindings.input_view).strip()
        if not line:
            bindings.set_context_line("输入不能为空")
            return TuiOutcome.REDRAW
        bindings.input_view.take()
        return bindings.submit_wire(line)
    if key.kind == "backspace":
        bindings.input_view.delete_before_cursor()
        return TuiOutcome.REDRAW
    if key.kind == "delete":
        bindings.input_view.delete_after_cursor()
        return TuiOutcome.REDRAW
    if key.kind == "left":
        bindings.input_view.move_cursor(-1, bindings.terminal_width)
        return TuiOutcome.REDRAW
    if key.kind == "right":
        bindings.input_view.move_cursor(1, bindings.terminal_width)
        return TuiOutcome.REDRAW
    if key.kind in ("home",) or (key.kind == "char" and key.char == "a" and key.ctrl):
        bindings.input_view.move_cursor_home()
        return TuiOutcome.REDRAW
    if key.kind in ("end",) or (key.kind == "char" and key.char == "e" and key.ctrl):
        bindings.input_view.move_cursor_end()
        return TuiOutcome.REDRAW
    if key.kind == "char" and key.char and not key.ctrl and "\n" not in key.char:
        bindings.input_view.insert_at_cursor(key.char, bindings.terminal_width)
        return TuiOutcome.REDRAW
    return None


def _activate_choice(bindings: AskUiBindings, index: int) -> TuiOutcome:
    request = bindings.pending
    view = bindings.view
    if index >= len(request.choices):
        return TuiOutcome.REDRAW
    choice = request.choices[index]
    if choice.value is None:
        view.selected = index
        draft = ask_view.inline_draft_text(bindings.input_view).strip()
        if draft:
            bindings.input_view.take()
            return bindings.submit_wire(draft)
        return TuiOutcome.REDRAW
    return bindings.submit_wire(choice.value)


def _is_custom_focused(request: AskRequest, view: AskViewState) -> bool:
    custom = ask_view.custom_choice_index(request)
    return custom is not None and view.selected == custom
