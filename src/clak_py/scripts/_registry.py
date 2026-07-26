"""脚本注册：@script 装饰器 + 自动扫描。"""

from __future__ import annotations

import importlib
import pkgutil
from collections.abc import Callable

from clak_py.commands.types import ScriptEntry
from clak_py.runtime.session import ScriptSession

ScriptRunner = Callable[[ScriptSession], None]

_SCRIPTS: dict[str, ScriptEntry] = {}
_discovered = False


def script(
    slash_name: str,
    description: str,
    *,
    aliases: tuple[str, ...] = (),
) -> Callable[[ScriptRunner], ScriptRunner]:
    """装饰脚本函数，注册为 ScriptEntry。slash_name 带斜杠，script_id 自动去斜杠。"""

    def deco(runner: ScriptRunner) -> ScriptRunner:
        entry = ScriptEntry(
            name=slash_name,
            aliases=aliases,
            description=description,
            script_id=slash_name.lstrip("/"),
            script_run=runner,
        )
        _SCRIPTS[entry.script_id] = entry
        return runner

    return deco


def all_scripts() -> tuple[ScriptEntry, ...]:
    if not _discovered:
        discover()
    return tuple(_SCRIPTS.values())


def script_for(script_id: str) -> ScriptEntry | None:
    if not _discovered:
        discover()
    return _SCRIPTS.get(script_id)


def discover() -> None:
    """扫描 scripts/ 包内所有非下划线开头模块，触发 @script 注册。"""
    global _discovered
    if _discovered:
        return
    _discovered = True
    # 用包 __path__ 而非文件路径，兼容 pyinstaller frozen 环境
    import clak_py.scripts as _pkg
    for mod_info in pkgutil.iter_modules(_pkg.__path__):
        if mod_info.name.startswith("_"):
            continue
        importlib.import_module(f"clak_py.scripts.{mod_info.name}")
