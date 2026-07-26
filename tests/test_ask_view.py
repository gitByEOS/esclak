from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.tui.views.ask import (
    encode_multi_answer,
    indices_from_default,
    init_for_request,
    option_label,
    type_row_head,
)


def test_multi_default_toggles_base_and_cn():
    request = AskRequest(
        field_id="targets",
        prompt="目标",
        default="base,cn",
        choices=(
            AskChoice(label="Base", value="base"),
            AskChoice(label="iOS", value="ios"),
            AskChoice(label="简体中文", value="cn"),
        ),
        mode=AskMode.MULTI,
    )
    assert indices_from_default(request) == [0, 2]
    state = init_for_request(request)
    assert state.toggled == frozenset({0, 2})
    assert encode_multi_answer(request, state.toggled) == "base,cn"


def test_option_label_custom_hint():
    choice = AskChoice(label="输入其他版本", value=None)
    assert option_label(choice, 1) == "2. 输入其他版本"


def test_type_row_head_keeps_hint_with_empty_input():
    choice = AskChoice(label="输入其他版本", value=None)
    head = type_row_head(choice, 1, 1, 1)
    assert "2. 输入其他版本" in head
    assert head.endswith(" ")
