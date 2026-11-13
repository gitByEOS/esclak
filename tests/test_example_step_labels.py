import pytest

from clak import ScriptTester
from examples.dev_tools.scripts.pack_upload import PackUploadScript
from examples.dev_tools.scripts.select_game_server import SelectGameServerScript
from examples.dev_tools.scripts.select_res_server import SelectResServerScript


@pytest.mark.parametrize(
    "script,expected",
    [
        (PackUploadScript, ["选择资源版本", "选择打包目标", "打包并上传", "校验Windows清单"]),
        (SelectGameServerScript, ["选择后端服"]),
        (SelectResServerScript, ["选择资源服"]),
    ],
)
def test_example_progress_uses_user_facing_step_labels(script, expected):
    run = ScriptTester(script).run()
    try:
        assert [step.name for step in run.session.progress.steps] == expected
    finally:
        run.session.cancel()
