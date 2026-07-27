from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from clak.application import Clak
from clak.runtime.headless import HeadlessError, emit, run_line
from clak.tui.app import run_tui


def build_parser(*, prog: str = "clak") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog, description="固定流程脚本 TUI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("tui", help="打开交互 TUI（默认）")

    exec_parser = sub.add_parser("exec", help="无头执行一条 slash 或 prompt")
    exec_parser.add_argument(
        "line",
        help='要执行的行，例如 "/version"',
    )
    exec_parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="FIELD=VALUE",
        help="脚本参数（可重复），如 --set version=1.0 --set targets=base,cn",
    )
    exec_parser.add_argument(
        "--use-defaults",
        action="store_true",
        help="未 --set 的 ask 字段使用 AskRequest.default（无交互批量）",
    )
    return parser


def run_app_cli(
    app: Clak,
    argv: Sequence[str] | None = None,
    *,
    prog: str | None = None,
) -> None:
    """运行已注册业务脚本的应用 CLI。exec 会以运行结果退出。"""
    parser = build_parser(prog=prog or "clak")
    args = parser.parse_args(argv)
    command = args.command

    if command == "exec":
        from clak.runtime.params import ScriptInputs

        try:
            inputs = ScriptInputs.parse_set_flags(
                args.set,
                allow_defaults=args.use_defaults or not args.set,
            )
            run = run_line(args.line, script_inputs=inputs, app=app)
        except (HeadlessError, ValueError) as error:
            print(f"clak: {error}", file=sys.stderr)
            code = error.code if isinstance(error, HeadlessError) else 2
            raise SystemExit(code) from error
        raise SystemExit(emit(run))

    if command in (None, "tui"):
        run_tui(app)
        return

    parser.error(f"未知子命令: {command}")


def main(argv: Sequence[str] | None = None) -> None:
    """clak 自带入口只包含内置命令；业务项目应调用 app.run_cli()。"""
    run_app_cli(Clak(), argv=argv, prog="clak")
