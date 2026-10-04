"""EIS-v0 mechanical indexing and zero-network provider-ready assembly."""

import json
import threading
from types import SimpleNamespace

from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.eis_v0 import (GUIDANCE, INDEX_NAME, SURFACE_LIMIT,
                                       append_index, executable_interpretation_surface)
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.runtime import MonitorRuntime
from monitor_agent_core.workspace import MonitorWorkspace


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("Maintain the public route.\n", encoding="utf-8")
    task = tmp_path / "workspace"
    task.mkdir()
    return MonitorWorkspace(evidence, tmp_path / "private", task_mounts={"workspace": task})


def event(seq, name, args, result, *, boundary="post_tool_pre_next_llm", call_id=None):
    ident = call_id or f"call-{seq}"
    return {"archive_sequence": seq, "task_turn": seq, "boundary": boundary,
            "tool_calls": [{"name": name, "args": args, "id": ident}],
            "tool_results": [{"tool_use_id": ident, "content": json.dumps(result)}]}


def add(ws, row):
    with (ws.evidence_root / "public_events.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    return append_index(ws.evidence_root, row)


def test_actual_archive_incremental_index_and_nonblocking_index_error(tmp_path, monkeypatch):
    runtime = MonitorRuntime.__new__(MonitorRuntime)
    runtime._archive_lock = threading.Lock()
    runtime._sequence = 0
    runtime.evidence_root = tmp_path
    runtime.private_root = tmp_path
    runtime.events_path = tmp_path / "public_events.jsonl"
    runtime.synopsis_path = tmp_path / "synopsis.jsonl"
    runtime._latest_task_turn = SimpleNamespace(value=0, get_lock=threading.Lock)
    runtime._eis_enabled = True
    packet = event(1, "file_write", {"path": "/app/x_test.go", "content": "check"}, {"status": "success"})
    assert runtime._archive(packet) == 1
    assert (tmp_path / INDEX_NAME).is_file()
    assert runtime._latest_task_turn.value == 1
    monkeypatch.setattr("monitor_agent_core.runtime.append_eis_index", lambda *_: (_ for _ in ()).throw(OSError("offline")))
    assert runtime._archive(packet) == 2
    assert len(runtime.events_path.read_text(encoding="utf-8").splitlines()) == 2
    assert "OSError" in (tmp_path / "eis_index_errors.jsonl").read_text(encoding="utf-8")


def test_successful_authored_change_and_actual_execution_with_source_pairing(tmp_path):
    ws = workspace(tmp_path)
    change = event(1, "file_write", {"path": "/app/pkg/route_test.go", "content": "assertRoute()\n"},
                   {"status": "success", "writed_bytes": 14})
    assert add(ws, change) == 1
    run = event(2, "code_run", {"script": "go test ./pkg", "type": "bash", "cwd": "/app"},
                {"status": "error", "exit_code": 1, "stdout": "FAIL route", "stderr": "trace"})
    assert add(ws, run) == 1
    rows = [json.loads(line) for line in (ws.evidence_root / INDEX_NAME).read_text(encoding="utf-8").splitlines()]
    assert rows[0]["path"] == "task/workspace/pkg/route_test.go"
    assert rows[0]["authored_excerpt"] == "assertRoute()\\n"
    assert rows[1]["exit_code"] == 1 and rows[1]["status"] == "error"
    block, meta = executable_interpretation_surface(ws)
    assert "task/public_events.jsonl#1" in block and "task/public_events.jsonl#2" in block
    assert "go test ./pkg" in block and "FAIL route" in block and "assertRoute()" in block
    assert meta["event_locators"] == ["task/public_events.jsonl#1", "task/public_events.jsonl#2"]
    assert len(block) <= SURFACE_LIMIT


def test_failed_write_unpaired_return_and_non_test_actions_are_not_indexed(tmp_path):
    ws = workspace(tmp_path)
    assert add(ws, event(1, "file_patch", {"path": "/app/pkg/route_test.go", "new_content": "bad"},
                         {"status": "error", "error": "not found"})) == 0
    assert add(ws, event(2, "file_write", {"path": "/app/pkg/route.go", "content": "source"},
                         {"status": "success"})) == 0
    assert add(ws, event(3, "code_run", {"script": "go build ./..."},
                         {"status": "success", "exit_code": 0})) == 0
    missing = event(4, "file_write", {"path": "/app/route_test.go", "content": "x"}, {"status": "success"})
    missing["tool_results"][0]["tool_use_id"] = "another-call"
    assert add(ws, missing) == 0
    assert add(ws, event(5, "file_write", {"path": "/app/route_test.go", "content": "x"},
                         {"status": "success"}, boundary="post_model_pre_tool")) == 0
    block, _ = executable_interpretation_surface(ws)
    assert "No candidate validation activity" not in block  # missing index has an explicit boundary
    assert "index_missing" in block and not (ws.evidence_root / INDEX_NAME).exists()


def test_repeated_changes_and_executions_are_bounded_and_not_mispaired(tmp_path):
    ws = workspace(tmp_path)
    for seq in range(1, 180):
        add(ws, event(seq, "file_patch", {"path": "/app/tests/test_route.py", "new_content": f"assert {seq} " + "x" * 900},
                      {"status": "success"}))
    add(ws, event(180, "code_run", {"script": "python -m pytest tests/test_route.py"},
                  {"status": "success", "exit_code": 0, "stdout": "old result"}))
    add(ws, event(181, "code_run", {"script": "python -m pytest tests/test_route.py"},
                  {"status": "error", "exit_code": 2, "stdout": "new result"}))
    block, _ = executable_interpretation_surface(ws)
    assert len(block) <= SURFACE_LIMIT
    assert "task/public_events.jsonl#179" in block
    assert "task/public_events.jsonl#181" in block and "task/public_events.jsonl#180" in block
    assert "changed again" in block or "Earlier same path/command" in block
    # A return for another call cannot be paired with the candidate test command.
    wrong = event(182, "code_run", {"script": "go test ./..."}, {"status": "success"})
    wrong["tool_results"][0]["tool_use_id"] = "not-call-182"
    assert add(ws, wrong) == 0


def _provider_request(ws, monkeypatch, enabled, root=False):
    config = {"apikey": "offline", "apibase": "https://offline.invalid", "model": "offline",
              "max_retries": 0, "monitor_dcec": True, "monitor_path_control_v0": True,
              "monitor_verification_loop_v0": True, "monitor_verification_runtime_managed": False,
              "monitor_executable_interpretation_surface": enabled}
    client = MonitorProviderClient("anthropic", config)
    monitor = MonitorAgent(client, ws)
    requests = []

    class Captured(Exception):
        pass

    def no_network(tools):
        requests.append(client.assembled_request_snapshot(tools))
        raise Captured

    monkeypatch.setattr(client, "_request_once", no_network)
    if root:
        handoff = {"generation": 1, "request_id": "root-1", "cursor": 2, "task_turn": 2}
        monitor.completion_state = lambda: handoff
        try:
            monitor.review("Root review", completion_pending=True, root_handoff=handoff)
        except Captured:
            pass
    else:
        try:
            monitor.review("Ordinary review")
        except Captured:
            pass
    assert len(requests) == 1
    return requests[0]


def test_provider_visible_off_on_and_same_root_ordinary_facts(tmp_path, monkeypatch):
    ws = workspace(tmp_path)
    add(ws, event(1, "file_write", {"path": "/app/route_test.go", "content": "assert route"},
                  {"status": "success"}))
    add(ws, event(2, "code_run", {"script": "go test ./..."},
                  {"status": "success", "exit_code": 0, "stdout": "ok"}))
    off = _provider_request(ws, monkeypatch, False)
    on = _provider_request(ws, monkeypatch, True)
    root = _provider_request(ws, monkeypatch, True, root=True)
    off_text, on_text, root_text = (json.dumps(x, ensure_ascii=False) for x in (off, on, root))
    assert "Executable Interpretation Surface" not in off_text and GUIDANCE not in off["system"]
    assert "Executable Interpretation Surface" in on_text and GUIDANCE in on["system"]
    assert "Executable Interpretation Surface" in root_text and "task/public_events.jsonl#2" in root_text
    assert "task/workspace/route_test.go" in on_text and "task/workspace/route_test.go" in root_text
    assert len(on["tools"]) == len(off["tools"]) == len(root["tools"]) == 7
    assert on["tools"] == off["tools"] == root["tools"]
    assert on["system"].replace("\n\n" + GUIDANCE, "") == off["system"]
