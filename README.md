<div align="center">
  <a name="readme-top"></a>

<img src="docs/images/logo.svg" alt="esclak" width="240" />

[![][license-shield]][license-link]
[![][pypi-shield]][pypi-link]

</div>

# clak

固定流程脚本 TUI 与无头执行（`StepList` + `ScriptSession`）。

CLAK = **C**ommand-**L**ine **A**utomation **K**it。

## 能力

- history / slash 菜单 / context / ask（单选、多选、过滤）
- `/` 补全
- 无头：`clak exec /pack-game-res --use-defaults` 或 `--set field=value`

## 目录结构

```
src/clak/
├── cli.py                          # argparse 入口
├── runtime/                        # 脚本运行时（与 UI 解耦）
│   ├── step_list.py                # 步骤执行器
│   ├── session.py                  # 会话 + ask 网关
│   ├── params.py                   # 无头 --set 参数
│   ├── headless.py                 # 无头执行入口
│   ├── slash.py                    # SlashEngine 分发
│   └── ask/                        # ask 协议（request/answer）
├── commands/                       # 纯 slash 命令
│   ├── types.py                    # SlashCommand / ScriptEntry / SlashEntry
│   ├── _registry.py                # 聚合 builtin + 脚本
│   └── version/status/clear/quit.py
├── scripts/                        # 业务脚本（自动发现）
│   ├── _registry.py                # @script 装饰器 + 扫描注册
│   └── pack_game_res/select_server.py
└── tui/                            # 渲染层
    ├── app.py / state.py / event.py / theme.py / screen.py
    └── views/                      # 渲染单元平铺
```

依赖链单向：`tui → runtime/slash → commands/_registry → scripts/_registry → runtime`（数据结构）。

## 安装与运行

需要 Python ≥ 3.10。依赖 `textual` + `wcwidth`。

### 用 uv

```bash
uv sync
uv run clak                          # 打开 TUI
uv run clak exec /version             # 无头执行
uv run pytest                         # 跑测试
```

### 不用 uv（pip + python）

```bash
pip install esclak                    # 装包，得到 clak 命令
clak                                  # 打开 TUI
clak exec /version                    # 无头执行
python -m pytest                      # 跑测试
```

## 无头执行

```bash
clak exec /<script> [--set field=value ...] [--use-defaults]
```

- `--set version=1.0`：传入脚本参数（可重复）
- `--use-defaults`：未 `--set` 的 ask 字段用 `AskRequest.default`，无交互批量执行
- 缺参且未开 `--use-defaults` 时报错退出码 2

## 扩展脚本

在 `src/clak/scripts/` 新建模块，用 `@script` 装饰器注册，启动时自动扫描，**无需改框架任何文件**：

```python
# scripts/my_script.py
from clak.runtime.ask import AskChoice, AskMode, AskRequest
from clak.runtime.session import ScriptSession
from clak.scripts import script


@script("/my-script", "我的脚本说明")
def run(session: ScriptSession) -> None:
    state = {"name": ""}

    def step_ask_name() -> int:
        def on_answer(answer) -> None:
            state["name"] = answer.primary
            session.log(f"已选: {state['name']}")

        return session.ask_step(
            AskRequest(
                field_id="name",
                prompt="选择名称",
                default="default",
                choices=(AskChoice(label="默认", value="default"),),
            ),
            on_answer,
        )

    def step_done() -> int:
        session.log(f"my-script: 完成 ({state['name']})")
        return 0

    step_list = session.step_list
    session.bind_step_end()
    step_list.clear()
    step_list.add(True, step_ask_name, "ask_name")
    step_list.add(True, step_done, "done")
    session.run()
```

加完即可用：`clak exec /my-script --set name=default`。

## 扩展 slash 命令（非脚本）

在 `src/clak/commands/` 新建模块，定义 `COMMAND = SlashCommand(...)`，加入 `commands/_registry.py` 的 `_BUILTINS`。

## 许可

[MIT](LICENSE)

<!-- 徽章引用 -->

[license-shield]: https://img.shields.io/badge/license-MIT-blue.svg
[license-link]: LICENSE
[pypi-shield]: https://img.shields.io/pypi/v/esclak.svg
[pypi-link]: https://pypi.org/project/esclak/
