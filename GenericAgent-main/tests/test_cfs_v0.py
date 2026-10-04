"""CFS-v0 mechanical sensing and real provider-ready assembly; zero network."""

import json
import queue
import threading

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.cfs_v0 import LIMIT, SituationState, code_run_outcomes
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "original_task.txt").write_text("Maintain the route.\n", encoding="utf-8")
    task = tmp_path / "task"
    task.mkdir()
    return MonitorWorkspace(evidence, tmp_path / "private", task_mounts={"workspace": task})


def event(ws, seq, *, text="Task update", calls=(), results=(), boundary="post_tool_pre_next_llm"):
    row = {"archive_sequence": seq, "task_turn": seq, "boundary": boundary,
           "text": text, "tool_calls": list(calls), "tool_results": list(results)}
    with (ws.evidence_root / "public_events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row) + "\n")
    return row


def run_call(seq, script, result=None):
    call = {"id": f"c{seq}", "name": "code_run", "args": {"script": script, "cwd": "/app"}}
    replies = [] if result is None else [{"tool_use_id": call["id"], "content": json.dumps(result)}]
    return call, replies


def test_interval_paths_pairing_and_bounded_manifest(tmp_path):
    ws = workspace(tmp_path)
    state = SituationState(ws)
    state.begin_review("r1")
    event(ws, 1, text="initial")
    first, meta = state.build(used_turns=1, max_turns=300, remaining_seconds=900)
    assert "interval=(0, 1]" in first and "Task turns=1..1" in first
    assert "remaining: 299" in first and meta["shown_through_cursor"] == 1
    assert state.committed_cursor == state.shown_cursor == 0  # build is not injection
    state.context_appended()
    state.end_review(None)
    assert state.committed_cursor == 1

    task = ws.task_mounts["workspace"]
    (task / "new.go").write_text("a", encoding="utf-8")
    (task / "old.go").write_text("old", encoding="utf-8")
    # Establish a path baseline at an actual injected request.
    state.begin_review("r2")
    state.build()
    state.context_appended()
    state.end_review(None)
    (task / "new.go").write_text("changed", encoding="utf-8")
    (task / "old.go").unlink()
    (task / "add.go").write_text("added", encoding="utf-8")
    c2, r2 = run_call(2, "echo one", {"status": "success", "exit_code": 0, "stdout": "one"})
    c3, r3 = run_call(3, "echo two", {"status": "error", "exit_code": 2, "stderr": "two"})
    c4, _ = run_call(4, "echo not returned")
    event(ws, 2, calls=[c2], results=r2)
    event(ws, 3, calls=[c3], results=r3)
    event(ws, 4, calls=[c4], results=[])
    state.begin_review("r3")
    text, meta = state.build()
    assert "interval=(1, 4]" in text and "Task turns=2..4" in text
    assert "modified: task/workspace/new.go" in text
    assert "deleted: task/workspace/old.go" in text
    assert "added: task/workspace/add.go" in text
    assert "echo one" in text and "exit_code=0" in text
    assert "echo two" in text and "exit_code=2" in text
    assert "echo not returned" in text and "no_return_in_interval" in text
    assert "verified" not in text.lower() and "coverage" not in text.lower()
    assert len(text) <= LIMIT
    manifest = json.loads((ws.private_root / "audit/cfs_deltas" /
                           (meta["manifest_locator"].split("/")[-1])).read_text(encoding="utf-8"))
    assert manifest["event_locators"] == [f"task/public_events.jsonl#{i}" for i in (2, 3, 4)]
    assert len(manifest["code_run_outcomes"]) == 3
    assert manifest["code_run_outcomes"][2]["result_present"] is False
    assert set(manifest["changed_paths"]) == {"added", "modified", "deleted"}


def test_code_run_identity_pairs_across_events_and_deduplicates_surface(tmp_path):
    ws = workspace(tmp_path)
    call, result = run_call(1, "echo actual", {"status": "success", "exit_code": 0,
                                                "stdout": "actual"})
    before = event(ws, 1, calls=[call], boundary="pre_tool")
    after = event(ws, 2, calls=[call], results=result)
    rows = code_run_outcomes([before, after])
    assert len(rows) == 1
    assert rows[0]["call_event_locator"] == "task/public_events.jsonl#1"
    assert rows[0]["result_event_locator"] == "task/public_events.jsonl#2"
    assert rows[0]["status"] == "success" and rows[0]["exit_code"] == 0
    state = SituationState(ws)
    state.begin_review("r")
    text, _ = state.build()
    assert "1 unique tool identities" in text
    assert text.count("command=echo actual") == 1
    assert "no_return_in_interval" not in text


def test_code_run_call_only_distinct_identities_and_conflicting_args(tmp_path):
    ws = workspace(tmp_path)
    first, _ = run_call(1, "echo first")
    second, response = run_call(2, "echo second", {"status": "error", "exit_code": 2})
    conflicting = {**first, "args": {"script": "echo changed", "cwd": "/app"}}
    events = [event(ws, 1, calls=[first, second], boundary="pre_tool"),
              event(ws, 2, calls=[first, second], results=response),
              event(ws, 3, calls=[conflicting])]
    rows = code_run_outcomes(events)
    assert len(rows) == 2
    assert rows[0]["tool_use_id"] == "c1"
    assert rows[0]["status"] == "no_return_in_interval"
    assert rows[0]["result_event_locator"] is None
    assert rows[0]["command"] == "echo first"
    assert rows[0]["call_conflicts"] == [{"event_locator": "task/public_events.jsonl#3",
                                          "args": conflicting["args"]}]
    assert rows[1]["tool_use_id"] == "c2"
    assert rows[1]["status"] == "error" and rows[1]["result_event_locator"] == "task/public_events.jsonl#2"
    state = SituationState(ws)
    state.begin_review("r")
    text, _ = state.build()
    assert "2 unique tool identities" in text
    assert text.count("command=echo first") == 1
    assert text.count("command=echo second") == 1
    assert "Conflicting call arguments" in text


def test_code_run_result_crosses_successful_review_cursor(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    call = {"id": "X", "name": "code_run", "args": {"script": "go test ./...", "cwd": "/app"}}
    event(ws, 1, calls=[call], boundary="post_model_pre_tool")
    config = {"apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
              "max_retries": 0, "monitor_dcec": True, "monitor_path_control_v0": True,
              "monitor_verification_loop_v0": True, "monitor_verification_runtime_managed": False,
              "monitor_coarse_to_fine_surface": True}
    client = MonitorProviderClient("anthropic", config)
    monitor = MonitorAgent(client, ws)
    requests = []

    def offline_once(tools):
        requests.append(client.assembled_request_snapshot(tools))
        return ([{"type": "tool_use", "id": f"wait-{len(requests)}", "name": "wait",
                  "input": {"after_turns": 1}}], {})

    monkeypatch.setattr(client, "_request_once", offline_once)
    assert monitor.review("First review").kind == "wait"
    assert monitor.situation.committed_cursor == 1
    first = json.dumps(requests[0])
    assert "go test ./..." in first and "no_return_in_interval" in first
    assert "task/public_events.jsonl#2" not in first

    event(ws, 2, results=[{"tool_use_id": "X", "content": json.dumps(
        {"status": "success", "exit_code": 0, "stdout": "ok"})}])
    assert monitor.review("Second review").kind == "wait"
    assert monitor.situation.committed_cursor == 2
    second = json.dumps(requests[1])
    assert "1 unique tool identities" in second
    assert "call=task/public_events.jsonl#1" in second
    assert "result=task/public_events.jsonl#2" in second
    assert "command=go test ./..." in second
    assert "status=success exit_code=0" in second
    assert "0 unique tool identities" not in second
    assert "validation execution" not in second.lower()
    assert "test adequate" not in second.lower()
    manifests = [json.loads(path.read_text(encoding="utf-8"))
                 for path in (ws.private_root / "audit/cfs_deltas").glob("*.json")]
    manifest = next(row for row in manifests if row["from_cursor"] == 1)
    assert len(manifest["code_run_outcomes"]) == 1
    assert manifest["code_run_outcomes"][0]["tool_use_id"] == "X"


def test_follow_refresh_unshown_end_and_root_handoff(tmp_path):
    ws = workspace(tmp_path)
    state = SituationState(ws)
    event(ws, 1)
    state.begin_review("r1")
    state.build()
    state.context_appended()
    unchanged, _ = state.build()
    assert unchanged == "Situation unchanged through cursor 1."
    event(ws, 2, text="concurrent event")
    refresh, _ = state.build()
    assert "interval=(1, 2]" in refresh and "concurrent event" in refresh
    state.context_appended()
    event(ws, 3, text="not injected before review end")
    state.end_review(None)
    assert state.committed_cursor == 2
    state.begin_review("root")
    handoff = {"cursor": 3, "generation": 1, "request_id": "root-1"}
    root, _ = state.build(handoff=handoff)
    assert "interval=(2, 3]" in root and "Pending root handoff" in root
    assert "task/public_events.jsonl#3" in root and "not injected" in root


def test_large_command_and_output_no_test_classification(tmp_path):
    ws = workspace(tmp_path)
    script = "echo 'cd /app && go test ./...'" + "x" * 12000
    call, result = run_call(1, script, {"status": "success", "exit_code": 0,
                                       "stdout": "FINAL DELIVERY REPORT " + "z" * 12000})
    row = event(ws, 1, calls=[call], results=result)
    state = SituationState(ws)
    state.begin_review("r")
    text, meta = state.build()
    manifest = json.loads((ws.private_root / "audit/cfs_deltas" /
                           meta["manifest_locator"].split("/")[-1]).read_text(encoding="utf-8"))
    assert len(text) <= LIMIT and "omitted" in text
    assert "task/public_events.jsonl#1" in text
    assert manifest["code_run_outcomes"][0]["command"] == script
    assert code_run_outcomes([row])[0]["exit_code"] == 0
    for forbidden in ("validation execution", "test adequate", "requirement covered", "verified"):
        assert forbidden not in text.lower()


def test_provider_ready_off_on_system_tools_and_cursor(tmp_path, monkeypatch):
    requests = {}
    for enabled in (False, True):
        ws = workspace(tmp_path / str(enabled))
        event(ws, 1, text="Task statement")
        config = {"apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
                  "max_retries": 0, "monitor_dcec": True, "monitor_path_control_v0": True,
                  "monitor_verification_loop_v0": True,
                  "monitor_verification_runtime_managed": False,
                  "monitor_executable_interpretation_surface": False,
                  "monitor_coarse_to_fine_surface": enabled}
        client = MonitorProviderClient("anthropic", config)
        monitor = MonitorAgent(client, ws)
        observed = []

        def no_network(tools):
            observed.append(client.assembled_request_snapshot(tools))
            return ([{"type": "tool_use", "id": "done", "name": "wait",
                      "input": {"after_turns": 1}}], {})

        monkeypatch.setattr(client, "_request_once", no_network)
        assert monitor.review("Ordinary review").kind == "wait"
        requests[enabled] = observed[0]
        if enabled:
            assert monitor.situation.committed_cursor == 1
            audit = (ws.private_root / "audit/dialogue.jsonl").read_text(encoding="utf-8")
            assert "supervisory_situation_injected" in audit
    off, on = requests[False], requests[True]
    assert off["system"] == on["system"]
    assert off["tools"] == on["tools"] and len(on["tools"]) == 7
    assert "Recent public Task events" in json.dumps(off)
    assert "Recent public Task events" not in json.dumps(on)
    assert "Supervisory Situation" in json.dumps(on)
    assert "Supervisory Situation" not in json.dumps(off)


def test_root_provider_input_and_no_retry_rebuild(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    event(ws, 1, text="ordinary update")
    event(ws, 2, text="current handoff", boundary="task_control_handoff")
    config = {"apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
              "max_retries": 1, "monitor_dcec": True, "monitor_path_control_v0": True,
              "monitor_verification_loop_v0": True, "monitor_verification_runtime_managed": False,
              "monitor_coarse_to_fine_surface": True}
    client = MonitorProviderClient("anthropic", config)
    monitor = MonitorAgent(client, ws)
    handoff = {"generation": 1, "request_id": "root-1", "cursor": 2, "task_turn": 2}
    monitor.completion_state = lambda: handoff
    attempts = []
    root_captures = []
    client.request_assembly_callback = lambda snapshot: root_captures.append(snapshot) or True

    from monitor_agent_core.provider import RetryableProviderError

    def offline_once(tools):
        attempts.append(client.assembled_request_snapshot(tools))
        assert monitor.situation.shown_cursor == 0
        if len(attempts) == 1:
            raise RetryableProviderError("offline transient")
        return ([{"type": "tool_use", "id": "done", "name": "allow_complete",
                  "input": {"result": "defer", "reason": "offline bounded delivery"}}], {})

    monkeypatch.setattr(client, "_request_once", offline_once)
    monkeypatch.setattr(client._cancelled, "wait", lambda _: False)
    assert monitor.review("Root review", completion_pending=True, root_handoff=handoff).kind == "incomplete_delivery"
    assert len(attempts) == 2
    assert attempts[0]["messages"] == attempts[1]["messages"]
    assert len(root_captures) == 1
    assert root_captures[0]["messages"] == attempts[0]["messages"]
    assert monitor.situation.committed_cursor == 2
    text = json.dumps(attempts[0], ensure_ascii=False)
    assert "Supervisory Situation" in text and "task/public_events.jsonl#2" in text
    assert "current handoff" in text and "Recent public Task events" not in text
    audit = (ws.private_root / "audit/dialogue.jsonl").read_text(encoding="utf-8")
    assert audit.count('"event": "supervisory_situation_injected"') == 1


def test_failed_provider_recovery_does_not_commit_and_next_review_reshows(tmp_path, monkeypatch):
    from monitor_agent_core.provider import ProviderRecoveryExhausted

    ws = workspace(tmp_path)
    event(ws, 1, text="unobserved task update")
    config = {"apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
              "max_retries": 0, "monitor_dcec": True, "monitor_path_control_v0": True,
              "monitor_verification_loop_v0": True, "monitor_verification_runtime_managed": False,
              "monitor_coarse_to_fine_surface": True}
    client = MonitorProviderClient("anthropic", config)
    monitor = MonitorAgent(client, ws)
    attempts = []

    def exhausted(tools):
        attempts.append(client.assembled_request_snapshot(tools))
        assert monitor.situation.shown_cursor == 0
        raise ProviderRecoveryExhausted("offline transport exhausted")

    monkeypatch.setattr(client, "_request_with_recovery", exhausted)
    import pytest
    with pytest.raises(ProviderRecoveryExhausted):
        monitor.review("Ordinary review")
    assert monitor.situation.shown_cursor == monitor.situation.committed_cursor == 0
    assert "interval=(0, 1]" in json.dumps(attempts[0])

    def success(tools):
        attempts.append(client.assembled_request_snapshot(tools))
        assert monitor.situation.shown_cursor == 0
        return ([{"type": "tool_use", "id": "done", "name": "wait",
                  "input": {"after_turns": 1}}], {})

    monkeypatch.setattr(client, "_request_with_recovery", success)
    assert monitor.review("Next ordinary review").kind == "wait"
    assert "interval=(0, 1]" in json.dumps(attempts[1])
    assert monitor.situation.shown_cursor == monitor.situation.committed_cursor == 1
    audit = (ws.private_root / "audit/dialogue.jsonl").read_text(encoding="utf-8")
    assert audit.count('"event": "supervisory_situation_injected"') == 1


def test_explicit_false_matches_absent_config(tmp_path, monkeypatch):
    snapshots = []
    ws = workspace(tmp_path)
    event(ws, 1, text="same public fact")
    for suffix, switch in (("absent", None), ("false", False)):
        config = {"apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
                  "max_retries": 0, "monitor_dcec": True, "monitor_path_control_v0": True,
                  "monitor_verification_loop_v0": True,
                  "monitor_verification_runtime_managed": False}
        if switch is not None:
            config["monitor_coarse_to_fine_surface"] = switch
        client = MonitorProviderClient("anthropic", config)
        monitor = MonitorAgent(client, ws)
        observed = []

        def offline_once(tools):
            observed.append(client.assembled_request_snapshot(tools))
            return ([{"type": "tool_use", "id": "done", "name": "wait",
                      "input": {"after_turns": 1}}], {})

        monkeypatch.setattr(client, "_request_once", offline_once)
        assert monitor.review("same wake").kind == "wait"
        snapshots.append(observed[0])
    for snapshot in snapshots:
        snapshot.pop("review_id", None)
    assert snapshots[0] == snapshots[1]


def test_cfs_runtime_replaces_wtv_wake_prose_without_new_wake(tmp_path, monkeypatch):
    import monitor_agent_core.agent as agent_module
    import monitor_agent_core.provider as provider_module
    from monitor_agent_core.runtime import _worker

    reviewed = []
    review_signals = queue.Queue()

    class FakeClient:
        def __init__(self, *args):
            pass

    class FakeMonitor:
        dcec_enabled = True
        cfs_v0 = True
        root_routed = False
        verification = None
        max_review_turns = 2

        def __init__(self, client, workspace, *args, **kwargs):
            pass

        def review(self, context, completion_pending=False, **kwargs):
            reviewed.append(context)
            review_signals.put(len(reviewed))
            return type("Action", (), {"kind": "wait", "payload":
                                   {"after_turns": 1, "mode": "patrol"}})()

    class Value:
        value = 0

        def get_lock(self):
            return threading.Lock()

    monkeypatch.setattr(provider_module, "MonitorProviderClient", FakeClient)
    monkeypatch.setattr(agent_module, "MonitorAgent", FakeMonitor)
    task = tmp_path / "task"
    task.mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    commands, outputs = queue.Queue(), queue.Queue()
    config = {"config_name": "offline", "model_config": {"monitor_live_intervention": False},
              "evidence_root": str(evidence), "private_root": str(tmp_path / "private"),
              "task_workspace": str(task), "max_review_turns": 2,
              "stop_event": threading.Event(), "active_completion": Value(),
              "completion_cursor": Value(), "latest_task_turn": Value()}
    worker = threading.Thread(target=_worker, args=(config, commands, outputs), daemon=True)
    worker.start()
    assert outputs.get(timeout=5)["kind"] == "ready"
    assert review_signals.get(timeout=5) == 1
    assert len(reviewed) == 1 and "Workspace transition" not in reviewed[0]
    commands.put({"kind": "boundary", "cursor": 1, "task_turn": 1})
    assert review_signals.get(timeout=5) == 2
    assert "Workspace transition" not in reviewed[1]
    commands.put({"kind": "close"})
    worker.join(timeout=5)
    assert not worker.is_alive()
    assert not (tmp_path / "private/audit/workspace_transitions.jsonl").exists()
