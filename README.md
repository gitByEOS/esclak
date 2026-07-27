<div align="center">

<img src="https://raw.githubusercontent.com/gitByEOS/esclak/master/docs/images/logo.svg" alt="esclak" width="240" />

</div>

# clak

可嵌入的固定流程脚本 TUI 与无头执行，支持步骤编排、交互提问、动态状态和脚本级输出视图。

## 安装

```bash
pip install esclak
```

需要 Python 3.10 或更高版本。发布变更见 [CHANGELOG.md](CHANGELOG.md)。

## 最小应用

```python
from clak import Clak, Script, Session


class DeployScript(Script):
    name = "/deploy"
    description = "发布服务"

    def run(self, session: Session) -> None:
        def publish() -> int:
            self.output.push("开始发布 staging")
            self.output.push("发布完成")
            return 0

        session.bind_step_end()
        session.step_list.add(True, publish, "publish")
        session.run()


app = Clak(status="发布工具 · staging")
app.register(DeployScript)

if __name__ == "__main__":
    app.run_cli(prog="my-tool")
```

保存为 `my_tool.py` 后，可以使用同一个应用入口运行 TUI 或无头任务：

```bash
python my_tool.py                 # 默认打开 TUI
python my_tool.py tui             # 显式打开 TUI
python my_tool.py exec /deploy    # 无头执行已注册脚本
```

安装后得到的全局 `clak` 命令只包含 `/version`、`/status` 等内置命令。业务脚本注册在自己的 `Clak` 实例中，因此应从项目入口执行。

## TUI 命令菜单

主输入区直接键入字母即可搜索命令，无需先输入 `/`。搜索使用大小写无关的子序列匹配，例如 `qi` 会匹配 `/quit`，命中的 `q` 和 `i` 显示为黄色。`↑`/`↓` 切换候选，`Enter` 执行选中命令，`Tab` 补全为完整 slash 命令，`Esc` 清空本次搜索；仍可直接输入完整 `/command`。

TUI 使用终端原生 ANSI 前景和背景，不强制深色主题；在 VS Code 集成终端中会继承当前终端配色。

## 带输入的无头执行

```bash
python my_tool.py exec /deploy --set environment=staging
python my_tool.py exec /deploy --use-defaults
```

- `--set field=value` 可以重复；只提供部分字段时，缺少的字段会报错并返回退出码 2。
- `--use-defaults` 允许未提供的字段使用 `AskRequest.default`。
- choice 字段在 TUI 和无头模式使用相同校验，候选之外的值会被拒绝。

也可以直接调用 Python API：

```python
from clak import ScriptInputs

run = app.run_line(
    "/deploy",
    script_inputs=ScriptInputs.from_pairs(
        {"environment": "staging"},
        allow_defaults=False,
    ),
)
print(run.text)
raise SystemExit(run.exit_code)
```

## 步骤协议

`session.step_list.add(can_do, step, name)` 中：

- `can_do` 是布尔值或无参判断函数；为假时跳过该步骤。
- 普通同步步骤返回 `0`，随后继续执行下一步。
- 非零返回值表示流程挂起，不代表进程失败；`ask_step()` 会负责挂起和恢复。
- `bind_step_end()` 绑定完成通知，脚本入口必须在 `run()` 前调用。
- 每次脚本执行都会获得新的 `Session` 和 `StepList`，通常不需要先调用 `clear()`。

可预期的业务失败使用 `ScriptError`：

```python
from clak import ScriptError

if deploy_failed:
    raise ScriptError("发布失败：健康检查未通过", exit_code=1)
```

TUI 会显示该错误；无头模式会写入 stderr 并返回指定退出码。参数格式错误使用 `ValueError`，返回退出码 2。

## 生命周期与输出

每次运行都会创建新的 Script 实例和 `self.output`。默认 `self.output.push()` 会为每一行增加 `[脚本名] ` 前缀，例如 `[pack-upload] 上传完成`，便于区分不同脚本的 history 输出。TUI 在启动时调用 `on_enter(session)`，完成、失败或中断时调用 `on_exit()`。脚本结束后，输出会保留在 history 中。

```python
class PublishScript(Script):
    name = "/publish"
    description = "发布"

    def on_enter(self, session: Session) -> None:
        super().on_enter(session)
        self.output.push("已创建临时目录")

    def on_exit(self) -> None:
        self.output.push("已清理临时目录")
        super().on_exit()
```

## 稳定公共 API

常用业务类型均可从 `clak` 顶层导入：

```python
from clak import (
    AskAnswer,
    AskChoice,
    AskMode,
    AskRequest,
    Clak,
    FooterViewData,
    HeadlessRun,
    OutputView,
    Script,
    ScriptError,
    ScriptInputs,
    Session,
)
```

`clak.runtime.*` 是实现模块；业务代码优先使用上述顶层导入。

## 完整项目示例

[dev_tools 完整示例](https://github.com/gitByEOS/esclak/tree/master/examples/dev_tools) 展示：

- 项目级 `tui`/`exec` 入口；
- 单选、多选、过滤与自定义输入；
- 跨脚本的进程内状态和动态 footer；
- choice 与版本号校验；
- 子进程成功、失败退出码、条件步骤和临时目录清理；
- TUI 与无头测试。

克隆仓库后，先以可编辑模式安装当前源码和开发依赖：

```bash
python3 -m pip install -e ".[dev]"
python3 -m examples.dev_tools
python3 -m examples.dev_tools exec /pack-upload --use-defaults
python3 -m examples.dev_tools exec /verify-release --set outcome=failure
```

详细说明见 [examples/dev_tools/README.md](https://github.com/gitByEOS/esclak/blob/master/examples/dev_tools/README.md)。源码发行包也包含 `examples/`。

## 开发验证

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
```

## 许可

[MIT](LICENSE)
