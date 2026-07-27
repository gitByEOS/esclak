from __future__ import annotations


class ScriptError(RuntimeError):
    """脚本可预期失败；在 TUI 显示错误，在无头模式返回指定退出码。"""

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        if not 1 <= exit_code <= 255:
            raise ValueError("ScriptError.exit_code 必须在 1..255 之间")
        super().__init__(message)
        self.exit_code = exit_code
