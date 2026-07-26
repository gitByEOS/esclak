from __future__ import annotations

from dataclasses import dataclass

from clak_py.runtime.ask import AskAnswer, AskChoice, AskMode, AskRequest
from clak_py.runtime.session import ScriptSession
from clak_py.scripts import script

SERVER_DEFAULT = "dev"


def server_choices() -> tuple[AskChoice, ...]:
    return (
        AskChoice(label="开发 dev", value="dev"),
        AskChoice(label="预发 staging", value="staging"),
        AskChoice(label="生产 prod", value="prod"),
        AskChoice(label="国服 cn", value="cn"),
        AskChoice(label="海外 global", value="global"),
        AskChoice(label="开发-亚洲 dev-asia", value="dev-asia"),
        AskChoice(label="开发-欧洲 dev-eu", value="dev-eu"),
        AskChoice(label="预发-亚洲 staging-asia", value="staging-asia"),
        AskChoice(label="生产-国服 prod-cn", value="prod-cn"),
        AskChoice(label="生产-海外 prod-global", value="prod-global"),
    )


@dataclass
class SelectServerState:
    server: str = ""


def build_select_server_exec(session: ScriptSession, state: SelectServerState) -> None:
    step_list = session.step_list

    def step_ask_server() -> int:
        if state.server:
            return 0

        def on_answer(answer: AskAnswer) -> None:
            state.server = answer.primary
            session.log(f"已选服务器: {state.server}")

        return session.ask_step(
            AskRequest(
                field_id="server",
                prompt="选择目标服务器（输入过滤）",
                default=SERVER_DEFAULT,
                choices=server_choices(),
                mode=AskMode.FILTER,
            ),
            on_answer,
        )

    def step_apply() -> int:
        server = state.server or SERVER_DEFAULT
        session.log(f"select-server: 切换上下文 → {server}")
        return 0

    def step_finished() -> int:
        server = state.server or SERVER_DEFAULT
        session.log(f"select-server: 完成 ({server})")
        return 0

    step_list.clear()
    step_list.add(True, step_ask_server, "ask_server")
    step_list.add(True, step_apply, "apply")
    step_list.add(True, step_finished, "finished")


@script("/select-server", "选择目标服务器（fzf 式过滤）")
def run(session: ScriptSession) -> None:
    state = SelectServerState()
    session.bind_step_end()
    build_select_server_exec(session, state)
    session.run()
