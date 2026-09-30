"""Offline request and control regressions for root-scoped independent support checks."""

import io
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest

from monitor_agent_core.agent import (DCEC_SYSTEM_PROMPT, INDEPENDENT_CHECK_TOOL,
                                      MONITOR_TOOLS, RISC_ROOT_PROMPT, MonitorAgent)
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


BASE = "746a695adac4325d6440941d384d543d1364fef9"
ROOT = Path(__file__).resolve().parents[2]
NAMES = [tool["function"]["name"] for tool in MONITOR_TOOLS]


def _workspace(tmp_path):
    evidence = tmp_path / "task"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "original_task.txt").write_text("Public obligation.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "monitor")


def _client(config):
    return MonitorProviderClient("anthropic", {
        "apikey": "offline-test", "apibase": "https://offline.invalid", "model": "fixture",
        "max_retries": 0, **config,
    })


def _capture(tmp_path, config, callback=None, root=False):
    ws = _workspace(tmp_path)
    ws.write_text("monitor/working.md", "Current decision: inspect public obligation.\n")
    client = _client(config)
    monitor = MonitorAgent(client, ws, independent_check=callback)
    requests = []

    def fake_send(tools):
        requests.append(client.assembled_request_snapshot(tools))
        action = "allow_complete" if root else "wait"
        return ([{"type": "tool_use", "id": "terminal", "name": action,
                  "input": {} if root else {"after_turns": 1}}], {})

    client._request_once = fake_send
    outcome = monitor.review("Neutral wake", completion_pending=root)
    assert outcome.kind == ("allow_complete" if root else "wait")
    assert len(requests) == 1
    return requests[0], monitor


def _base_request(tmp_path, dcec, callback):
    """Run original Git bytes in a separate interpreter, with no provider transport."""
    archive = subprocess.check_output([
        "git", "-C", str(ROOT), "archive", "--format=zip", BASE, "GenericAgent-main"
    ])
    extracted = tmp_path / "base_source"
    extracted.mkdir()
    with zipfile.ZipFile(io.BytesIO(archive)) as stream:
        stream.extractall(extracted)
    fixture = tmp_path / "shared_fixture"
    fixture.mkdir()
    script = r'''
import json, pathlib, sys
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
root=pathlib.Path(sys.argv[1]); evidence=root/'task'; evidence.mkdir(exist_ok=True)
(evidence/'original_task.txt').write_text('Public obligation.\n', encoding='utf-8')
ws=MonitorWorkspace(evidence, root/'monitor')
ws.write_text('monitor/working.md', 'Current decision: inspect public obligation.\n')
client=MonitorProviderClient('anthropic', {'apikey':'offline-test','apibase':'https://offline.invalid',
 'model':'fixture','max_retries':0,'monitor_dcec':sys.argv[2]=='1'})
callback=(lambda *_: None) if sys.argv[3]=='1' else None
monitor=MonitorAgent(client,ws,independent_check=callback)
def send(tools):
 request=client.assembled_request_snapshot(tools)
 request['review_id']=None
 print(json.dumps(request,ensure_ascii=False))
 return ([{'type':'tool_use','id':'terminal','name':'wait','input':{'after_turns':1}}],{})
client._request_once=send
assert monitor.review('Neutral wake').kind=='wait'
'''
    env = dict(os.environ, PYTHONPATH=str(extracted / "GenericAgent-main"))
    proc = subprocess.run(
        [sys.executable, "-c", script, str(fixture), str(int(dcec)), str(int(callback))],
        cwd=tmp_path, env=env, text=True, capture_output=True, check=True,
    )
    return json.loads(proc.stdout.strip())


@pytest.mark.parametrize("dcec,callback", [(False, False), (False, True), (True, False)])
def test_no_treatment_provider_ready_request_equals_exact_m1(tmp_path, dcec, callback):
    original = _base_request(tmp_path, dcec, callback)
    request, _ = _capture(tmp_path / "shared_fixture", {"monitor_dcec": dcec},
                          (lambda *_: None) if callback else None)
    request["review_id"] = None  # Only the newly generated mechanical review identity differs.
    assert request == original


def test_source_diff_is_limited_to_agent_and_tests():
    assert subprocess.check_output(["git", "-C", str(ROOT), "cat-file", "-t", BASE],
                                   text=True).strip() == "commit"
    changed = set(subprocess.check_output([
        "git", "-C", str(ROOT), "diff", "--name-only", BASE
    ], text=True).splitlines())
    assert changed <= {
        "GenericAgent-main/monitor_agent_core/agent.py",
        "GenericAgent-main/tests/test_monitor_dcec.py",
        "GenericAgent-main/tests/test_monitor_independent_check.py",
        "GenericAgent-main/tests/test_monitor_risc.py",
    }
    assert "GenericAgent-main/monitor_agent_core/probe.py" not in changed
    assert "GenericAgent-main/monitor_agent_core/runtime.py" not in changed


def test_root_only_provider_schema_and_contract(tmp_path):
    config = {"monitor_dcec": True, "monitor_semantic_continuity": True}
    callback = lambda *_: {"status": "completed", "outcome": "unresolved"}
    ordinary, _ = _capture(tmp_path, config, callback)
    root, _ = _capture(tmp_path, config, callback, root=True)
    assert [t["function"]["name"] for t in ordinary["tools"]] == NAMES
    assert root["tools"] == [*ordinary["tools"], INDEPENDENT_CHECK_TOOL]
    assert ordinary["system"].count(DCEC_SYSTEM_PROMPT) == 1
    assert RISC_ROOT_PROMPT not in ordinary["system"]
    assert root["system"].count(DCEC_SYSTEM_PROMPT) == 1
    assert root["system"].count(RISC_ROOT_PROMPT) == 1
    assert root["messages"] == ordinary["messages"]
    assert root["model_parameters"] == ordinary["model_parameters"]


def test_one_child_per_root_review_and_new_proposal_resets(tmp_path):
    calls = []
    ws = _workspace(tmp_path)
    client = _client({"monitor_dcec": True})
    monitor = MonitorAgent(client, ws, independent_check=lambda q, p: calls.append((q, p)) or {
        "status": "completed", "outcome": "unresolved", "requests": 1,
    })
    arguments = {"question": "Does this evidence support the public obligation?",
                 "paths": ["task/original_task.txt"]}
    assert monitor.dispatch("independent_check", arguments).data["status"] == "error"
    assert calls == []
    for proposal in ("completion-1", "completion-2"):
        monitor.completion_pending = True
        monitor._risc_root_review = True
        monitor._risc_probe_used = False
        monitor.completion_state = lambda p=proposal: {"generation": p, "request_id": p}
        first = monitor.dispatch("independent_check", arguments).data
        second = monitor.dispatch("independent_check", arguments).data
        assert first["status"] == "completed"
        assert second["status"] == "error" and "already been used" in second["error"]
    assert calls == [(arguments["question"], tuple(arguments["paths"]))] * 2
    assert monitor.dispatch("independent_check", {**arguments,
        "paths": ["monitor/working.md"]}).data["status"] == "error"


def test_repeated_tool_call_is_recoverable_in_actual_root_loop(tmp_path):
    ws = _workspace(tmp_path)
    client = _client({"monitor_dcec": True})
    calls, requests = [], []
    monitor = MonitorAgent(client, ws, independent_check=lambda q, p: calls.append((q, p)) or {
        "status": "completed", "outcome": "unresolved", "requests": 1,
    })
    arguments = {"question": "Does the evidence satisfy this obligation?",
                 "paths": ["task/original_task.txt"]}

    def fake_send(tools):
        requests.append(client.assembled_request_snapshot(tools))
        number = len(requests)
        if number <= 2:
            return ([{"type": "tool_use", "id": f"probe-{number}",
                      "name": "independent_check", "input": arguments}], {})
        return ([{"type": "tool_use", "id": "approval", "name": "allow_complete",
                  "input": {}}], {})

    client._request_once = fake_send
    assert monitor.review("Root handoff", completion_pending=True).kind == "allow_complete"
    assert len(requests) == 3 and len(calls) == 1
    history = json.dumps(client.history, ensure_ascii=False)
    assert "already been used in this root review" in history
    assert "probe-1" in history and "probe-2" in history


def test_new_root_proposal_allows_one_new_probe_in_next_review(tmp_path):
    ws = _workspace(tmp_path)
    client = _client({"monitor_dcec": True})
    calls = []
    monitor = MonitorAgent(client, ws, independent_check=lambda q, p: calls.append((q, p)) or {
        "status": "completed", "outcome": "supported_in_scope", "requests": 1,
    })
    current = {"generation": 1, "request_id": "completion-1", "cursor": 1}
    monitor.completion_state = lambda: current
    seen_in_review = 0

    def fake_send(tools):
        nonlocal seen_in_review
        seen_in_review += 1
        if seen_in_review == 1:
            return ([{"type": "tool_use", "id": f"probe-{current['generation']}",
                      "name": "independent_check", "input": {
                          "question": "Does this satisfy the public obligation?",
                          "paths": ["task/original_task.txt"]}}], {})
        return ([{"type": "tool_use", "id": f"approval-{current['generation']}",
                  "name": "allow_complete", "input": {}}], {})

    client._request_once = fake_send
    for generation in (1, 2):
        current = {"generation": generation, "request_id": f"completion-{generation}",
                   "cursor": generation}
        seen_in_review = 0
        action = monitor.review("Root handoff", completion_pending=True)
        assert action.kind == "allow_complete"
        assert action.payload["request_id"] == current["request_id"]
        assert seen_in_review == 2
    assert len(calls) == 2


def test_intervention_invalidates_pending_proposal_for_probe_and_approval(tmp_path):
    ws = _workspace(tmp_path)
    monitor = MonitorAgent(_client({"monitor_dcec": True}), ws,
                           independent_check=lambda *_: {"status": "completed"})
    pending = {"generation": 1, "request_id": "old", "cursor": 1}
    monitor.completion_state = lambda: pending
    monitor.completion_pending = True
    monitor._risc_root_review = True
    monitor._seen_completion = pending
    monitor.intervention_callback = lambda _: {"delivered": True}
    assert monitor.dispatch("intervene", {"message": "Correct the issue"}).data["status"] == "submitted"
    assert monitor.dispatch("independent_check", {
        "question": "q", "paths": ["task/original_task.txt"]}).data["status"] == "error"
    assert monitor.dispatch("allow_complete", {}).data["status"] == "error"
