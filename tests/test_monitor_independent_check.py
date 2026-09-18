from monitor_agent_core.agent import INDEPENDENT_CHECK_TOOL, MonitorAgent


def _monitor(callback):
    monitor = object.__new__(MonitorAgent)
    monitor.independent_check = callback
    return monitor


def test_independent_check_is_optional_and_returns_scoped_result():
    calls = []
    monitor = _monitor(lambda question, paths: calls.append((question, paths)) or {
        "status": "completed", "outcome": "unresolved", "conclusion": "build is not enough",
        "requests": 1, "remaining_requests": 2,
    })

    result = monitor._dispatch("independent_check", {
        "question": "Does the build prove runtime behavior?",
        "paths": ["task/original_task.txt", "task/build_observation.json"],
    })

    assert result.data["outcome"] == "unresolved"
    assert calls == [("Does the build prove runtime behavior?",
                      ("task/original_task.txt", "task/build_observation.json"))]
    assert INDEPENDENT_CHECK_TOOL["function"]["name"] == "independent_check"


def test_independent_check_rejects_non_task_paths_before_callback():
    called = []
    monitor = _monitor(lambda *_: called.append(True))
    result = monitor._dispatch("independent_check", {
        "question": "q", "paths": ["monitor/working.md"],
    })
    assert result.data["status"] == "error"
    assert called == []
