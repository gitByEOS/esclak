from __future__ import annotations

import argparse
import sys

from clak_py.runtime.headless import HeadlessError, emit, run_line
from clak_py.tui.app import run_tui


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clak-py", description="固定流程脚本 TUI")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("tui", help="打开交互 TUI（默认）")

    exec_parser = sub.add_parser("exec", help="无头执行一条 slash 或 prompt")
    exec_parser.add_argument(
        "line",
        help='要执行的行，例如 "/version" 或 "/pack-game-res"',
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


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command

    if command == "exec":
        from clak_py.runtime.params import ScriptInputs

        try:
            inputs = ScriptInputs.parse_set_flags(
                args.set,
                allow_defaults=args.use_defaults or not args.set,
            )
            run = run_line(args.line, script_inputs=inputs)
        except (HeadlessError, ValueError) as error:
            print(f"clak-py: {error}", file=sys.stderr)
            code = error.code if isinstance(error, HeadlessError) else 2
            raise SystemExit(code) from error
        raise SystemExit(emit(run))

    if command in (None, "tui"):
        run_tui()
        return

    parser.error(f"未知子命令: {command}")
