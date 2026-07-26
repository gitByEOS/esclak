from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from clak_py.runtime.ask import AskAnswer, AskChoice, AskMode, AskRequest
from clak_py.runtime.session import ScriptSession
from clak_py.scripts import script

PACK_TARGET_DEFAULT = "base,cn"


def default_pack_version() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def pack_target_choices() -> tuple[AskChoice, ...]:
    return (
        AskChoice(label="Base 资源", value="base"),
        AskChoice(label="iOS", value="ios"),
        AskChoice(label="Windows", value="win"),
        AskChoice(label="简体中文", value="cn"),
        AskChoice(label="English", value="en"),
        AskChoice(label="Deutsch", value="de"),
    )


@dataclass
class PackState:
    version: str = ""
    targets: frozenset[str] | None = None


def build_pack_game_res_exec(session: ScriptSession, state: PackState) -> None:
    step_list = session.step_list

    def step_ask_version() -> int:
        if state.version:
            return 0

        def on_answer(answer: AskAnswer) -> None:
            state.version = answer.primary
            session.log(f"使用版本号: {state.version}")

        default = default_pack_version()
        return session.ask_step(
            AskRequest(
                field_id="version",
                prompt="资源包版本号",
                default=default,
                choices=(
                    AskChoice(label=default, value=default),
                    AskChoice(label="输入其他版本", value=None),
                ),
            ),
            on_answer,
        )

    def step_ask_targets() -> int:
        if state.targets is not None:
            return 0

        def on_answer(answer: AskAnswer) -> None:
            state.targets = answer.tokens
            session.log(f"打包目标: {answer.text}")

        return session.ask_step(
            AskRequest(
                field_id="targets",
                prompt="选择打包目标（可多选）",
                default=PACK_TARGET_DEFAULT,
                choices=pack_target_choices(),
                mode=AskMode.MULTI,
            ),
            on_answer,
        )

    def step_pack() -> int:
        version = state.version or default_pack_version()
        targets = ",".join(sorted(state.targets or frozenset(PACK_TARGET_DEFAULT.split(","))))
        session.log(f"pack-game-res: 开始打包 {version} [{targets}]")
        session.log(f"pack-game-res: 完成 {version} [{targets}]")
        return 0

    def step_finished() -> int:
        version = state.version or "?"
        targets = ",".join(sorted(state.targets or frozenset(PACK_TARGET_DEFAULT.split(","))))
        session.log(f"pack-game-res: 全部结束 ({version} / {targets})")
        return 0

    step_list.clear()
    step_list.add(True, step_ask_version, "ask_version")
    step_list.add(True, step_ask_targets, "ask_targets")
    step_list.add(True, step_pack, "pack")
    step_list.add(True, step_finished, "finished")


@script("/pack-game-res", "打包游戏资源（版本号 + 多选目标）")
def run(session: ScriptSession) -> None:
    state = PackState()
    session.bind_step_end()
    build_pack_game_res_exec(session, state)
    session.run()
