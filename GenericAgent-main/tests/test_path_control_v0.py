"""Offline assembly and public-event-window checks; no model service is contacted."""

import json

from monitor_agent_core.agent import DCEC_SYSTEM_PROMPT, MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.path_control_v0 import (
    CONTINUATION_PROMPT, SYSTEM_PROMPT, WINDOW_GUIDANCE, WORKING_GUIDANCE,
    recent_public_events,
)
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace


def make_workspace(tmp_path):
    evidence, private = tmp_path / "evidence", tmp_path / "private"
    evidence.mkdir(parents=True)
    (evidence / "original_task.txt").write_text("A public task.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, private)


def event(workspace, **fields):
    path = workspace.evidence_root / "public_events.jsonl"
    with path.open("a", encoding="utf-8") as out:
        out.write(json.dumps(fields, ensure_ascii=False) + "\n")


def request(tmp_path, enabled, monkeypatch):
    ws = make_workspace(tmp_path)
    event(ws, archive_sequence=1, task_turn=0, boundary="post_model_pre_tool",
          text="Task says done", tool_calls=[{"name": "code_run", "args": "run demo"}],
          tool_results=[], next_prompt="SECRET_NEXT", synopsis="SECRET_SYNOPSIS")
    event(ws, archive_sequence=2, task_turn=1, boundary="post_tool_pre_next_llm",
          text="Task observes output", tool_calls=[{"name": "code_run", "args": "run demo"}],
          tool_results=[{"tool_use_id": "x", "content": "actual output"}])
    client = MonitorProviderClient("anthropic", {
        "apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
        "max_retries": 0, "monitor_dcec": True, "monitor_path_control_v0": enabled,
        "monitor_dcec_working_chars": 4000,
    })
    monitor = MonitorAgent(client, ws)
    requests = []

    def no_network(tools):
        requests.append(client.assembled_request_snapshot(tools))
        return ([{"type": "tool_use", "id": "control", "name": "wait",
                  "input": {"after_turns": 1}}], {})

    monkeypatch.setattr(client, "_request_once", no_network)
    assert monitor.review("Ordinary review").kind == "wait"
    return requests[0], ws


def test_base_and_path_provider_ready_assembly(tmp_path, monkeypatch):
    base, _ = request(tmp_path / "base", False, monkeypatch)
    path, ws = request(tmp_path / "path", True, monkeypatch)
    assert DCEC_SYSTEM_PROMPT in base["system"]
    assert SYSTEM_PROMPT not in base["system"]
    assert SYSTEM_PROMPT in path["system"]
    assert DCEC_SYSTEM_PROMPT not in path["system"]
    assert [t["function"]["name"] for t in path["tools"]] == [
        t["function"]["name"] for t in MONITOR_TOOLS]
    assert len(path["tools"]) == 7
    visible = json.dumps(path, ensure_ascii=False)
    assert WORKING_GUIDANCE in visible and WINDOW_GUIDANCE in visible
    assert "actual output" in visible
    assert "SECRET_NEXT" not in visible and "SECRET_SYNOPSIS" not in visible
    assert "Task observes output" in visible and "tool_results: This record contains no tool return" not in visible
    audit = (ws.private_root / "audit" / "dialogue.jsonl").read_text(encoding="utf-8")
    assert "path_control_public_window" in audit and "task/public_events.jsonl#2" in audit
    assert "path_control_public_window" not in json.dumps(base)
    assert CONTINUATION_PROMPT != DCEC_SYSTEM_PROMPT


def test_missing_return_and_root_event_are_separate(tmp_path):
    ws = make_workspace(tmp_path)
    event(ws, archive_sequence=1, task_turn=1, boundary="post_tool_pre_next_llm",
          text="prior", tool_calls=[{"id": "old"}], tool_results=[{"content": "prior result"}])
    event(ws, archive_sequence=2, task_turn=2, boundary="task_control_handoff",
          text="completion proposed", tool_calls=[{"id": "new"}], tool_results=[])
    block, meta = recent_public_events(ws, {"cursor": 2})
    assert meta["source_lines"] == [2, 1]
    assert block.index("task/public_events.jsonl#2") < block.index("task/public_events.jsonl#1")
    assert "This record contains no tool return" in block
    assert "prior result" in block
    assert len(block) <= 2400


def test_long_event_partial_line_and_missing_file(tmp_path):
    ws = make_workspace(tmp_path)
    block, meta = recent_public_events(ws)
    assert "No complete public event" in block and meta["visible_boundary"] == "file_missing"
    event(ws, archive_sequence=1, task_turn=1, boundary="post_tool_pre_next_llm",
          text="z" * 8000, tool_calls=[{"args": "a" * 4000}],
          tool_results=[{"content": "b" * 4000}])
    with (ws.evidence_root / "public_events.jsonl").open("ab") as out:
        out.write(b'{"archive_sequence": 2')
    block, meta = recent_public_events(ws)
    assert len(block) <= 2400
    assert meta["visible_boundary"].startswith("trailing_partial_line")
    assert "omitted" in block and "task/public_events.jsonl#1" in block
    assert "archive_sequence=2" not in block
