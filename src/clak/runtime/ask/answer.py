from __future__ import annotations

from dataclasses import dataclass

from clak.runtime.ask.request import AskMode, AskRequest


@dataclass(frozen=True)
class AskAnswer:
    """脚本侧结构化答案；线协议仅在边界序列化。"""

    field_id: str
    text: str
    tokens: frozenset[str]

    @property
    def primary(self) -> str:
        return self.text


def parse_ask_answer(request: AskRequest, wire: str) -> AskAnswer:
    raw = wire.strip() or request.default
    if not raw:
        raise ValueError(f"输入不能为空 [{request.field_id}]: {request.prompt}")
    if request.mode == AskMode.MULTI:
        parts = {p.strip() for p in raw.split(",") if p.strip()}
        _validate_choice_values(request, parts)
        return AskAnswer(
            field_id=request.field_id,
            text=",".join(sorted(parts)),
            tokens=frozenset(parts),
        )
    allows_custom = request.mode == AskMode.SINGLE and any(
        choice.value is None for choice in request.choices
    )
    if request.choices and not allows_custom:
        _validate_choice_values(request, {raw})
    return AskAnswer(
        field_id=request.field_id,
        text=raw,
        tokens=frozenset({raw}),
    )


def _validate_choice_values(request: AskRequest, values: set[str]) -> None:
    allowed = {
        choice.value or choice.label
        for choice in request.choices
        if choice.value is not None
    }
    invalid = sorted(values - allowed)
    if invalid:
        joined = ",".join(invalid)
        raise ValueError(f"无效输入 [{request.field_id}]: {joined}")
