"""Offline request/control checks for the M1-based CPRR candidate."""

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import requests

from monitor_agent_core.agent import (
    CONTINUATION_MODE_PROMPT,
    DCEC_CONTINUATION_PROMPT,
    DCEC_SYSTEM_PROMPT,
    MONITOR_SYSTEM_PROMPT,
    MONITOR_TOOLS,
    REVIEW_MODE_PROMPT,
    MonitorAgent,
)
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.working_context import (
    DCEC_WORKING_VIEW_DEFAULT_CHARS, dcec_working_context,
)
from monitor_agent_core.workspace import MonitorWorkspace


BASE = "746a695adac4325d6440941d384d543d1364fef9"
PROJECT = Path(__file__).resolve().parents[1]
REPO = PROJECT.parent


def _config(dcec):
    return {
        "apikey": "offline-test-only", "apibase": "https://offline.invalid",
        "provider": "anthropic", "model": "claude-opus-4-8",
        "monitor_dcec": dcec, "monitor_semantic_continuity": True,
        "monitor_dcec_working_chars": 4000, "max_tokens": 8192,
        "context_win": 200000, "temperature": 1, "thinking_type": "adaptive",
        "reasoning_effort": "high", "max_retries": 0,
    }


def _tool(name, tool_id="tool-1", **arguments):
    return [{"type": "tool_use", "id": tool_id, "name": name, "input": arguments}]


def _make_monitor(root, *, dcec=True, scripted=None, monkeypatch=None):
    evidence, private = root / "task", root / "monitor"
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "original_task.txt").write_text(
        "Public obligation: keep literal wildcard.\n", encoding="utf-8")
    client = MonitorProviderClient("claude_monitor_opus48", _config(dcec))
    monitor = MonitorAgent(client, MonitorWorkspace(evidence, private))
    responses = iter(scripted or [])
    captured = []

    def fake_transport(tools):
        _, _, payload = client._anthropic_request(tools)
        captured.append(copy.deepcopy(payload))
        return next(responses), {"input_tokens": 1, "output_tokens": 1, "synthetic": True}

    client._request_once = fake_transport
    if monkeypatch is not None:
        monkeypatch.setattr(requests, "post", lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("external transport must not be used")))
    return monitor, client, captured


def _capture_off(root):
    monitor, _, captured = _make_monitor(
        root, dcec=False, scripted=[_tool("wait", after_turns=1)])
    try:
        assert monitor.review("Ordinary synthetic patrol.").kind == "wait"
        return captured[0]
    finally:
        monitor.analysis.close()


def test_dcec_off_provider_ready_request_equals_frozen_m1(tmp_path):
    """Compare actual provider payloads, not only prompt fragments or tool names."""
    baseline = tmp_path / "baseline_source"
    package = baseline / "monitor_agent_core"
    shutil.copytree(PROJECT / "monitor_agent_core", package,
                    ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("agent.py", "working_context.py"):
        original = subprocess.check_output(
            ["git", "show", f"{BASE}:GenericAgent-main/monitor_agent_core/{name}"],
            cwd=REPO)
        (package / name).write_bytes(original)

    outputs = []
    for source in (baseline, PROJECT):
        env = {**os.environ, "PYTHONPATH": str(source), "PYTHONDONTWRITEBYTECODE": "1"}
        proc = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--capture-off", str(tmp_path / "same_workspace")],
            cwd=tmp_path, env=env, text=True, capture_output=True, check=True)
        outputs.append(json.loads(proc.stdout))
    assert outputs[0] == outputs[1]
    assert outputs[0]["system"] == MONITOR_SYSTEM_PROMPT + "\n\n" + REVIEW_MODE_PROMPT
    assert [tool["name"] for tool in outputs[0]["tools"]] == [
        "file_read", "file_write", "file_patch", "code_run",
        "wait", "intervene", "allow_complete"]


def test_root_contract_and_request_are_conditional_and_native(tmp_path, monkeypatch):
    monitor, client, captured = _make_monitor(
        tmp_path, scripted=[_tool("wait", after_turns=1), _tool("allow_complete")],
        monkeypatch=monkeypatch)
    try:
        assert monitor.system_prompt == MONITOR_SYSTEM_PROMPT + "\n\n" + DCEC_SYSTEM_PROMPT
        assert "Only while the current decision is whole-task completion" in DCEC_SYSTEM_PROMPT
        assert "Outside whole-task completion" in DCEC_SYSTEM_PROMPT
        assert "one focal unresolved premise" in DCEC_SYSTEM_PROMPT
        assert "completed observation" in DCEC_SYSTEM_PROMPT
        assert "Intervention starts recovery but is not resolution" in DCEC_SYSTEM_PROMPT
        assert "Requested, running and\ninterrupted are not positive evidence" in DCEC_SYSTEM_PROMPT
        assert "same decision-relevant distinction" in DCEC_SYSTEM_PROMPT
        assert "Adequate unchanged support may be reused" in DCEC_SYSTEM_PROMPT
        assert "do not create a permanent conservative barrier" in DCEC_SYSTEM_PROMPT
        assert monitor.review("Ordinary synthetic patrol.").kind == "wait"
        assert len(captured) == 1
        assert "Runtime update: the Task Agent is waiting" not in json.dumps(captured[0])
        assert "root support cover" in captured[0]["system"]
        current = {"request_id": "completion-1", "generation": 1, "cursor": 7}
        monitor.completion_state = lambda: current
        action = monitor.review("Root completion proposal.", completion_pending=True)
        assert action.kind == "allow_complete"
        assert action.payload["request_id"] == "completion-1"
        assert len(captured) == 2
        assert captured[1]["system"].count(DCEC_SYSTEM_PROMPT) == 1
        assert "Root completion proposal." in json.dumps(captured[1]["messages"])
        assert "Runtime update: the Task Agent is waiting" in json.dumps(captured[1]["messages"])
        assert "root support cover" in captured[1]["system"]
        assert len(captured[1]["tools"]) == len(MONITOR_TOOLS) == 7
        assert client.complete_calls == 2
    finally:
        monitor.analysis.close()


def test_working_state_is_free_prose_and_bounded_across_reviews(tmp_path, monkeypatch):
    state = "Root support: wildcard witness covers API only; behavior remains uncertain."
    monitor, client, captured = _make_monitor(
        tmp_path, scripted=[_tool("file_write", path="monitor/working.md", content=state),
                            _tool("wait", after_turns=1), _tool("wait", after_turns=1)],
        monkeypatch=monkeypatch)
    try:
        assert monitor.review("First wake.").kind == "wait"
        assert (tmp_path / "monitor" / "working.md").read_text(encoding="utf-8") == state
        assert len(captured) == 2
        assert state in json.dumps(captured[1]["messages"])
        assert monitor.review("Later wake.").kind == "wait"
        assert state in json.dumps(captured[2]["messages"])
        assert DCEC_WORKING_VIEW_DEFAULT_CHARS == monitor.dcec_working_chars == 4000
        assert "<dcec_working_state>" in json.dumps(captured[2]["messages"])
        assert len(client.history) >= 2
        assert not (tmp_path / "monitor" / "control_slot.json").exists()
    finally:
        monitor.analysis.close()


def test_root_cover_uses_existing_4000_character_view(tmp_path, monkeypatch):
    monitor, _, _ = _make_monitor(tmp_path, monkeypatch=monkeypatch)
    try:
        state = "Root support cover, natural prose.\n" + "w" * 4100 + "UNSEEN_TAIL_MARKER"
        (tmp_path / "monitor" / "working.md").write_text(state, encoding="utf-8")
        view, metadata = dcec_working_context(monitor.workspace)
        assert metadata["limit_characters"] == 4000
        assert metadata["visible_characters"] == 4000
        assert metadata["truncated"] is True
        assert state[:4000] in view
        assert "UNSEEN_TAIL_MARKER" not in view
        assert "use file_read if more is needed" in view
    finally:
        monitor.analysis.close()


def test_continuation_keeps_root_cover_without_control_tools(tmp_path, monkeypatch):
    state = "Whole-task root; support witness A under premise B; focal contrast C."
    monitor, client, captured = _make_monitor(
        tmp_path, scripted=[[{"type": "text", "text": state}], _tool("wait", after_turns=1)],
        monkeypatch=monkeypatch)
    try:
        (tmp_path / "monitor" / "working.md").write_text(state, encoding="utf-8")
        assert monitor._prepare_continuation() == state
        assert captured[0]["tools"] == []
        assert CONTINUATION_MODE_PROMPT in captured[0]["system"]
        assert DCEC_CONTINUATION_PROMPT in captured[0]["messages"][-1]["content"][0]["text"]
        assert "bounded temporary root support cover" in DCEC_CONTINUATION_PROMPT
        assert "one current focal contrast" in DCEC_CONTINUATION_PROMPT
        assert "cannot allow_complete or intervene" in DCEC_CONTINUATION_PROMPT
        assert (tmp_path / "monitor" / "working.md").read_text(encoding="utf-8") == state
        assert monitor.review("After maintenance.").kind == "wait"
        assert CONTINUATION_MODE_PROMPT not in captured[1]["system"]
        assert captured[1]["system"].count(DCEC_SYSTEM_PROMPT) == 1
        assert state in json.dumps(captured[1]["messages"])
        assert client.complete_calls == 1  # maintenance uses the existing request path, not a new stage
    finally:
        monitor.analysis.close()


def test_intervene_invalidates_old_completion_without_new_guard(tmp_path, monkeypatch):
    monitor, _, _ = _make_monitor(tmp_path, scripted=[], monkeypatch=monkeypatch)
    current = {"request_id": "completion-1", "generation": 1, "cursor": 7}
    monitor.completion_state = lambda: current
    monitor.intervention_callback = lambda message: {"delivered": True, "message": message}
    try:
        monitor._refresh_completion()
        outcome = monitor.dispatch("intervene", {"message": "Correct the public mismatch."})
        assert outcome.data["status"] == "submitted"
        assert monitor.dispatch("allow_complete", {}).data["status"] == "error"
        current = {"request_id": "completion-2", "generation": 2, "cursor": 10}
        monitor._refresh_completion()
        approved = monitor.dispatch("allow_complete", {})
        assert approved.action.kind == "allow_complete"
        assert approved.action.payload["request_id"] == "completion-2"
    finally:
        monitor.analysis.close()


@pytest.mark.parametrize("flag", ["monitor_inquiry", "monitor_pma_memory",
                                   "monitor_grounded_context", "monitor_active_working_context"])
def test_historical_candidates_remain_exclusive(tmp_path, flag):
    task = tmp_path / "task"
    task.mkdir()
    config = _config(True)
    config[flag] = True
    client = MonitorProviderClient("claude_monitor_opus48", config)
    with pytest.raises(ValueError, match="cannot be stacked"):
        MonitorAgent(client, MonitorWorkspace(task, tmp_path / "monitor"))


if __name__ == "__main__" and sys.argv[1:2] == ["--capture-off"]:
    requests.post = lambda *a, **k: (_ for _ in ()).throw(
        AssertionError("external transport must not be used"))
    print(json.dumps(_capture_off(Path(sys.argv[2])), ensure_ascii=False, sort_keys=True))
