import json
import time

import pytest

from monitor_agent_core.checkpoint import (
    capture_live_root_checkpoint, extract_root_checkpoint_archive,
    load_root_checkpoint, package_root_checkpoint, restored_request,
    write_root_checkpoint)
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient, RetryableProviderError
from monitor_agent_core.workspace import MonitorWorkspace


def _materials(tmp_path):
    events = tmp_path / "public_events.jsonl"
    events.write_text(json.dumps({"archive_sequence": 1, "text": "done"}) + "\n", encoding="utf-8")
    synopsis = tmp_path / "synopsis.jsonl"
    synopsis.write_text(json.dumps({"cursor": 1, "intent": "done"}) + "\n", encoding="utf-8")
    workspace = tmp_path / "view"
    (workspace / "workspace").mkdir(parents=True)
    (workspace / "original_task.txt").write_text("Do the task.", encoding="utf-8")
    (workspace / "workspace" / "code.py").write_text("value = 1\n", encoding="utf-8")
    private = tmp_path / "private"
    private.mkdir()
    (private / "working.md").write_text("Current judgment.", encoding="utf-8")
    return events, synopsis, workspace, private


def _request(generation=1):
    return {
        "review_id": "review-1", "request_sequence": 3, "purpose": "review",
        "system": "stable system",
        "messages": [{"role": "user", "content": [{"type": "text", "text": "dynamic once"}]}],
        "tools": [{"type": "function", "function": {"name": "wait"}}],
        "model_parameters": {"model": "test", "api_mode": "chat"},
        "root_handoff": {"generation": generation, "request_id": f"completion-{generation}", "cursor": 1},
    }


def _live_workspace(tmp_path, events=1):
    evidence = tmp_path / "evidence"
    private = tmp_path / "private"
    live = tmp_path / "live"
    evidence.mkdir(); private.mkdir(); live.mkdir()
    (evidence / "original_task.txt").write_text("Do the task.", encoding="utf-8")
    (evidence / "synopsis.jsonl").write_text(
        "".join(json.dumps({"cursor": i, "intent": f"event {i}"}) + "\n"
                for i in range(1, events + 1)), encoding="utf-8")
    (evidence / "public_events.jsonl").write_text(
        "".join(json.dumps({"archive_sequence": i, "text": f"event {i}"}) + "\n"
                for i in range(1, events + 1)), encoding="utf-8")
    (live / "code.py").write_text("value = 1\n", encoding="utf-8")
    (private / "working.md").write_text("Current judgment.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, private, task_mounts={"workspace": live}), live


def test_checkpoint_roundtrip_is_exact_and_frozen(tmp_path):
    events, synopsis, workspace, private = _materials(tmp_path)
    request = _request()
    checkpoint = write_root_checkpoint(
        checkpoint_root=tmp_path / "checkpoints", checkpoint_id="checkpoint-0001",
        request=request, identity={"handoff": request["root_handoff"], "review_id": "review-1"},
        event_source=events, synopsis_source=synopsis,
        task_snapshot=workspace, private_root=private)
    loaded = load_root_checkpoint(checkpoint)
    assert restored_request(checkpoint) == request
    assert loaded["manifest"]["path_map"]["task/workspace/"] == "task/workspace/"
    (workspace / "workspace" / "code.py").write_text("value = 2\n", encoding="utf-8")
    assert (loaded["root"] / "task/workspace/code.py").read_text() == "value = 1\n"


@pytest.mark.parametrize("relative", ["request.json", "monitor/state/working.md"])
def test_checkpoint_loader_rejects_mutation(tmp_path, relative):
    events, synopsis, workspace, private = _materials(tmp_path)
    checkpoint = write_root_checkpoint(
        checkpoint_root=tmp_path / "checkpoints", checkpoint_id="checkpoint-0001",
        request=_request(), identity={"handoff": _request()["root_handoff"]},
        event_source=events, synopsis_source=synopsis,
        task_snapshot=workspace, private_root=private)
    path = checkpoint / relative
    path.write_text(path.read_text(encoding="utf-8") + "changed", encoding="utf-8")
    with pytest.raises(ValueError, match="hash changed"):
        load_root_checkpoint(checkpoint)


def test_request_capture_uses_observed_handoff_and_deduplicates_retry(tmp_path):
    client = MonitorProviderClient("test", {
        "apikey": "test", "apibase": "http://127.0.0.1", "model": "test",
        "provider": "openai", "api_mode": "chat", "max_retries": 1})
    client.system = "system"
    client.history = []
    client.prepare_active_context = lambda: "dynamic"
    captures = []
    client.request_assembly_callback = lambda snapshot: captures.append(snapshot) or True
    client._request_with_recovery = lambda tools: ([], {})
    client.observed_root_handoff = {"generation": 1, "request_id": "completion-1", "cursor": 1}
    client.complete([{"role": "user", "content": "first"}], [])
    client.complete([{"role": "user", "content": "same handoff"}], [])
    assert len(captures) == 1
    client.observed_root_handoff = {"generation": 2, "request_id": "completion-2", "cursor": 2}
    client.complete([{"role": "user", "content": "new handoff"}], [])
    assert [row["root_handoff"]["generation"] for row in captures] == [1, 2]


def test_live_capture_uses_exact_handoff_and_actual_writer_loader(tmp_path):
    workspace, live = _live_workspace(tmp_path)
    request = _request()
    current = dict(request["root_handoff"])
    checkpoint = capture_live_root_checkpoint(
        workspace=workspace, checkpoint_root=tmp_path / "checkpoints",
        snapshot=request, identity={"task_id": "task", "review_id": "review-1"},
        current_handoff=lambda: dict(current))
    assert restored_request(checkpoint) == request
    (live / "code.py").write_text("value = 2\n", encoding="utf-8")
    assert (checkpoint / "task/workspace/code.py").read_text() == "value = 1\n"


def test_live_capture_rejects_identity_change_without_completion_marker(tmp_path):
    workspace, _ = _live_workspace(tmp_path)
    request = _request()
    observed = [dict(request["root_handoff"]), {**request["root_handoff"], "generation": 2}]

    def current():
        return observed.pop(0) if len(observed) > 1 else observed[0]

    with pytest.raises(ValueError, match="changed during"):
        capture_live_root_checkpoint(
            workspace=workspace, checkpoint_root=tmp_path / "checkpoints",
            snapshot=request, identity={"task_id": "task"}, current_handoff=current)
    assert not list((tmp_path / "checkpoints").glob("checkpoint-*"))
    assert not list((tmp_path / "checkpoints").glob(".events-*"))


def test_live_capture_write_failure_leaves_no_valid_checkpoint(tmp_path, monkeypatch):
    workspace, _ = _live_workspace(tmp_path)
    request = _request()
    monkeypatch.setattr("monitor_agent_core.checkpoint.write_root_checkpoint",
                        lambda **_: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        capture_live_root_checkpoint(
            workspace=workspace, checkpoint_root=tmp_path / "checkpoints",
            snapshot=request, identity={"task_id": "task"},
            current_handoff=lambda: dict(request["root_handoff"]))
    assert not list((tmp_path / "checkpoints").glob("checkpoint-*"))
    assert not list((tmp_path / "checkpoints").glob(".events-*"))


def test_ordinary_review_can_observe_root_handoff_mid_review(tmp_path):
    workspace, _ = _live_workspace(tmp_path)
    client = MonitorProviderClient("test", {
        "apikey": "test", "apibase": "http://127.0.0.1", "model": "test",
        "provider": "openai", "api_mode": "chat"})
    state = {"value": None}
    agent = MonitorAgent(client, workspace)
    agent.completion_state = lambda: state["value"]
    assert agent._refresh_completion() is None
    state["value"] = {"generation": 1, "request_id": "completion-1", "cursor": 1}
    assert "waiting on a current handoff" in agent._refresh_completion()
    assert client.observed_root_handoff == state["value"]


def test_transport_retry_does_not_duplicate_checkpoint_callback():
    client = MonitorProviderClient("test", {
        "apikey": "test", "apibase": "http://127.0.0.1", "model": "test",
        "provider": "openai", "api_mode": "chat"})
    client.system = "system"
    client.observed_root_handoff = {"generation": 1, "request_id": "completion-1", "cursor": 1}
    captures, attempts = [], []
    client.request_assembly_callback = lambda snapshot: captures.append(snapshot) or True
    client.recovery_deadline = time.monotonic() + 60
    client.recovery_stop = type("Stop", (), {"is_set": lambda self: False,
                                               "wait": lambda self, _: False})()

    def request_batch(_):
        attempts.append(1)
        if len(attempts) == 1:
            raise RetryableProviderError("synthetic disconnect")
        return [], {}

    client._request_batch = request_batch
    client.complete([{"role": "user", "content": "review"}], [])
    assert len(attempts) == 2
    assert len(captures) == 1


def test_provider_restores_exact_send_boundary_without_duplicate_dynamic_context():
    config = {"apikey": "test", "apibase": "http://127.0.0.1", "model": "test",
              "provider": "openai", "api_mode": "chat", "max_tokens": 1234}
    source = MonitorProviderClient("test", config)
    source.system = "stable system"
    source.review_id = "review-1"
    source.complete_calls = 7
    source.history = [
        {"role": "user", "content": [{"type": "text", "text": "ordinary input"}]},
        {"role": "user", "content": [{"type": "text", "text": "dynamic context"}]},
    ]
    source.observed_root_handoff = {
        "generation": 2, "request_id": "completion-2", "cursor": 4}
    tools = [{"type": "function", "function": {"name": "wait"}}]
    captured = source.assembled_request_snapshot(tools)
    restored = MonitorProviderClient("test", config)
    assert restored.restore_request_snapshot(captured) == captured
    texts = [block.get("text") for message in restored.history
             for block in message.get("content", [])]
    assert texts.count("dynamic context") == 1


def test_checkpoint_single_file_transport_roundtrip(tmp_path):
    events, synopsis, workspace, private = _materials(tmp_path)
    root = write_root_checkpoint(
        checkpoint_root=tmp_path / "checkpoints", checkpoint_id="checkpoint-0001",
        request=_request(), identity={"handoff": _request()["root_handoff"]},
        event_source=events, synopsis_source=synopsis,
        task_snapshot=workspace, private_root=private)
    archive = package_root_checkpoint(root)
    shutil_target = tmp_path / "transported"
    extracted = extract_root_checkpoint_archive(archive, shutil_target)
    assert restored_request(extracted) == _request()
    assert (extracted / "task/workspace/code.py").read_text() == "value = 1\n"


def test_checkpoint_archive_rejects_unsafe_member(tmp_path):
    import io
    import tarfile
    archive = tmp_path / "unsafe.tar"
    with tarfile.open(archive, "w") as stream:
        info = tarfile.TarInfo("../escape")
        content = b"bad"
        info.size = len(content)
        stream.addfile(info, io.BytesIO(content))
    with pytest.raises(ValueError, match="unsafe"):
        extract_root_checkpoint_archive(archive, tmp_path / "extracted")
    assert not (tmp_path / "escape").exists()
