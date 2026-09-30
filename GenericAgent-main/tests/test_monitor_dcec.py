"""Deterministic DCEC contract and production assembly regressions."""

import json
import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

from monitor_agent_core.agent import DCEC_CONTINUATION_PROMPT, DCEC_SYSTEM_PROMPT, MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.working_context import dcec_working_context
from monitor_agent_core.workspace import MonitorWorkspace
from test_monitor_agent import SequenceClient


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "original_task.txt").write_text("Preserve all requested behavior.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "private")


def provider(config=None):
    return MonitorProviderClient("anthropic", {
        "apikey": "test", "apibase": "https://example.test", "model": "claude-test",
        "max_retries": 0, **(config or {}),
    })


def test_dcec_off_preserves_ordinary_agent_contract(tmp_path):
    left, right = SequenceClient([]), SequenceClient([])
    right.config = {"monitor_dcec": False}
    a = MonitorAgent(left, workspace(tmp_path / "a"))
    b = MonitorAgent(right, workspace(tmp_path / "b"))
    assert a.system_prompt == b.system_prompt
    assert DCEC_SYSTEM_PROMPT not in a.system_prompt
    assert not hasattr(left, "prepare_active_context")
    assert not hasattr(right, "prepare_active_context")


@pytest.mark.parametrize("setting", [
    "monitor_inquiry", "monitor_decision_context", "monitor_pma_memory",
    "monitor_active_working_context", "monitor_grounded_context", "monitor_feedback_focus",
    "monitor_tool_feedback", "monitor_live_awareness", "monitor_advice_revision",
])
def test_dcec_rejects_historical_semantic_candidates(tmp_path, setting):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True, setting: True}
    with pytest.raises(ValueError, match="cannot be stacked"):
        MonitorAgent(client, workspace(tmp_path))


def test_dcec_rejects_independent_c_and_invalid_bound(tmp_path):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True}
    with pytest.raises(ValueError, match="monitor_independent_c"):
        MonitorAgent(client, workspace(tmp_path / "child"), independent_check=lambda *_: None)
    client = SequenceClient([])
    client.config = {"monitor_dcec": True, "monitor_dcec_working_chars": 9000}
    with pytest.raises(ValueError, match="between 512 and 8000"):
        MonitorAgent(client, workspace(tmp_path / "bound"))
    client = SequenceClient([])
    client.config = {"monitor_dcec": True, "monitor_semantic_continuity": False}
    with pytest.raises(ValueError, match="requires the ordinary semantic continuation"):
        MonitorAgent(client, workspace(tmp_path / "continuation"))


def test_bounded_view_is_single_state_and_reports_transport_cost(tmp_path):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision\n" + "x" * 6000)
    text, metadata = dcec_working_context(ws, 1000)
    assert text.count("<dcec_working_state>") == 1
    assert "not a fact source or verified truth" in text
    assert "Only the first 1000 characters" in text
    assert metadata == {**metadata, "path": "monitor/working.md", "limit_characters": 1000,
                        "visible_characters": 1000, "truncated": True}
    assert metadata["source_characters"] > metadata["visible_characters"]
    assert metadata["injected_characters"] == len(text)
    assert metadata["estimated_tokens"] > 0
    assert not (ws.private_root / "decision_state.json").exists()


def test_ader_contract_regulates_decision_evidence_and_root_completion(tmp_path):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision\n- whole-task completion")
    view, _metadata = dcec_working_context(ws)
    combined = "\n".join((DCEC_SYSTEM_PROMPT, DCEC_CONTINUATION_PROMPT, view)).lower()
    normalized = " ".join(combined.split())

    assert "evidential reference" in normalized
    assert "actual evidence reach" in normalized
    assert "residual decision gap" in normalized
    assert "change the measurement scheme" in normalized
    assert "a new observation adds control-relevant information only if it reduces the gap" in normalized
    assert "difficulty or infeasibility changes the feasible control action or task-side outcome" in normalized
    assert "requested, running and interrupted are not positive evidence" in normalized
    assert "return to the same root decision" in normalized
    assert "a local repair alone never authorizes allow_complete" in normalized
    assert "immediately recondition the evidential reference" in normalized
    assert "clear the dependency, prune superseded grounds and relax" in normalized
    assert "task checklist" in normalized
    assert "at most one focal" in normalized


def test_v1_uses_only_working_note_and_existing_model_stage(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision\n- local recovery")
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws)
    requests = []

    def request_once(tools):
        requests.append(client.assembled_request_snapshot(tools))
        return ([{"type": "tool_use", "id": "wait", "name": "wait",
                  "input": {"after_turns": 1}}], {})

    monkeypatch.setattr(client, "_request_once", request_once)
    assert monitor.review("Normal wake").kind == "wait"
    assert len(requests) == client.complete_calls == 1
    assert not (ws.private_root / "decision_state.json").exists()
    assert not (ws.private_root / "epistemic_state.json").exists()
    assert [tool["function"]["name"] for tool in requests[0]["tools"]] == [
        "file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]


def test_production_request_injects_view_once_and_does_not_persist_copy(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision\n- inspect a material uncertainty")
    client = provider({"monitor_dcec": True, "monitor_dcec_working_chars": 1200})
    monitor = MonitorAgent(client, ws)
    snapshots = []

    def request_once(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        assert [tool["function"]["name"] for tool in tools] == [
            "file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]
        wire = json.dumps(client.history, ensure_ascii=False)
        assert wire.count("<dcec_working_state>") == 1
        return ([{"type": "tool_use", "id": "wait", "name": "wait",
                  "input": {"after_turns": 1}}], {})

    monkeypatch.setattr(client, "_request_once", request_once)
    assert monitor.review("Normal wake").kind == "wait"
    assert len(snapshots) == client.complete_calls == 1
    assert "<dcec_working_state>" not in json.dumps(client.history, ensure_ascii=False)
    events = [json.loads(line) for line in
              (ws.private_root / "audit/progress.jsonl").read_text(encoding="utf-8").splitlines()]
    view = next(event for event in events if event["event"] == "dcec_working_view")
    assert view["limit_characters"] == 1200 and view["injected_characters"] > 0


def test_lifecycle_revision_replaces_active_concern_and_can_reopen(tmp_path):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True}
    monitor = MonitorAgent(client, workspace(tmp_path))
    open_state = "Current decision\n- local repair\nActive concern\n- open: wrong API\nCurrent grounds\n- task claim only"
    assert monitor.dispatch("file_write", {"path": "monitor/working.md", "content": open_state}).data["characters"]
    monitor.dispatch("file_patch", {"path": "monitor/working.md", "old_text": "open: wrong API",
                                    "new_text": "recovering: intervention sent; uptake not yet observed"})
    monitor.dispatch("file_patch", {"path": "monitor/working.md",
                                    "old_text": "recovering: intervention sent; uptake not yet observed",
                                    "new_text": "resolved locally after direct post-repair observation; not whole-task support"})
    current = (monitor.workspace.private_root / "working.md").read_text(encoding="utf-8")
    assert "open: wrong API" not in current and "resolved locally" in current
    assert "not whole-task support" in current
    monitor.dispatch("file_patch", {"path": "monitor/working.md", "old_text": "resolved locally",
                                    "new_text": "reopened by a new relevant conflict"})
    assert "reopened by a new relevant conflict" in (
        monitor.workspace.private_root / "working.md").read_text(encoding="utf-8")
    events = (monitor.workspace.private_root / "audit/progress.jsonl").read_text(encoding="utf-8")
    assert events.count('"event": "dcec_state_mutation"') == 4
    assert monitor.dispatch("file_patch", {"path": "monitor/working.md", "old_text": "absent",
                                           "new_text": "unused"}).data["status"] == "error"
    events = (monitor.workspace.private_root / "audit/progress.jsonl").read_text(encoding="utf-8")
    assert '"event": "dcec_state_mutation_failed"' in events


def test_evidence_receipt_preserves_range_hash_and_truncation_without_truth_label(tmp_path):
    client = SequenceClient([])
    client.config = {"monitor_dcec": True}
    monitor = MonitorAgent(client, workspace(tmp_path))
    (monitor.workspace.evidence_root / "source.txt").write_text("abcdef\nsecond\n", encoding="utf-8")
    receipt = monitor.dispatch("file_read", {
        "path": "task/source.txt", "start": 1, "count": 2, "max_chars": 3}).data
    assert receipt["truncated"] and receipt["next_read"]
    assert receipt["sha256"] and receipt["path"] == "task/source.txt"
    assert not ({"satisfied", "correct", "sufficient", "semantically_stale"} & set(receipt))


def test_dcec_continuation_contract_and_rejected_note_never_overwrite(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Active concern\n- recovering: direct evidence pending")
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws)
    original = (ws.private_root / "working.md").read_text(encoding="utf-8")
    calls = []

    def truncated(_tools):
        calls.append(client.history[-1]["content"][0]["text"])
        assert DCEC_CONTINUATION_PROMPT in calls[-1]
        assert "do not reactivate" in calls[-1].lower()
        client.last_response_metadata = {"stop_reason": "max_tokens"}
        return [{"type": "text", "text": "partial"}], {}

    monkeypatch.setattr(client, "_request", truncated)
    with pytest.raises(ValueError, match="output limit"):
        monitor._prepare_continuation()
    assert len(calls) == 2
    assert (ws.private_root / "working.md").read_text(encoding="utf-8") == original


def test_valid_continuation_replaces_old_state_and_next_view_uses_only_current_note(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Active concern\n- resolved item incorrectly remains active")
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws)
    revised = ("Current decision\n- decide whether recovery evidence is sufficient\n"
               "Active concern\n- recovering: wait for direct result\n"
               "Current grounds and limits\n- Task Agent reports a fix; not direct evidence")

    def request(_tools):
        assert DCEC_CONTINUATION_PROMPT in client.history[-1]["content"][0]["text"]
        client.last_response_metadata = {"stop_reason": "end_turn", "stream_complete": True}
        return [{"type": "text", "text": revised}], {}

    monkeypatch.setattr(client, "_request", request)
    assert monitor._prepare_continuation() == revised
    visible, _ = dcec_working_context(ws)
    assert revised in visible
    assert "resolved item incorrectly remains active" not in visible
    assert "Task Agent reports a fix; not direct evidence" in visible


@pytest.mark.parametrize("value", ["0", "1", "bad"])
def test_adapter_exposes_dcec_without_mutating_input(tmp_path, monkeypatch, value):
    import ga_monitor_adapter as adapter
    monkeypatch.setenv("GA_PMA_ENABLED", "0")
    monkeypatch.setenv("GA_MONITOR_DCEC", value)
    monkeypatch.setenv("GA_MONITOR_DCEC_WORKING_CHARS", "4000")
    captured = {}
    monkeypatch.setattr(adapter, "MonitorRuntime", lambda **kw: captured.update(kw))
    original = {"model": "fixture"}
    if value == "bad":
        with pytest.raises(ValueError, match="must be 0 or 1"):
            adapter.GenericAgentMonitorAdapter(
                task_workspace=tmp_path, public_task="Task", model_config=original)
    else:
        adapter.GenericAgentMonitorAdapter(task_workspace=tmp_path, public_task="Task", model_config=original)
        assert captured["model_config"]["monitor_dcec"] == (value == "1")
        assert captured["model_config"]["monitor_dcec_working_chars"] == 4000
    assert original == {"model": "fixture"}


def test_adapter_rejects_external_pma_stacking(tmp_path, monkeypatch):
    import ga_monitor_adapter as adapter
    monkeypatch.setenv("GA_MONITOR_DCEC", "1")
    monkeypatch.setenv("GA_PMA_ENABLED", "1")
    monkeypatch.setattr(adapter, "MonitorRuntime", lambda **_kw: pytest.fail("must reject before runtime"))
    with pytest.raises(ValueError, match="GA_PMA_ENABLED"):
        adapter.GenericAgentMonitorAdapter(
            task_workspace=tmp_path, public_task="Task", model_config={"model": "fixture"})


def test_discriminating_manifest_is_frozen_unexecuted_and_isolates_candidates():
    path = (Path(__file__).resolve().parents[2] / "method_discovery/artifacts/dcec_v0_20260921"
            / "discriminating_manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    assert manifest["status"] == "prepared_not_executed"
    assert manifest["execution_authorized"] is True
    assert (Path(__file__).resolve().parents[2] / manifest["execution_output"]
            / "results.json").is_file()
    assert manifest["model_api_calls_made_during_preparation"] == 0
    assert manifest["conditions"]["ordinary"]["GA_MONITOR_DCEC"] == "0"
    assert manifest["conditions"]["dcec_v0"]["GA_MONITOR_DCEC"] == "1"
    assert set(manifest["historical_candidate_switches"].values()) == {"0"}
    assert manifest["shared_contract"]["dcec_additional_model_calls"] == 0
    fixture = Path(__file__).resolve().parents[2] / manifest["fixture_spec"]
    # Git's LF blob is authoritative; this Windows worktree may materialize CRLF.
    assert hashlib.sha256(fixture.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == manifest["fixture_spec_sha256"]
    assert json.loads(fixture.read_text(encoding="utf-8"))["status"] == "frozen_executable_spec"
    assert manifest["implementation_commit"] == "1cd7048c5742ca7415937ec5142cc28fd2bcaf22"
    runner = Path(__file__).resolve().parents[2] / manifest["runner_path"]
    assert hashlib.sha256(runner.read_bytes().replace(b"\r\n", b"\n")).hexdigest() == manifest["runner_sha256"]


M1_BASE = "746a695adac4325d6440941d384d543d1364fef9"


def test_ader_has_exact_m1_parent_and_only_allowed_production_changes():
    root = Path(__file__).resolve().parents[2]
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    head = git("rev-parse", "HEAD")
    assert head == M1_BASE or git("rev-parse", "HEAD^") == M1_BASE
    changed = set(git("diff", "--name-only", M1_BASE).splitlines())
    production = {p for p in changed if p.startswith("GenericAgent-main/monitor_agent_core/")}
    assert production == {
        "GenericAgent-main/monitor_agent_core/agent.py",
        "GenericAgent-main/monitor_agent_core/working_context.py",
    }


def test_dcec_off_exact_provider_ready_equality_to_frozen_m1(tmp_path):
    """Run each real assembly in a fresh interpreter; fake only the transport."""
    root = Path(__file__).resolve().parents[2]
    base = Path(os.environ["ADER_M1_SOURCE"]).resolve()
    assert subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"], text=True).strip() == M1_BASE
    evidence = tmp_path / "evidence"
    private = tmp_path / "private"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("A neutral public task.\n", encoding="utf-8")
    script = """
import json, sys
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
client = MonitorProviderClient('anthropic', {
    'apikey': 'virtual-test', 'apibase': 'https://offline.invalid',
    'model': 'claude-test', 'max_retries': 0, 'monitor_dcec': False})
monitor = MonitorAgent(client, MonitorWorkspace(sys.argv[1], sys.argv[2]))
def fake(tools):
    print(json.dumps(client.assembled_request_snapshot(tools), sort_keys=True))
    return ([{'type': 'tool_use', 'id': 'wait-1', 'name': 'wait',
              'input': {'after_turns': 1}}], {})
client._request_once = fake
assert monitor.review('Ordinary synthetic wake.').kind == 'wait'
"""
    def capture(source):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source / "GenericAgent-main")
        out = subprocess.check_output([sys.executable, "-c", script, str(evidence), str(private)],
                                      env=env, cwd=str(source / "GenericAgent-main"), text=True)
        payload = json.loads(out.strip().splitlines()[-1])
        # The only non-deterministic request identity is generated per review.
        payload["review_id"] = "<review-id>"
        return payload
    assert capture(base) == capture(root)


def test_ader_ordinary_and_pending_root_requests_keep_native_tools(tmp_path, monkeypatch):
    for pending in (False, True):
        ws = workspace(tmp_path / str(pending))
        ws.write_text("monitor/working.md", "Current decision: inspect public evidence.")
        client = provider({"monitor_dcec": True})
        monitor = MonitorAgent(client, ws)
        snapshots = []
        if pending:
            monitor.completion_state = lambda: {"generation": 1, "request_id": "completion-1", "cursor": 3}
        def fake(tools):
            snapshots.append(client.assembled_request_snapshot(tools))
            name = "allow_complete" if pending else "wait"
            args = {} if pending else {"after_turns": 1}
            return ([{"type": "tool_use", "id": "control", "name": name, "input": args}], {})
        monkeypatch.setattr(client, "_request_once", fake)
        assert monitor.review("Synthetic wake", completion_pending=pending).kind == (
            "allow_complete" if pending else "wait")
        assert client.complete_calls == 1
        request = snapshots[0]
        assert "evidential reference" in request["system"]
        assert "residual decision gap" in request["system"]
        assert [tool["function"]["name"] for tool in request["tools"]] == [
            "file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]
        assert "independent_check" not in json.dumps(request)
        assert request["root_handoff"] == (
            {"generation": 1, "request_id": "completion-1", "cursor": 3} if pending else None)
        assert "<dcec_working_state>" in json.dumps(request)


def test_ader_mid_review_completion_reconditions_next_real_request(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision: local recovery; direct observation pending.")
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws)
    state = {"pending": None}
    monitor.completion_state = lambda: state["pending"]
    snapshots = []
    def fake(tools):
        snapshots.append(client.assembled_request_snapshot(tools))
        if len(snapshots) == 1:
            state["pending"] = {"generation": 2, "request_id": "completion-2", "cursor": 7}
            return ([{"type": "tool_use", "id": "read-1", "name": "file_read",
                      "input": {"path": "task/original_task.txt"}}], {})
        return ([{"type": "tool_use", "id": "approval", "name": "allow_complete", "input": {}}], {})
    monkeypatch.setattr(client, "_request_once", fake)
    action = monitor.review("Ordinary follow wake", completion_pending=False)
    assert action.kind == "allow_complete" and action.payload["request_id"] == "completion-2"
    assert client.complete_calls == len(snapshots) == 2
    assert snapshots[0]["root_handoff"] is None
    assert snapshots[1]["root_handoff"] == state["pending"]
    assert "Runtime update: the Task Agent is waiting" in json.dumps(snapshots[1]["messages"])
    assert "immediately recondition the evidential reference" in snapshots[1]["system"]
    assert "local recovery adequacy is not whole-task adequacy" in snapshots[1]["system"]
    assert snapshots[0]["tools"] == snapshots[1]["tools"]
    assert "independent_check" not in json.dumps(snapshots[1])


def test_ader_continuation_and_view_are_semantic_not_parser(tmp_path):
    ws = workspace(tmp_path)
    note = "Decision: local correction. Witness: source range. Gap: result not yet returned."
    ws.write_text("monitor/working.md", note)
    view, metadata = dcec_working_context(ws)
    assert note in view and metadata["limit_characters"] == 4000
    assert "not required headings or a fixed form" in view
    assert "actual evidence reach" in view
    assert "unavailable" in view
    assert "evidential reference" in DCEC_CONTINUATION_PROMPT
    assert "actual evidence reach" in DCEC_CONTINUATION_PROMPT
    assert "residual decision gap" in DCEC_CONTINUATION_PROMPT
    assert "prune the resolved" in DCEC_CONTINUATION_PROMPT
    assert not (ws.private_root / "decision_state.json").exists()


def test_ader_keeps_m1_intervention_and_completion_identity_boundary(tmp_path):
    client = provider({"monitor_dcec": True})
    monitor = MonitorAgent(client, workspace(tmp_path))
    state = {"current": {"generation": 1, "request_id": "completion-1", "cursor": 5}}
    monitor.completion_state = lambda: state["current"]
    monitor.intervention_callback = lambda message: {"delivered": message}
    monitor._refresh_completion()
    sent = monitor.dispatch("intervene", {"message": "A public requirement is still open."})
    assert sent.data["status"] == "submitted"
    stale = monitor.dispatch("allow_complete", {})
    assert stale.data["status"] == "error"
    state["current"] = {"generation": 2, "request_id": "completion-2", "cursor": 9}
    monitor._refresh_completion()
    current = monitor.dispatch("allow_complete", {})
    assert current.action.kind == "allow_complete"
    assert current.action.payload == {"request_id": "completion-2"}
