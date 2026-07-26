from clak.runtime.step_list import StepList


def test_step_list_runs_sync_steps_in_one_execute():
    order: list[str] = []
    exe = StepList()
    exe.add(True, lambda: order.append("a") or 0, "a")
    exe.add(True, lambda: order.append("b") or 0, "b")
    exe.execute()
    assert order == ["a", "b"]
    assert exe.is_finished


def test_step_list_pauses_until_resume():
    order: list[str] = []
    exe = StepList()

    def pause() -> int:
        order.append("wait")
        return 1

    exe.add(True, pause, "pause")
    exe.add(True, lambda: order.append("after") or 0, "after")
    exe.execute()
    assert order == ["wait"]
    assert exe.is_waiting
    exe.resume()
    assert order == ["wait", "after"]
    assert exe.is_finished


def test_step_list_end_callback():
    ended: list[str] = []
    exe = StepList()
    exe.set_end_callback(lambda: ended.append("done"))
    exe.add(True, lambda: 0, "only")
    exe.execute()
    assert ended == ["done"]
