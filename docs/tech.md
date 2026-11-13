# clak 设计原则与技术契约

本文是框架的设计原则与技术契约，面向维护框架、扩展运行时或自定义视图的人，用于约束实现而非事后描述。修改代码必须在同轮核对并同步相关原则、状态与边界；原则未变化时明确核对结果，不添加空泛文字凑同步。

只需编写和运行脚本时，从 [使用说明](../README.md) 与 [完整示例](../examples/dev_tools/README.md) 开始；Agent 使用指南见 [skills/clak](../skills/clak/SKILL.md)。项目维护流程以 [AGENTS](../AGENTS.md) 为准。

## 1. 定位与设计边界

clak 为散落的 Python 脚本提供统一入口，同一份业务代码可在交互 TUI 与无头模式执行。它不是远程任务平台或智能体编排系统，不内置 HTTP/gRPC、MCP、数据库或跨进程持久化。

| 不变量 | 约束 |
|---|---|
| 业务入口单源 | `Clak` 注册 `Script` 子类，TUI 与无头复用业务定义与输入校验 |
| 单次运行隔离 | 每次创建新的 Script、OutputView、Session 和 ExecList |
| 会话拥有进度 | 队列只通知执行事实，Session 统一管理步骤、时间与结果 |
| 视图不执行业务 | Runner 转发不可变快照，TUI 只更新界面与动画 |
| 取消不冒充强杀 | 当前同步调用返回后才能安全收尾，不宣称终止任意线程或子进程 |

## 2. 分层架构

```text
┌────────────────────────────────────────────────────────────────────────────┐
│ A. 调用接入层 Access                                                       │
│    项目 CLI：tui / exec · Python：run_cli / run_tui / run_line               │
├────────────────────────────────────────────────────────────────────────────┤
│ B. 应用与脚本层 Application                                                │
│    Clak：注册与查重 · SlashEngine：搜索/分发 · Script：业务步骤与输出          │
├────────────────────────────────────────────────────────────────────────────┤
│ C. 会话管理层 Session                                                      │
│    输入解析 · 问答挂起/恢复 · 生命周期 · 步骤进度 · 时间/结果 · 只读快照       │
├────────────────────────────────────────────────────────────────────────────┤
│ D. 顺序执行层 Execution                                                    │
│    ExecList：条件判断 → 执行 → 挂起/继续 · notify：只报告实际发生的事实         │
├────────────────────────────────────────────────────────────────────────────┤
│ E. 展示适配层 Adapters                                                     │
│    ScriptRunner：线程隔离、答案队列、事件投递 · HeadlessRun：纯文本与退出码     │
├────────────────────────────────────────────────────────────────────────────┤
│ F. 终端视图层 Terminal                                                     │
│    Textual · TuiState · 布局 · 历史/输入/问答/命令/步骤进度/底栏 · 颜色动画    │
└────────────────────────────────────────────────────────────────────────────┘
```

这是职责分层，不是严格的单向调用栈：展示适配器驱动会话，执行层通知会话，视图通过适配器提交答案或取消请求。

| 层 | 主要模块 | 拥有的职责 | 不承担 |
|---|---|---|---|
| A | [`cli.py`](../src/clak/cli.py)、[`application.py`](../src/clak/application.py) | 命令行参数与嵌入式入口 | 业务步骤、视图排版 |
| B | [`commands/types.py`](../src/clak/commands/types.py)、[`runtime/slash.py`](../src/clak/runtime/slash.py) | 脚本工厂、命令元数据、模糊搜索与分发 | 跨运行共享脚本实例 |
| C | [`runtime/session.py`](../src/clak/runtime/session.py)、[`runtime/ask/`](../src/clak/runtime/ask/) | 本次运行状态、问答、进度与终态快照 | 动画、Widget 操作 |
| D | [`runtime/exec_list.py`](../src/clak/runtime/exec_list.py) | 按序调用函数、检查条件、报告执行事实 | 保存会话进度或展示状态 |
| E | [`tui/runner.py`](../src/clak/tui/runner.py)、[`runtime/headless.py`](../src/clak/runtime/headless.py) | 驱动运行、跨线程事件、无头结果 | 再算一份业务进度 |
| F | [`tui/app.py`](../src/clak/tui/app.py)、[`tui/state.py`](../src/clak/tui/state.py)、[`tui/views/`](../src/clak/tui/views/) | 输入适配、快照缓存、布局与渲染 | 推断步骤是否完成 |

## 3. 入口、注册与公共接口

`Clak` 保存当前应用的命令集合；内置命令与业务注册项共同参与搜索和分发。注册时校验 slash 名称并拒绝重名，业务命令不会自动进入其他 `Clak` 实例或全局 `clak` 命令。

```text
项目入口 → Clak.register(Script类) → SlashEngine搜索/分发 → ScriptEntry.create()
                                                               ↓
                                                  一次运行专属的Script与OutputView
```

业务优先从 `clak` 顶层导入 `Clak`、`Script`、`Session`、`AskRequest`、`AskChoice`、`AskMode`、`AskAnswer`、`ScriptInputs`、`ScriptError`、`OutputView`、`FooterViewData`、`HeadlessRun`、`ScriptTester` 和 `ScriptRun`。

`clak.runtime.*` 与 `clak.tui.*` 是实现模块。下文的队列通知、状态枚举与快照结构用于理解和扩展框架，不要求普通脚本直接依赖它们。

## 4. 执行与进度的唯一事实来源

### 4.1 职责链

```text
ExecList 执行事实 → notify → Session 更新进度与会话状态
                                      ↓
                                SessionSnapshot
                                      ↓
                            ScriptRunner 跨线程转发
                                      ↓
                            TuiState 缓存 → 视图渲染
```

`ExecList` 不保存 `StepState`，也不生成界面进度。它通过 `ExecNotice` 报告注册、开始、返回、恢复、跳过、失败、重置与清空；事件携带步骤索引、名称和必要返回值。`Session` 订阅这些事实并维护唯一的步骤状态。

### 4.2 队列契约

| 操作 | 行为 |
|---|---|
| `add(can_do, task, name, *args)` | 添加步骤；条件为布尔值或无参函数，任务必须可调用 |
| 条件为假 | 标记跳过，继续下一项 |
| 任务返回 `0` 或空值 | 同步继续，不是进程退出码 |
| 任务返回非零 | 挂起，等待 `resume()`；不是业务失败 |
| `resume()` | 报告恢复并继续；挂起步骤由会话更新为完成 |
| `reset()` | 重置队列位置；未结束会话将步骤状态恢复为待执行 |
| `clear()` | 清空执行队列；会话结束清理时不丢失已保存的最终快照 |
| 任务内追加步骤 | 后续循环按当前队列长度继续，新增步骤可参与本次执行 |

使用底层 Session 时，应先 `bind_exec_end()`，再启动 `run()`；业务侧通常使用 `Script.run_steps()` 完成这两项操作。任务失败抛 `ScriptError`，参数错误抛 `ValueError`，不要把非零任务返回值当失败码。

### 4.3 快照与状态

| 数据 | 字段 | 含义 |
|---|---|---|
| `StepProgress` | `name`、`state` | 单步骤的不可变展示事实 |
| `ExecProgress` | `steps`、`current` | 全部步骤与当前零基索引；无当前项时为 `None` |
| `SessionSnapshot` | `state`、`progress`、`started_at`、`finished_at`、`request`、`result` | 会话运行状态、进度、单调时钟时间、待答请求与结果 |

`session.progress` 与 `session.snapshot` 返回只读快照；展示端不能通过修改它们控制执行。

| 状态集合 | 取值 |
|---|---|
| 会话状态 | `IDLE`、`RUNNING`、`AWAITING_INPUT`、`PAUSED`、`EXITED` |
| 会话结果 | `COMPLETED`、`FAILED`、`CANCELLED`；未定结果为 `None` |
| 步骤状态 | `PENDING`、`RUNNING`、`WAITING`、`COMPLETED`、`SKIPPED`、`FAILED`、`CANCELLED` |

```text
IDLE → RUNNING → EXITED
          ├→ AWAITING_INPUT → 提交并校验答案 → RUNNING
          └→ PAUSED → 恢复 → RUNNING
```

非零步骤不能提前标完成；问答恢复后才继续完成步骤。条件判断或任务异常归属当前步骤；答案回调异常也归属等待中的步骤。取消保留已完成项，未完成项标取消；队列随后清空，但最终进度继续存在。已结束会话不能用迟到的失败通知覆盖取消终态。

## 5. TUI 数据流与线程边界

### 5.1 运行链路

```text
按键/粘贴 → TuiState命令分发 → 创建ScriptRunner → Textual线程worker
                                                     ↓
                                      创建Script/OutputView/Session
                                                     ↓
                                       on_enter → run → 执行队列
                                                     ↓
输出/会话通知 → RunUpdate → Textual消息 → TuiState → 固定区域与日志刷新
```

TUI 每次只有一个活动脚本，未结束前拒绝重入。Script 构造、`on_enter()`、`run()`、步骤、答案回调和 `on_exit()` 串行运行在该工作线程；它们不应直接修改 Textual Widget。界面线程负责输入、历史、问答状态与渲染。

Runner 转发会话快照，不自行保存另一份步骤状态。输出通知与会话通知是独立事件：日志变化只更新文本，不能清除待答问题；消息合并不能用一条普通输出吞掉会话状态快照。

### 5.2 问答与输入

`AskRequest` 为不可变请求，包含 `field_id`、提示、默认值、候选与模式。模式支持单选、多选和过滤；候选值由统一解析器校验，只有带 `AskChoice(value=None)` 的单选允许自定义值。

```text
步骤请求输入 → Session保存请求/回调 → Runner等待答案队列
                                             ↑
界面提交 → 立即锁住本题 → 答案入队 → 同一worker校验与续跑
```

会话结束通知会唤醒等待中的 Runner，不靠定时轮询。直接从其他线程恢复执行仍需遵守 Session 的串行调用边界，不能并发修改队列。

Textual 的 Key/Paste/Resize 事件统一转换为内部事件。主输入粘贴保留文本并统一换行格式，不自动执行；提问的过滤或自定义输入合并为单行；普通候选不接收粘贴。

主输入的执行历史与日志历史独立，保存在当前 TuiState 中，不跨进程持久化。空输入按 `↑` 回填最近提交的命令，继续 `↑`/`↓` 浏览，`Enter` 再次执行；到达最新记录之后 `↓` 清空，`Esc` 取消浏览并清空，不恢复未提交草稿。历史回填时关闭命令候选，避免方向键被候选列表抢占；正常键入新命令时，方向键仍用于候选选择。模糊选择记录实际执行命令，空行和 Ask 答案不进入执行历史，`/clear` 只清日志，不清执行历史。

### 5.3 取消与清理

```text
Ctrl+C / 退出请求 → 设置取消信号 → 唤醒等待
                                     ↓
                         当前同步调用返回 → 停止后续步骤
                                     ↓
                            会话收尾 → Script.on_exit
                                     ↓
                      最终输出/快照 → 清空进度区或退出界面
```

界面不跨线程直接 `Session.cancel()` 清空正在遍历的队列。运行器在安全边界收尾，清理失败与输出渲染失败分别收集，保证最终完成事件仍能发送。退出请求等待安全清理；卸载路径只请求取消，不与业务并发清理。收到 Runner 的 `FINISHED` 后，TuiState 清除展示快照、标题与运行句柄，固定进度高度归零且动画停止；业务日志和错误进入历史。Session 自身仍保留最终只读快照，不因界面清理而删除事实。迟到的旧 Runner 消息因运行身份不匹配被忽略。

Python 不能安全强杀任意线程，工作线程取消也不等于终止 `subprocess.run()`。阻塞调用应设置超时或由业务管理进程终止；当前实现没有通用子进程托管 API。

## 6. 输出视图与扩展

每次 Script 构造独立的 `OutputView`，默认按行添加 `[脚本名] ` 前缀。`push()` 追加业务日志并主动通知展示端；TUI 保存输出镜像，结束后将内容保留在历史中。

| 接口 | 约定 |
|---|---|
| `Script.output_view` | 可替换为 OutputView 子类 |
| `render_lines()` | 返回当前展示文本的元组，不驱动执行、不修改 Widget |
| `notify_changed()` | 自定义内容变化后主动通知，无需伪造一条日志 |
| `set_change_callback()` | 展示端绑定的单一变化回调，在写入线程执行 |
| `on_enter(session)` / `on_exit()` | 与 Script 生命周期配对，不直接操作 Widget |

```python
from clak import OutputView


class SummaryOutput(OutputView):
    def __init__(self) -> None:
        super().__init__()
        self.summary = "等待结果"

    def update_summary(self, text: str) -> None:
        self.summary = text
        self.notify_changed()

    def render_lines(self) -> tuple[str, ...]:
        return (*super().render_lines(), f"{self.prefix}{self.summary}")
```

这用于业务专属的摘要或输出，不用于维护通用步骤计数；通用进度仍由 Session 管理。

## 7. 终端渲染与固定进度区

### 7.1 布局

```text
历史日志
固定步骤进度
命令候选（打开时）
主输入 或 Ask问答
底栏
```

布局基于当前终端列宽与行数计算。历史按显示列折行；输入维护原文本偏移，区分真实换行与软换行；裁切与填充复用 Rich 的列宽能力，不用 Python 字符长度代替终端宽度。

日志默认跟尾，向上查阅使用离底偏移；同宽新增输出补偿偏移保持阅读位置，回到底部后恢复跟尾。缩放后重新排版并约束滚动边界。

### 7.2 五项窗口与状态样式

| 项目 | 契约 |
|---|---|
| 标题 | 脚本名称随运行帧换色；耗时与 `step n/N` 元信息灰色，当前索引展示为一基编号 |
| 总数 | 所有注册步骤，包含提问、条件步骤和最终验证，不由示例另算 |
| 无队列脚本 | 只显示名称与时间，不虚构步数 |
| 步骤窗口 | 当前项附近固定五个真实步骤，首尾夹紧；不足五项时全部展示 |
| 完成项 | 仅 `✔` 使用 `PROGRESS_COMPLETED` 绿色 `#42c732`，步骤名称灰色并添加删除线，符号和空白不加删除线 |
| 未完成项 | 名称白色，当前运行名称加粗；当前方块固定 `PROGRESS_CURRENT` 黄绿 `#b8b72f`，不随动画变色 |
| 搜索命中 | 主输入命令菜单的命中字符使用 `COMMAND_MATCH` 黄绿 `#b8b72f`，与当前方块共享交互强调色 |
| 缩进 | 首个可见步骤前灰色 `└`，标记固定在第 5 列；独占行省略号与标记对齐 |
| 省略摘要 | 无隐藏项不显示；无隐藏完成项显示 `…`；否则 `… +N completed` |
| 摘要计数 | 只统计窗口外 `COMPLETED`，不计跳过、失败或取消 |
| 高度不足 | 放不下完整窗口则只显示标题摘要；恰好标题加五行时摘要并入标题 |
| 结束清理 | 完成、失败、停止收尾后自动清空固定进度区，历史只保留业务日志和错误 |

省略摘要不挤占五个步骤名额，进度不写入历史日志。极小终端优先保留输入和底栏，允许隐藏进度区。

### 7.3 动画

配色与时间参数集中在 `tui/theme.py`，视图不散落原始色值：

| 语义变量 | 用途 | 值 |
|---|---|---|
| `PROGRESS_PULSE_SHADOW` | 深棕红起点 | `#6d2a1c` |
| `PROGRESS_PULSE_BASE` | 砖红主色 | `#b8442a` |
| `PROGRESS_PULSE_ACCENT` | 暖橙强调 | `#e26b43` |
| `PROGRESS_PULSE_SOFT` | 柔和赭色 | `#d9875c` |
| `PROGRESS_PULSE_GLOW` | 浅棕高光 | `#cf9971` |
| `INTERACTION_HIGHLIGHT` | 当前方块与搜索命中的共同强调色 | `#b8b72f` |
| `PROGRESS_COMPLETED` | 完成对勾 | `#42c732` |
| `PROGRESS_PULSE_FRAMES` | 五色索引往返，末帧也完整停留 | `(0, 1, 2, 3, 4, 3, 2, 1, 0)` |
| `PROGRESS_ANIMATION_INTERVAL_SECONDS` | 每帧停留与刷新间隔 | `0.22` 秒 |
| `PROGRESS_PULSE_PERIOD_SECONDS` | 九帧完整周期，由帧数与间隔计算 | `1.98` 秒 |

- 标题名称与旋转标记共用九帧序列 `· ✢ ✶ ✳ ✻ ✳ ✶ ✢ ·`，每 0.22 秒切换一次，末帧回到起点后额外完整停留 0.22 秒
- 一轮共九个帧槽，包含回程与末帧停留，总周期为 `9 × 0.22 = 1.98` 秒；不再使用连续余弦或 RGB 插值
- 帧索引按会话单调时间计算，使用明确时间边界选择帧，不累计定时次数；各帧槽内部标记与标题样式不变化
- 仅运行与正在停止时播放；等待输入、挂起、完成、失败、取消时停止；结束清理规则不变
- 动画只影响展示，不追加日志、不执行步骤，不是业务心跳；当前方块保持固定强调样式
- 保留 Rich 前景样式，不强制背景；未完成名称白色、当前名称加粗、完成名称灰色删除线保持

测试不限制具体 HEX、色名、RGB 或主题数值；配色只在主题与设计文档维护。回归验证九帧顺序、0.22 秒帧槽、末帧停留、1.98 秒重复、静态状态、删除线/粗体、搜索命中样式差异与历史导航行为，调色不应要求修改测试色值。

## 8. 无头执行与错误边界

无头模式在调用线程同步执行，复用脚本定义、Session 和输入解析，不启动 TUI worker 或动画。

```text
exec /command → 参数解析 → SlashEngine → 创建Script与Session
                                             ↓
                          解析输入/默认值 → 执行 → HeadlessRun
                                                        ↓
                                             stdout/stderr + 退出码
```

| 情况 | 结果 |
|---|---|
| 正常业务执行 | 输出纯文本，退出码 `0` |
| `ScriptError` | 使用错误自带退出码，写入 stderr |
| 参数或候选值错误 | 退出码 `2`，写入 stderr |
| 提供部分字段却缺少其他必填字段 | 明确报错；`--use-defaults` 允许使用默认值 |
| 脚本仍在等待输入 | 返回缺失字段提示，不启动交互输入 |

TUI 能捕获并显示运行阶段未预期异常；无头适配器当前主要处理业务与输入异常，不应把两端所有异常或收尾细节宣称为完全一致。普通业务脚本应使用 `run_steps()` 绑定正常完成清理，并给外部调用设置超时。

## 9. 验证策略

| 层次 | 重点 | 代表测试 |
|---|---|---|
| 执行事实与会话 | 正常、条件跳过、挂起/恢复、动态追加、取消终态 | [`test_exec_progress.py`](../tests/test_exec_progress.py)、[`test_exec_list.py`](../tests/test_exec_list.py) |
| 业务脚本 | 参数校验、成功/失败、服务器快照、输出降噪 | [`test_verify_release.py`](../tests/test_verify_release.py)、[`test_pack_game_res.py`](../tests/test_pack_game_res.py) |
| 线程与生命周期 | 界面响应、问答同线程恢复、错误隔离、清理与退出 | [`test_tui_runner.py`](../tests/test_tui_runner.py)、[`test_tui_shutdown.py`](../tests/test_tui_shutdown.py) |
| 纯视图 | 五项窗口、隐藏完成统计、删除线、确定性九帧节拍 | [`test_progress_view.py`](../tests/test_progress_view.py) |
| 终端集成 | 缩放、窄屏、输入光标、动画不污染日志 | [`test_progress_integration.py`](../tests/test_progress_integration.py)、[`test_terminal_width.py`](../tests/test_terminal_width.py) |

测试采用先失败再修复；耗时业务测试可替换等待函数，不为生产代码增加测试专用模式。测试源码导航面向完整仓库，源码发行包默认不包含 `tests/`；测试命令见 [开发验证](../README.md#开发验证)。

## 10. 文档与发布

| 资产 | 职责与同步时点 |
|---|---|
| [AGENTS](../AGENTS.md) | 项目维护流程与授权边界，规则变化时更新 |
| 本文 | 设计原则与技术契约，代码修改时同轮核对并同步 |
| [README](../README.md) | 面向未参与项目的开发者快速入门，与代码行为同步 |
| [示例说明](../examples/dev_tools/README.md) | 业务场景与手动验收，随示例代码同步 |
| [skills/clak](../skills/clak/SKILL.md) | 面向 Agent 使用 esclak 编写工具，仅提交阶段同步 |
| [docs/task.md](task.md) | task-polling 唯一任务状态源，修改完成并验证后记录理解与真实改动目录 |
| [CHANGELOG](../CHANGELOG.md) | 仅发版时根据对应范围内已完成任务、代码差异与验证结果整理 |

```text
修改代码 → 同步设计与使用说明 → 验证 → 记录任务完成
                                           ↓
                              提交时同步skill → 发版时整理CHANGELOG
```

任务记录不是提交或发布证明，不补造历史轮次；任务完成记录应保留作为后续发版回顾。完整任务流转、混合工作区和提交/发版规则见 [维护指南](../AGENTS.md)。新增框架行为不得只改代码不更新设计原则，也不要将实现细节重新堆回 README。

版本真源为 `src/clak/__init__.py` 的 `__version__`，Hatch 通过 `pyproject.toml` 动态读取；源码包包含本技术文档，wheel 仅打包 `src/clak`。本文中的任务与 skill 链接面向完整仓库，不表示二进制包内含全部维护资产。
