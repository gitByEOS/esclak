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
    if request.mode == AskMode.MULTI:
        parts = {p.strip() for p in raw.split(",") if p.strip()}
        return AskAnswer(
            field_id=request.field_id,
            text=",".join(sorted(parts)),
            tokens=frozenset(parts),
        )
    return AskAnswer(
        field_id=request.field_id,
        text=raw,
        tokens=frozenset({raw}),
    )
