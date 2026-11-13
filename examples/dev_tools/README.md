# dev_tools 示例

这是一个可直接运行、也适合复制进业务仓库的 clak 项目。它使用自己的 `Clak` 实例注册业务脚本，同一个入口同时支持 TUI 和无头执行。

## 从源码仓库运行

在 esclak 仓库根目录执行：

```bash
python3 -m pip install -e ".[dev]"
python3 -m examples.dev_tools
python3 -m examples.dev_tools tui
python3 -m examples.dev_tools exec /pack-upload --use-defaults
```

运行示例前必须先以可编辑模式安装当前源码，确保使用的是当前仓库版本的 `esclak`。TUI 会继承宿主终端主题；在 VS Code 集成终端中不会强制黑底。

## 复制到业务项目

安装依赖：

```bash
pip install esclak
```

复制 `dev_tools/` 目录后运行：

```bash
python -m dev_tools
python -m dev_tools exec /pack-upload \
  --set version=1.2.3 \
  --set targets=base,win
```

不要使用全局 `clak exec /pack-upload`：全局命令不知道业务项目注册了哪些脚本。`python -m dev_tools` 才会加载本目录的 `app`。

在 TUI 主输入区直接键入字母即可搜索命令，不需要先输入 `/`。搜索采用子序列模糊匹配，例如 `pu` 可匹配 `/pack-upload`；`Enter` 执行选中项，`Tab` 补全为完整命令。主输入、提问过滤框和自定义输入支持粘贴，粘贴不会自动执行；候选选项不会接收粘贴。

主输入为空时按 `↑` 回填最近执行的命令，继续 `↑`/`↓` 浏览，`Enter` 再次执行，`Esc` 取消并清空；只记本进程已提交命令，不记问答答案，也不恢复草稿。输入新命令打开候选列表时，`↑`/`↓` 仍选择候选。

日志默认跟随最新输出，`PageUp` 翻阅历史时保持阅读位置，`PageDown` 回到底部后恢复跟尾；中文按终端显示列宽排版。

耗时步骤在工作线程运行，不阻塞界面。`Ctrl+C` 请求停止，当前同步调用返回后才清理；`Ctrl+Q` 或 `/quit` 请求停止并等待清理后退出。示例子进程仍使用带超时的 `subprocess.run()`，停止不会自动终止它，最多等待其完成或超时后再收尾。

## 脚本一览

- `/pack-upload`：询问版本和目标，运行子进程生成临时产物，按条件校验 Windows 清单，上传后清理临时目录。
- `/select-res-server`：过滤选择资源服，完成后 `/status` 立即更新。
- `/select-game-server`：过滤选择后端服，完成后 footer 立即更新。
- `/verify-release`：对当前资源服与后端服执行六项本地模拟检查，约 4 秒完成；固定底部区域显示步骤、耗时与九帧节拍动画，业务日志只保留目标和结果。最终子进程展示成功或退出码为 1 的失败结果。

## 发布检查最小演示

从仓库根目录启动：

```bash
python3 -m examples.dev_tools
```

```text
/select-res-server → /select-game-server → /verify-release → 选择成功或模拟失败
                                                   ├→ 分步检查 → 结果与收尾
                                                   └→ Ctrl+C → 当前项结束 → 停止与收尾
```

这只是本地模拟，不会连接或修改真实服务器。每次运行会记录进入时选择的服务器；后续切换不会改变本次检查目标。

| 操作 | 可观察结果 |
|---|---|
| 先选择资源服和后端服 | 发布检查显示相同目标，底栏保留当前后端服 |
| 执行 `/verify-release` 并选择成功 | 运行时显示步骤进度，完成后进度区清空，日志保留“发布检查通过” |
| 观察运行标题和当前步骤 | 九帧每帧0.22秒，末帧停留，总周期1.98秒；方块固定黄绿，当前名称白色加粗，完成名称灰色删除线、对勾绿色 |
| 运行中输入字母或翻阅已有日志 | 输入正常响应，固定进度区不随历史滚动，不刷入日志 |
| 运行中 `Ctrl+C` | 当前约 0.6 秒检查结束后停止，收尾后清空进度区，不执行后续检查 |
| 运行中 `Ctrl+Q` | 等当前检查结束并收尾后退出 |
| 选择模拟失败 | 日志保留失败原因，收尾后进度区清空 |

`scripts/verify_release.py` 定义六项模拟检查，加上提问和最终验证，共 8 步。脚本只需用 `add_step()` 命名并注册步骤，进度自动显示，不需要自己计数；内部职责见 [执行与进度设计](../../docs/tech.md#4-执行与进度的唯一事实来源)。

```text
✻ 发布检查…（2s · step 3/8 ）
  └ ✔ 选择检查结果
    ✔ 检查发布配置
    ◼ 检查资源清单
    ◻ 检查资源版本
    ◻ 检查服务连接
    …
```

进度显示当前附近五项，完成名称灰色删除线，隐藏完成项用 `… +N completed` 汇总，省略号与对勾对齐。等待答案时动画停止，收尾后进度区自动清空；无头模式只输出业务文本。精确的窗口、摘要与矮屏规则见 [终端渲染设计](../../docs/tech.md#7-终端渲染与固定进度区)。

可以直接验证失败路径：

```bash
python -m dev_tools exec /verify-release --set outcome=failure
echo $?
# 1
```

候选值会严格校验，下面的命令返回退出码 2，不会修改当前服务器：

```bash
python -m dev_tools exec /select-res-server \
  --set res_server=unknown
```

## 目录

```text
dev_tools/
├── README.md
├── __init__.py
├── __main__.py       # app.run_cli()：项目级 tui/exec 入口
├── app.py            # 创建 app，注册所有脚本
├── context.py        # 多脚本共享的进程内状态
└── scripts/
    ├── pack_upload.py
    ├── select_game_server.py
    ├── select_res_server.py
    └── verify_release.py
```

`context.py` 定义模块级 `context`：资源服选择脚本写入 `res_server`，后端服选择脚本写入 `game_server`；上传脚本、状态栏和 footer 读取这些值。它只在当前 Python 进程内共享；关闭并重新启动应用后会恢复默认值。`reset()` 用于测试隔离，跨进程持久化应接入配置文件或数据库。

## 编写脚本时必须理解的约定

1. `app.register(MyScript)` 注册的是脚本类，每次执行都会创建新实例。
2. `self.add_step(can_do, task, name)` 向本次执行队列追加一步，`can_do` 可以是布尔值或运行时判断函数。
3. `self.run_steps()` 绑定完成回调并启动执行队列，负责在全部步骤结束时触发生命周期清理。
4. 任务返回 `0` 表示同步继续；非零表示队列挂起，不是失败退出码。
5. 需要用户输入时返回 `self.ask_tool(AskRequest(...), on_answer)`，框架会在得到答案后恢复下一项。
6. 业务失败抛出 `ScriptError`；输入格式错误抛出 `ValueError`。
7. 临时资源在 `on_exit()` 清理，完成、失败或请求停止后的安全边界都会调用一次；不能提前删除仍被当前步骤使用的文件。
8. 步骤与回调不要直接操作 Textual Widget；线程与通知约定见 [TUI 数据流与线程边界](../../docs/tech.md#5-tui-数据流与线程边界)。

候选、多选和过滤字段由框架统一校验。只有包含 `AskChoice(value=None)` 的单选问题允许用户输入候选之外的自定义文本，业务格式仍应在答案回调中校验。

每个脚本的 `self.output.push()` 默认以 `[脚本名] ` 标记每行输出，例如 `[pack-upload] 上传完成`，便于在 history 中区分多个脚本。

## 测试

仓库根目录的测试覆盖 TUI、无头参数、非法 choice、子进程失败和资源清理：

```bash
python3 -m pytest
python3 -m pytest -q tests/test_verify_release.py
```

`tests/test_verify_release.py` 演示用 `ScriptTester` 驱动同一业务脚本，验证服务器快照、成功/失败、动态输出，以及真实 TUI 运行中停止；测试替换等待函数，不为正式示例添加快速模式。

```python
from clak import ScriptTester
from examples.dev_tools.scripts.verify_release import VerifyReleaseScript

run = ScriptTester(VerifyReleaseScript).run()
assert run.is_awaiting("outcome")
run.provide("outcome", "success")
assert run.succeeded
assert len(run.session.progress.steps) == 8
assert "发布检查通过" in run.output.text
```
