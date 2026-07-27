from __future__ import annotations

from dataclasses import dataclass, field


class MissingScriptInputError(ValueError):
    def __init__(self, field_id: str, prompt: str) -> None:
        super().__init__(f"缺少脚本输入 [{field_id}]: {prompt}")
        self.field_id = field_id


@dataclass
class ScriptInputs:
    """Exec 无交互：只从此读取参数；未补齐则挂起或报错。"""

    values: dict[str, str] = field(default_factory=dict)
    allow_defaults: bool = False

    def get(self, field_id: str) -> str | None:
        return self.values.get(field_id)

    def set(self, field_id: str, wire: str) -> None:
        self.values[field_id] = wire

    def resolve_wire(self, field_id: str, default: str) -> str | None:
        wire = self.get(field_id)
        if wire is not None:
            return wire
        if self.allow_defaults and default:
            return default
        return None

    @classmethod
    def from_pairs(cls, pairs: dict[str, str], *, allow_defaults: bool = False) -> ScriptInputs:
        return cls(values=dict(pairs), allow_defaults=allow_defaults)

    @classmethod
    def parse_set_flags(cls, flags: list[str], *, allow_defaults: bool = False) -> ScriptInputs:
        values: dict[str, str] = {}
        for item in flags:
            if "=" not in item:
                raise ValueError(f"无效 --set 格式（需 field=value）: {item}")
            key, value = item.split("=", 1)
            key = key.strip()
            if not key:
                raise ValueError(f"无效 --set 格式: {item}")
            values[key] = value.strip()
        return cls(values=values, allow_defaults=allow_defaults)
