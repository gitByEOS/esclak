# AGENTS.md — clak 三方库接入指南

clak 不承载业务脚本。业务项目创建 `Clak`，并注册自己的 Script 子类。

```python
from clak import Clak, Script, Session


class DeployScript(Script):
    name = "/deploy"
    description = "发布服务"

    def run(self, session: Session) -> None:
        def deploy() -> int:
            self.output.push("发布完成")
            return 0

        session.bind_exec_end()
        session.exec_list.add(True, deploy, "deploy")
        session.run()


app = Clak(status="发布工具")
app.register(DeployScript)

if __name__ == "__main__":
    app.run_cli(prog="dev-tools")
```

每次执行都会创建新的 Script 和 `self.output`。默认 `self.output.push()` 为每行追加 `[脚本名] ` 前缀；TUI 会在 `on_enter` 挂载输出，在完成或中断后调用 `on_exit` 脱离。

业务项目从自己的入口执行：`python -m dev_tools` 或 `python -m dev_tools exec /deploy`。全局 `clak` 入口只包含内置命令。TUI 主输入区可直接输入字母模糊搜索命令，`Enter` 执行候选，`Tab` 补全，`Esc` 清空搜索。

`session.exec_list` 是本次运行专属的执行队列：任务返回 `0` 表示同步继续，非零表示挂起而不是失败。调用 `session.bind_exec_end()` 绑定完成清理；业务失败抛出 `ScriptError`，参数格式错误抛出 `ValueError`。常用业务类型从 `clak` 顶层导入。

验证：`python3 -m pip install -e ".[dev]" && python3 -m pytest`
