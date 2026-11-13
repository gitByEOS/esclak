from threading import Event

from clak import OutputView, Session


def test_cancellation_stops_following_steps_without_early_cleanup():
    is_cancelled = Event()
    order: list[str] = []
    session = Session(OutputView(), is_cancelled=is_cancelled.is_set)
    session.on_exit(lambda: order.append("清理"))
    session.bind_exec_end()

    def execute() -> int:
        order.append("开始")
        is_cancelled.set()
        order.append("当前步骤结束")
        return 0

    session.exec_list.add(True, execute, "execute")
    session.exec_list.add(True, lambda: order.append("不应执行") or 0, "after")
    session.run()
    session.cancel()
    session.cancel()
    assert order == ["开始", "当前步骤结束", "清理"]


def test_cancellation_before_run_does_not_execute_a_step():
    order: list[str] = []
    session = Session(OutputView(), is_cancelled=lambda: True)
    session.exec_list.add(True, lambda: order.append("不应执行") or 0, "execute")
    session.run()
    assert order == []
