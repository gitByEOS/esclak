<div align="center">

<img src="https://raw.githubusercontent.com/gitByEOS/esclak/master/docs/images/logo.svg" alt="esclak" width="240" />

</div>

# clak

**C**ommand · **L**ines · **A**ggregator · **K**it

给散落的 Python 脚本一个统一入口，支持交互 TUI 和无头执行。

- 输入字母即可模糊搜索命令
- 注册自己的业务脚本，编排步骤与交互提问
- 查看日志、动态状态和固定步骤进度
- 同一份脚本可交互运行，也可传参批量执行

| 文档 | 适合什么时候阅读 |
|---|---|
| 本页 | 安装、接入与日常操作 |
| [完整示例](examples/dev_tools/README.md) | 运行发布工具、编写问答与验证停止行为 |
| [设计原则](docs/tech.md) | 维护框架时核对职责、状态、线程与扩展契约 |
| [Agent 使用指南](skills/clak/SKILL.md) | 让 Agent 使用 esclak 编写自己的业务工具 |
| [项目维护指南](AGENTS.md) | 修改本仓库、验证、记录任务、提交与发版 |
| [版本记录](CHANGELOG.md) | 查看已整理的版本变化 |

## 安装

```bash
pip install esclak
```

需要 Python 3.10 或更高版本。

## 最小应用

```python
from clak import Clak, Script


class DeployScript(Script):
    name = "/deploy"
    description = "发布服务"

    def run(self) -> None:
        def publish() -> int:
            self.output.push("开始发布 staging")
            self.output.push("发布完成")
            return 0

        self.add_step(True, publish, "发布服务")
        self.run_steps()


app = Clak(status="发布工具 · staging")
app.register(DeployScript)

if __name__ == "__main__":
    app.run_cli(prog="my-tool")
```

保存为 `my_tool.py` 后运行：

```bash
python my_tool.py                 # 默认打开 TUI
python my_tool.py tui             # 显式打开 TUI
python my_tool.py exec /deploy    # 无头执行已注册脚本
```

业务脚本应从自己的项目入口运行；安装后的全局 `clak` 只包含 `/version`、`/status` 等内置命令。

## 交互操作

| 操作 | 用法 |
|---|---|
| 搜索命令 | 直接输入字母，例如 `qi` 可匹配 `/quit`，命中字符黄绿色 |
| 选择与执行 | 命令候选打开时 `↑`/`↓` 选择，`Enter` 执行，`Tab` 补全 |
| 执行历史 | 空输入按 `↑` 回填上一条命令，`↑`/`↓` 浏览，`Enter` 再次执行 |
| 取消输入或历史浏览 | `Esc` 清空，不恢复草稿 |
| 粘贴 | 支持主输入、提问过滤框与自定义输入，不自动执行 |
| 查阅日志 | `PageUp` 上翻，`PageDown` 回底后恢复跟尾 |
| 清空日志 | `/clear`，保留当前进程的执行历史 |
| 查看版本 | `/version` |

普通单选、多选候选不接收粘贴；提问文本输入会将换行合并为单行。终端配色继承宿主环境，不强制黑底；中文按显示宽度排版。

### 步骤进度

运行时，输入区上方显示固定进度：

```text
✻ 发布检查…（3s · step 3/8 ）
  └ ✔ 选择检查结果
    ✔ 检查发布配置
    ◼ 检查资源清单
    ◻ 检查资源版本
    ◻ 检查服务连接
    …
```

完成项名称置灰并带删除线，仅对勾为绿色；未完成名称白色，当前名称加粗，当前方块固定黄绿色。标题与旋转标记按暖色九帧往返，每帧停留 0.22 秒，末帧完整停留，1.98 秒一轮。进度显示当前附近五项，省略号与步骤标记对齐；隐藏完成项以 `… +N completed` 汇总。完成、失败或停止收尾后进度区自动清空，业务日志与错误保留；进度不刷入日志。

### 停止与退出

| 操作 | 行为 |
|---|---|
| 运行中 `Ctrl+C` | 请求停止，当前调用结束后跳过后续步骤并清理 |
| 等待答案时 `Ctrl+C` | 停止当前脚本 |
| `Ctrl+Q` 或 `/quit` | 停止并清理后退出 |
| 当前脚本未结束时再启动 | 提示等待，避免重复运行 |

耗时步骤不会阻塞界面，但停止不等于强杀：`subprocess.run()`、网络请求等阻塞调用不会被自动终止，应由脚本设置超时或管理终止。临时资源应在 `on_exit()` 清理，不要提前删除仍在使用的文件。

## 无头执行与输入参数

```bash
python my_tool.py exec /deploy
```

脚本有提问字段时，用 `--set 字段名=值` 提供答案，或用 `--use-defaults` 接受默认值；字段名由脚本定义。以完整示例为例：

```bash
python3 -m examples.dev_tools exec /pack-upload \
  --set version=1.2.3 \
  --set targets=base,ios
python3 -m examples.dev_tools exec /pack-upload --use-defaults
```

- `--set` 可重复；只提供部分字段时，缺少的字段会报错，退出码为 `2`
- `--use-defaults` 允许未提供的字段使用默认值
- 候选值与业务格式仍会校验，不会绕过交互模式的规则

也可直接调用 Python API：

```python
run = app.run_line("/deploy")
print(run.text)
raise SystemExit(run.exit_code)
```

## 编写业务脚本

| 需求 | 推荐接口 |
|---|---|
| 添加步骤 | `self.add_step(条件, 函数, "面向用户的步骤名称")` |
| 启动步骤 | `self.run_steps()` |
| 提问 | 在步骤中返回 `self.ask_tool(AskRequest(...), 答案回调)` |
| 输出日志 | `self.output.push("发布完成")` |
| 业务失败 | 抛出 `ScriptError("失败原因", exit_code=1)` |
| 参数错误 | 抛出 `ValueError("输入格式不正确")` |
| 资源清理 | 重写 `on_exit()`，并调用 `super().on_exit()` |

普通步骤返回 `0` 继续；非零表示等待恢复，不是失败退出码。使用 `run_steps()` 绑定完成清理。提问、生命周期和自定义输出的完整写法见 [示例](examples/dev_tools/README.md)；底层接口与扩展约定见 [技术设计](docs/tech.md)。

## 完整项目示例

`examples/dev_tools` 展示服务器选择、单选/多选/过滤与自定义输入、发布检查、失败退出码、临时资源清理和脚本测试。

在源码仓库根目录执行：

```bash
python3 -m pip install -e ".[dev]"
python3 -m examples.dev_tools
python3 -m examples.dev_tools exec /pack-upload --use-defaults
python3 -m examples.dev_tools exec /verify-release --set outcome=failure
```

进入 TUI 后依次运行 `/select-res-server`、`/select-game-server` 和 `/verify-release`，即可观察进度与停止行为；检查仅为本地模拟，不访问真实服务器。

详细操作见 [示例说明](examples/dev_tools/README.md)。源码发行包包含示例、[技术设计](docs/tech.md)、任务记录与完整 [Agent 使用指南](skills/clak/SKILL.md)。

## 开发验证

```bash
python3 -m pip install -e ".[dev]"
python3 -m pytest
```

测试分层与框架不变量见 [技术设计](docs/tech.md#9-验证策略)。

## 许可

[MIT](LICENSE)
