"""ask 协议：请求、选项、答案与解析。"""

from clak_py.runtime.ask.answer import AskAnswer, parse_ask_answer
from clak_py.runtime.ask.request import AskChoice, AskMode, AskRequest

__all__ = [
    "AskAnswer",
    "AskChoice",
    "AskMode",
    "AskRequest",
    "parse_ask_answer",
]
