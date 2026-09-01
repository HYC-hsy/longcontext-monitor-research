import threading
import time

import pytest

from test_monitor_agent import PersistentSequenceClient, Response
from monitor_agent import MonitorAction, MonitorAgent, MonitorWorkspace
from monitor_controller import MonitorController


def test_publish_never_waits_for_blocked_monitor():
    entered = threading.Event()
    release = threading.Event()

    def review(context, completion_pending):
        entered.set()
        release.wait(2)
        return MonitorAction("wait", {"after_turns": 3})

    controller = MonitorController(review)
    controller.start()
    started = time.monotonic()
    assert controller.initialize("turn zero") is True
    assert entered.wait(1)
    assert controller.publish_cursor(1, "cursor 1") is False
    assert time.monotonic() - started < 0.2
    release.set()
    receipt = controller.get_receipt(timeout=1)
    controller.stop()

    assert receipt.action["kind"] == "wait"
    assert controller.failures == []


def test_wait_uses_model_selected_cursor_distance():
    calls = []

    def review(context, completion_pending):
        calls.append(context)
        return MonitorAction("wait", {"after_turns": 3})

    controller = MonitorController(review)
    controller.start()
    assert controller.initialize("init")
    controller.get_receipt(timeout=1)

    assert controller.publish_cursor(1, "one") is False
    assert controller.publish_cursor(2, "two") is False
    assert controller.publish_cursor(3, "three") is True
    controller.get_receipt(timeout=1)
    controller.stop()

    assert calls == ["init", "three"]


def test_intervention_enters_close_watch_until_monitor_waits():
    actions = iter([
        MonitorAction("intervene", {"message": "Correct the mistaken test oracle."}),
        MonitorAction("wait", {"after_turns": 4}),
    ])
    delivered = []
    controller = MonitorController(lambda *_: next(actions), on_intervention=delivered.append)
    controller.start()

    assert controller.initialize("init")
    first = controller.get_receipt(timeout=1)
    assert first.action["kind"] == "intervene"
    assert controller.close_watch is True
    assert delivered == ["Correct the mistaken test oracle."]

    assert controller.publish_cursor(1, "first public intent after correction") is True
    second = controller.get_receipt(timeout=1)
    assert second.action["kind"] == "wait"
    assert controller.close_watch is False
    assert controller.publish_cursor(2, "ordinary progress") is False
    controller.stop()


def test_completion_forces_review_independent_of_patrol_schedule():
    seen = []

    def review(context, completion_pending):
        seen.append(completion_pending)
        if completion_pending:
            return MonitorAction("allow_complete", {})
        return MonitorAction("wait", {"after_turns": 100})

    controller = MonitorController(review)
    controller.start()
    controller.initialize("init")
    controller.get_receipt(timeout=1)
    assert controller.propose_completion(2, "root completion proposed") is True
    receipt = controller.get_receipt(timeout=1)
    controller.stop()

    assert receipt.action["kind"] == "allow_complete"
    assert seen == [False, True]


def test_monitor_failure_is_recorded_without_fabricated_receipt():
    controller = MonitorController(lambda *_: (_ for _ in ()).throw(RuntimeError("provider down")))
    controller.start()
    assert controller.initialize("init")
    deadline = time.monotonic() + 1
    while not controller.failures and time.monotonic() < deadline:
        time.sleep(0.01)
    controller.stop()

    assert "provider down" in controller.failures[0]["error"]
    with pytest.raises(Exception):
        controller.get_receipt(timeout=0.01)


def test_events_arriving_during_review_are_caught_up_after_action():
    entered = threading.Event()
    release = threading.Event()
    calls = []

    def review(context, completion_pending):
        calls.append(context)
        if len(calls) == 1:
            entered.set()
            release.wait(1)
            return MonitorAction("intervene", {"message": "repair"})
        return MonitorAction("wait", {"after_turns": 2})

    controller = MonitorController(review)
    controller.start()
    controller.initialize("init")
    assert entered.wait(1)
    controller.publish_cursor(1, "cursor one while review is running")
    release.set()
    controller.get_receipt(timeout=1)
    follow_up = controller.get_receipt(timeout=1)
    controller.stop()

    assert follow_up.cursor == 1
    assert calls == ["init", "cursor one while review is running"]


def test_completion_proposed_during_review_is_not_lost():
    entered = threading.Event()
    release = threading.Event()
    completion_flags = []

    def review(context, completion_pending):
        completion_flags.append(completion_pending)
        if len(completion_flags) == 1:
            entered.set()
            release.wait(1)
            return MonitorAction("wait", {"after_turns": 50})
        return MonitorAction("allow_complete", {})

    controller = MonitorController(review)
    controller.start()
    controller.initialize("ordinary review")
    assert entered.wait(1)
    assert controller.propose_completion(4, "completion while busy") is False
    release.set()
    controller.get_receipt(timeout=1)
    completion_receipt = controller.get_receipt(timeout=1)
    controller.stop()

    assert completion_receipt.cursor == 4
    assert completion_receipt.action["kind"] == "allow_complete"
    assert completion_flags == [False, True]


def test_controller_runs_real_monitor_agent_adapter(tmp_path):
    task = tmp_path / "task"
    task.mkdir()
    (task / "task.txt").write_text("Do not drop the wildcard.", encoding="utf-8")
    client = PersistentSequenceClient([Response("wait", {"after_turns": 2})])
    agent = MonitorAgent(client, MonitorWorkspace(task, tmp_path / "private"))
    controller = MonitorController(agent.review_sync)
    controller.start()

    assert controller.initialize("Read task/task.txt and orient yourself.")
    receipt = controller.get_receipt(timeout=1)
    controller.stop()

    assert receipt.action == {"kind": "wait", "payload": {"after_turns": 2}}
