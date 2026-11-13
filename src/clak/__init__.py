"""clak：固定流程脚本壳。"""

__version__ = "0.2.0"

from clak.application import Clak, FooterViewData
from clak.commands.types import Script
from clak.runtime.ask import AskAnswer, AskChoice, AskMode, AskRequest
from clak.runtime.errors import ScriptError
from clak.runtime.headless import HeadlessRun
from clak.runtime.output import OutputView
from clak.runtime.params import ScriptInputs
from clak.runtime.session import Session
from clak.testing import ScriptRun, ScriptTester

__all__ = [
    "AskAnswer",
    "AskChoice",
    "AskMode",
    "AskRequest",
    "Clak",
    "FooterViewData",
    "HeadlessRun",
    "OutputView",
    "Script",
    "ScriptError",
    "ScriptInputs",
    "ScriptRun",
    "ScriptTester",
    "Session",
    "__version__",
]
