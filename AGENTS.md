# AGENTS.md — 接入 Script 指南

给 AI agent 的工作指南：把散落的游戏脚本接入 clak 框架。

## 何时接入

满足任一即接入 clak：

- 有固定流程（多步骤、有顺序依赖）
- 需要人工确认参数（版本号、目标服务器、打包配置）
- 需要 TUI 交互 + 无头批量执行两种模式
- 当前是裸脚本/Shell，想统一管理

纯一次性命令、无参数、无流程 → 不接入，写普通函数即可。

## 接入流程

### 1. 在 `src/clak/scripts/` 新建模块

文件名非下划线开头（`_registry.py` 等被扫描跳过）。一个脚本一个文件。

### 2. 用 `@script` 装饰 `run` 函数

```python
# src/clak/scripts/my_script.py
from clak.runtime.ask import AskAnswer, AskChoice, AskRequest
from clak.runtime.session import ScriptSession
from clak.scripts import script


@script("/my-script", "脚本说明（TUI 菜单展示）")
def run(session: ScriptSession) -> None:
    state = {"field": ""}

    def step_ask() -> int:
        def on_answer(answer: AskAnswer) -> None:
            state["field"] = answer.primary
            session.log(f"已选: {state['field']}")
        return session.ask_step(
            AskRequest(
                field_id="field",
                prompt="选择字段",
                default="x",
                choices=(AskChoice(label="X", value="x"),),
            ),
            on_answer,
        )

    def step_done() -> int:
        session.log(f"my-script: 完成 ({state['field']})")
        return 0

    step_list = session.step_list
    session.bind_step_end()
    step_list.clear()
    step_list.add(True, step_ask, "ask")
    step_list.add(True, step_done, "done")
    session.run()
```

### 3. 验证

```bash
# 无头：缺参报错
python3 -m clak exec /my-script
# 无头：补参执行
python3 -m clak exec /my-script --set field=x
# 无头：用默认值批量
python3 -m clak exec /my-script --use-defaults
# TUI 交互
python3 -m clak
# 然后输入 /my-script
```

### 4. 写测试

参考 `tests/test_pack_game_res.py`：

```python
from clak.runtime.params import ScriptInputs
from clak.runtime.session import ScriptSession
from clak.scripts.my_script import run


def test_my_script_prefill():
    logs: list[str] = []
    inputs = ScriptInputs.from_pairs({"field": "x"}, allow_defaults=False)
    run(ScriptSession(logs.append, inputs=inputs))
    assert any("x" in line for line in logs)
    assert any("完成" in line for line in logs)
```

## ScriptSession 接口

| API | 作用 | 返回 |
|---|---|---|
| `session.step_list.add(can_do, run, name)` | 加步骤 | — |
| `session.ask_step(AskRequest, on_answer)` | 挂起等输入 | `1` 暂停 / `0` 已补参直接答 |
| `session.bind_step_end()` | 绑定结束回调 | **脚本入口必调** |
| `session.run()` | 启动执行 | — |
| `session.log(msg)` | 输出到 history | — |
| `session.cancel()` | 中断脚本 | — |
| `session.provide_input(field, wire)` | 外部补参（框架用，脚本别调） | — |

**步骤函数 `run` 返回值**：`0` 同步继续下一步，非 0 暂停直至 `resume`（ask_step 已处理）。

## 常见模式

### 无 ask 的纯流程

```python
@script("/clean-cache", "清理缓存")
def run(session: ScriptSession) -> None:
    def step_clean() -> int:
        session.log("clean-cache: 清理中")
        # 实际清理逻辑
        session.log("clean-cache: 完成")
        return 0
    step_list = session.step_list
    session.bind_step_end()
    step_list.clear()
    step_list.add(True, step_clean, "clean")
    session.run()
```

### 单选 ask

```python
AskRequest(
    field_id="env",
    prompt="选择环境",
    default="dev",
    choices=(
        AskChoice(label="开发", value="dev"),
        AskChoice(label="生产", value="prod"),
    ),
)
# answer.primary == "dev" / "prod"
```

### 多选 ask

```python
from clak.runtime.ask import AskMode

AskRequest(
    field_id="targets",
    prompt="选择目标（可多选）",
    default="base,cn",
    choices=(AskChoice(label="Base", value="base"), AskChoice(label="中文", value="cn")),
    mode=AskMode.MULTI,
)
# answer.tokens == frozenset({"base", "cn"})
# answer.text == "base,cn"（已排序）
```

### 自定义输入行

```python
AskRequest(
    field_id="version",
    prompt="版本号",
    default="2026-01-01",
    choices=(
        AskChoice(label="2026-01-01", value="2026-01-01"),
        AskChoice(label="输入其他版本", value=None),  # value=None 即自定义输入
    ),
)
# 用户选自定义行可输入任意值，answer.primary 是输入内容
```

### fzf 式过滤单选

```python
from clak.runtime.ask import AskMode

AskRequest(
    field_id="server",
    prompt="选择服务器（输入过滤）",
    default="dev",
    choices=tuple(server_choices()),  # 候选多时用 FILTER
    mode=AskMode.FILTER,
)
# 输入字符按 subsequence 过滤候选，↑↓ 在过滤后列表移动，Enter 确认
# answer.primary == 选中项的 value（或 label）
```

### 步骤条件跳过

```python
def step_optional() -> int:
    if not state["need_x"]:
        return 0  # 跳过本步，继续下一步
    # ... 执行
    return 0

step_list.add(state["need_x"], step_optional, "optional")  # can_do 控制是否执行
```

## 禁止事项

- **不要改 `commands/_registry.py`**：脚本通过 `@script` 自动注册，加文件即生效
- **不要在脚本里调 `session.provide_input`**：那是框架给 TUI/headless 补参用的
- **不要硬编码 `COMMAND` 实例**：`@script` 装饰器已生成 `ScriptEntry` 并注册
- **不要在 `scripts/` 放非脚本模块**：扫描会尝试 import，非脚本文件用 `_` 前缀（如 `_helpers.py`）
- **不要跨脚本共享状态**：每个 `run` 是独立会话，状态用闭包 `state` dict 或 dataclass 承载

## 框架边界

- `runtime/`：执行引擎（`session`/`step_list`/`params`/`headless`/`slash`/`ask`）——脚本只读用，不改
- `commands/`：纯 slash 元命令（version/status/clear/quit）——业务脚本不进这里
- `scripts/`：业务脚本——**你只动这里**
- `tui/`：渲染层——脚本不碰

依赖链单向：`scripts → runtime`（拿数据结构和执行器），`commands/_registry → scripts/_registry`（聚合），`runtime/slash → commands/_registry`（分发）。

## 验证清单

接入一个脚本前确认：

- [ ] 文件在 `src/clak/scripts/` 下，文件名非下划线开头
- [ ] `@script("/xxx", "说明")` 装饰 `run`，slash 名带斜杠
- [ ] `run(session)` 签名，内部 `bind_step_end()` + `step_list.clear()` + `add(...)` + `session.run()`
- [ ] `ask_step` 的 `field_id` 唯一，`on_answer` 回调更新 state
- [ ] `python3 -m clak exec /xxx` 缺参报错码 2
- [ ] `python3 -m clak exec /xxx --set field=v` 执行成功
- [ ] TUI 里 `/xxx` 能交互
- [ ] 写了测试，`python3 -m pytest` 全绿
