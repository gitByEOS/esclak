import pytest

from clak import OutputView, Session
from clak.runtime.exec_list import ExecList, ExecNoticeKind
from clak.runtime.progress import StepState


def states(session):
    return tuple(step.state for step in session.progress.steps)


def test_queue_notifies_facts_and_session_owns_progress():
    queue = ExecList()
    notices = []
    queue.set_notify(notices.append)
    queue.add(True, lambda: 0, "配置")
    queue.execute()
    assert [notice.kind for notice in notices] == [
        ExecNoticeKind.REGISTERED, ExecNoticeKind.STARTED, ExecNoticeKind.RETURNED,
    ]
    assert not hasattr(queue, "progress")


def test_session_manages_completed_and_skipped_states():
    session = Session(OutputView())
    snapshots = []
    session.set_change_callback(snapshots.append)
    session.exec_list.add(True, lambda: 0, "检查配置")
    session.exec_list.add(False, lambda: 0, "检查可选资源")
    session.run()
    assert states(session) == (StepState.COMPLETED, StepState.SKIPPED)
    assert any(snapshot.progress.steps[0].state == StepState.RUNNING for snapshot in snapshots)
    assert session.progress.current == 1


def test_nonzero_step_stays_waiting_until_resume():
    session = Session(OutputView())
    session.exec_list.add(True, lambda: 1, "选择目标")
    session.exec_list.add(True, lambda: 0, "检查目标")
    session.run()
    assert states(session) == (StepState.WAITING, StepState.PENDING)
    assert session.progress.current == 0
    session.exec_list.resume()
    assert states(session) == (StepState.COMPLETED, StepState.COMPLETED)


@pytest.mark.parametrize("is_condition", [False, True])
def test_failed_condition_or_task_marks_current_step(is_condition):
    session = Session(OutputView())

    def fail():
        raise RuntimeError("检查失败")

    session.exec_list.add(fail if is_condition else True, (lambda: 0) if is_condition else fail, "检查")
    with pytest.raises(RuntimeError, match="检查失败"):
        session.run()
    assert states(session) == (StepState.FAILED,)


def test_cancel_preserves_completed_and_cancels_unfinished_after_queue_clear():
    session = Session(OutputView())
    session.exec_list.add(True, lambda: 0, "配置")
    session.exec_list.add(True, lambda: 1, "等待")
    session.exec_list.add(True, lambda: 0, "发布")
    session.run()
    session.cancel()
    assert states(session) == (StepState.COMPLETED, StepState.CANCELLED, StepState.CANCELLED)
    assert session.exec_list.is_finished


def test_step_can_append_work_while_session_is_running():
    session = Session(OutputView())
    session.bind_exec_end()
    executed = []

    def append() -> int:
        session.exec_list.add(True, lambda: executed.append("新增") or 0, "新增")
        return 0

    session.exec_list.add(True, append, "初始")
    session.run()
    assert executed == ["新增"]
    assert states(session) == (StepState.COMPLETED, StepState.COMPLETED)
    assert session.is_exited


def test_step_can_cancel_session_without_overwriting_terminal_result():
    session = Session(OutputView())
    session.bind_exec_end()
    session.exec_list.add(True, lambda: session.cancel() or 0, "停止")
    session.exec_list.add(True, lambda: pytest.fail("不应执行"), "后续")
    session.run()
    assert states(session) == (StepState.CANCELLED, StepState.CANCELLED)
    from clak.runtime.session import SessionResult
    assert session.snapshot.result == SessionResult.CANCELLED
    session.fail()
    assert session.snapshot.result == SessionResult.CANCELLED


def test_reset_clear_and_dynamic_add_are_managed_by_session():
    session = Session(OutputView())
    session.exec_list.add(True, lambda: 0, "配置")
    session.run()
    session.exec_list.add(True, lambda: 0, "资源")
    assert states(session) == (StepState.COMPLETED, StepState.PENDING)
    session.exec_list.reset()
    assert states(session) == (StepState.PENDING, StepState.PENDING)
    assert session.progress.current is None
    session.exec_list.clear()
    assert session.progress.steps == ()
