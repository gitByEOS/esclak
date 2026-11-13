# Changelog

## 0.2.0 — 2026-11-13

- 新增 TUI 后台执行与安全停止
- 新增 会话步骤进度、五项窗口、完成项删除线与结束清理
- 新增 九帧进度动画，每帧 0.22 秒，总周期 1.98 秒
- 新增 主输入执行历史，支持上下浏览、回车执行和 Esc 取消
- 修复 粘贴、日志跟尾、翻页、中文列宽与输入光标
- 修复 生命周期异常清理、动态追加步骤与挂起恢复
- 修复 `ScriptTester` 未保留业务自定义退出码

## 0.1.0 — 2026-07-27

- 修改 `ExecList.add` 非法 `can_do`/`run` 改抛 `TypeError`
- 修改 `ExecList._later` 在 `delay > 0` 且无 delay_runner 时抛 `RuntimeError`
- 新增 `ScriptTester` / `ScriptRun` 测试类
- 新增 `Script.add_step` / `ask_tool` / `run_steps` 

## 0.0.6 — 2026-07-27

- 新增 `examples/dev_tools` 完整示例，覆盖 TUI、无头执行、动态状态、输入校验、子进程和资源清理
- 新增 命令菜单使用子序列模糊匹配
- 新增 脚本输出按行增加 `[script-name] ` 前缀
- 提高 TUI 不再被强制为黑底

## 0.0.5 — 2026-07-26

### 核心

- 新增 `Clak` 应用容器：`register` 注册脚本/slash 命令，`run_line` 无头执行，`run_tui` 打开交互界面，`run_cli` 项目入口
- 新增 `Script` 基类：`name`/`description`/`aliases`/`output_view` 类属性，`on_enter`/`on_exit` 生命周期钩子，`run` 入口
- 新增 `Session` 运行时：`exec_list` 执行队列，`ask_step` 交互提问，`provide_input` 续跑，`cancel` 中断，`on_exit` 完成回调
- 新增 `ExecList` 顺序执行队列：任务返回 `0` 同步继续，非 `0` 挂起直至 `resume`；
- 新增 `AskRequest`/`AskChoice`/`AskMode`/`AskAnswer` 交互模型：单选 `SINGLE`、多选 `MULTI`、过滤 `FILTER`；`AskChoice(value=None)` 允许候选外自定义输入
- 新增 `ScriptInputs` 输入解析：`from_pairs`、`parse_set_flags`（`--set field=value`）、`resolve_wire`、`allow_defaults`
- 新增 `SlashCommand` 纯 slash 命令：只分发不跑脚本
- 新增 内置命令：`/version`、`/status`、`/clear`、`/quit`
- 新增 `HeadlessRun` 无头执行结果
- 新增 `tui` 子命令（默认）、`exec` 子命令（`--set`/`--use-defaults`）
- 新增 交互 TUI：命令菜单、history 视图、ask 控制器、footer、screen、theme
- 新增 `OutputView` 脚本专属输出视图，`push` 按行追加，`render_lines` 渲染