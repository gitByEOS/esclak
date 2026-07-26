# clak

固定流程脚本 TUI 与无头执行（`StepList` + `ScriptSession`）。

CLAK = **C**ommand-**L**ine **A**utomation **K**it。

## 能力

- history / slash 菜单 / 多行输入 / context / ask（单选、多选、过滤）
- `/` 补全
- 脚本：`/pack-game-res`（版本 + 打包目标）、`/select-server`（目标服务器）
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
uv run clak exec /pack-game-res --set version=1.0 --set targets=base,cn
```

### 不用 uv（pip + python）

```bash
pip install -e .                         # 装依赖 + 入口命令
python -m clak                        # 打开 TUI
python -m clak exec /version
python -m clak exec /pack-game-res --use-defaults
```

若依赖已装（`pip install textual wcwidth`），可直接跑无需安装：

```bash
python3 -m clak                       # 直接运行
python3 -m clak exec /version
python3 -m pytest                        # 跑测试
```

入口命令：`clak`（pip install 后可用）。PyPI 包名为 `esclak`（绕开 `clack` 相似性），import 名为 `clak`（`from clak... import`）。

```bash
pip install esclak                            # 装包，得到 clak 命令
```

## 构建单文件二进制（组内分发）

无需 Python 环境即可分发，用 pyinstaller 打成单文件：

```bash
./build.sh                               # 产出上级目录的 clak 二进制
```

部署到游戏代码仓库时，目录约定：

```
tools/
├── clak_src/                            # clak 源码（入库）
│   ├── build.sh
│   └── src/...
└── clak                                 # 构建产物（gitignore，不入库）
```

组员拉代码后，在 `tools/clak_src/` 执行 `./build.sh` 即生成 `tools/clak`，直接 `./tools/clak` 使用。

> 跨平台需分别构建：macOS 上构建得到 macOS 二进制，Linux 同理。onefile 模式首次启动会解压到临时目录，约慢几百毫秒。

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

## 测试

```bash
python -m pytest                    # 或 uv run pytest
```

测试覆盖：reducer、headless、pack_game_res、select_server、ask（view/multi/navigation）、view_lifecycle、tui_script、exec_list、key_from_textual。
