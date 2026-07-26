from textual import events

from clak.tui.app import key_from_textual


def test_key_from_textual_printable():
    key = key_from_textual(events.Key("a", "a"))
    assert key.kind == "char"
    assert key.char == "a"
    assert not key.ctrl


def test_key_from_textual_ctrl_enter():
    key = key_from_textual(events.Key("ctrl+enter", None))
    assert key.kind == "enter"
    assert key.ctrl


def test_key_from_textual_super_enter():
    key = key_from_textual(events.Key("super+enter", None))
    assert key.kind == "enter"
    assert key.meta
