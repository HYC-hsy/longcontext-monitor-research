"""Offline path-transition facts; these tests do not measure model adoption."""

import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time

import pytest

from monitor_agent_core.runtime import WorkspaceTransitionSampler
from monitor_agent_core.runtime import _worker


PARENT = "e52107808527cb42ad2169db721b69b450a674fc"
TOOLS = ["file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]


def root():
    return Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", "-C", str(root()), *args], text=True).strip()


def put(workspace, relative, value):
    path = workspace / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def sample(sampler, workspace, cursor):
    return sampler.sample(workspace, cursor=cursor, task_turn=cursor)


def test_topology_and_production_scope():
    head = git("rev-parse", "HEAD")
    if head == PARENT:
        pytest.skip("candidate not committed yet")
    assert git("rev-list", "--parents", "-n", "1", "HEAD").split() == [head, PARENT]
    changed = set(git("diff", "--name-only", PARENT, head).splitlines())
    assert {p for p in changed if p.startswith("GenericAgent-main/monitor_agent_core/")} == {
        "GenericAgent-main/monitor_agent_core/runtime.py"}


def test_v0c_prompt_and_working_guidance_bytes_unchanged():
    parent = Path(os.environ["WORKSPACE_TRANSITION_PARENT_SOURCE"]).resolve()
    assert subprocess.check_output(["git", "-C", str(parent), "rev-parse", "HEAD"],
                                   text=True).strip() == PARENT
    for name in ("agent.py", "working_context.py"):
        relative = f"GenericAgent-main/monitor_agent_core/{name}"
        # Git's Windows checkout may mix CRLF/LF; compare exact stored content.
        assert subprocess.check_output(["git", "-C", str(root()), "show", f"{PARENT}:{relative}"]) == \
            (root() / relative).read_bytes().replace(b"\r\n", b"\n")


def test_dcec_off_full_provider_ready_request_equals_v0c(tmp_path):
    parent = Path(os.environ["WORKSPACE_TRANSITION_PARENT_SOURCE"]).resolve()
    assert subprocess.check_output(["git", "-C", str(parent), "rev-parse", "HEAD"],
                                   text=True).strip() == PARENT
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("A neutral public task.\n", encoding="utf-8")
    script = r"""
import json, pathlib, sys
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
import monitor_agent_core.agent as agent_module
import monitor_agent_core.provider as provider_module
source = pathlib.Path(sys.argv[3]).resolve()
for module in (agent_module, provider_module):
    assert pathlib.Path(module.__file__).resolve().is_relative_to(source / 'GenericAgent-main')
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
assert client.complete_calls == 1
"""

    def capture(source):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source / "GenericAgent-main")
        output = subprocess.check_output(
            [sys.executable, "-c", script, str(evidence), str(tmp_path / "private"), str(source)],
            env=env, cwd=str(source / "GenericAgent-main"), text=True)
        payload = json.loads(output.strip().splitlines()[-1])
        payload["review_id"] = "<generated-review-id>"
        return payload

    assert capture(parent) == capture(root())
    assert [t["function"]["name"] for t in capture(root())["tools"]] == TOOLS


def test_initial_baseline_and_filesystem_delta_without_task_tool_events(tmp_path):
    put(tmp_path, "unchanged.txt", "same")
    old = put(tmp_path, "delete.txt", "old")
    changed = put(tmp_path, "modify.txt", "old")
    sampler = WorkspaceTransitionSampler()
    view, audit = sample(sampler, tmp_path, 0)
    assert audit["initial_baseline"] and audit["sample_complete"]
    assert audit["total_changed"] == 0 and "baseline" in view
    old.unlink()
    put(tmp_path, "add.txt", "new")
    changed.write_text("new content", encoding="utf-8")
    view, audit = sample(sampler, tmp_path, 10)
    assert audit["from_cursor"] == 0 and audit["to_cursor"] == 10
    assert audit["added"] == ["task/workspace/add.txt"]
    assert audit["modified"] == ["task/workspace/modify.txt"]
    assert audit["deleted"] == ["task/workspace/delete.txt"]
    assert "unchanged.txt" not in view
    assert "task/workspace/modify.txt" in view
    assert "ground_valid" not in view and "ground_invalid" not in view


def test_design_vectors_are_only_path_facts(tmp_path):
    sampler = WorkspaceTransitionSampler()
    endpoint = put(tmp_path, "pkg/endpoint/endpoint.go", "state A")
    hyperlink = put(tmp_path, "widget/hyperlink.go", "callback")
    direct = put(tmp_path, "direct/observed.go", "unchanged")
    sample(sampler, tmp_path, 0)
    endpoint.write_text("state B", encoding="utf-8")  # T2-like related rewrite
    view, audit = sample(sampler, tmp_path, 1)
    assert audit["modified"] == ["task/workspace/pkg/endpoint/endpoint.go"]
    assert "T2" not in view and "reopen" not in view.lower()
    for name in ("client/option_unary.go", "client/option_stream.go",
                 "internal/option_wiring.go", "pkg/endpoint/endpoint.go"):
        put(tmp_path, name, f"rewrite {name}")
    view, audit = sample(sampler, tmp_path, 2)  # T5-like multi-file rewrite
    assert set(audit["added"] + audit["modified"]) == {
        f"task/workspace/{name}" for name in (
            "client/option_unary.go", "client/option_stream.go",
            "internal/option_wiring.go", "pkg/endpoint/endpoint.go")}
    put(tmp_path, "data/validation/all.go", "unrelated validation")
    view, audit = sample(sampler, tmp_path, 3)  # Hyperlink positive carry vector
    assert audit["added"] == ["task/workspace/data/validation/all.go"]
    assert "hyperlink" not in view.lower()
    put(tmp_path, "direct/observed.go", "unchanged // comment")
    view, audit = sample(sampler, tmp_path, 4)  # Same-file irrelevant edit
    assert audit["modified"] == ["task/workspace/direct/observed.go"]
    assert "invalid" not in view.lower()
    put(tmp_path, "other/dispatch.go", "new wiring")
    view, audit = sample(sampler, tmp_path, 5)  # Cross-file related edit
    assert audit["added"] == ["task/workspace/other/dispatch.go"]
    assert "direct/observed.go" not in view
    view, audit = sample(sampler, tmp_path, 6)  # Fyne no-op boundary: no transition
    assert audit["total_changed"] == 0
    assert "behavior verified" not in view.lower()
    assert "semantic grounds" in view or "semantic basis" in view
    assert hyperlink.is_file() and direct.is_file()


def test_git_and_symlinks_excluded(tmp_path):
    put(tmp_path, ".git/objects/object", "one")
    sampler = WorkspaceTransitionSampler()
    sample(sampler, tmp_path, 0)
    put(tmp_path, ".git/objects/object", "two")
    _, audit = sample(sampler, tmp_path, 1)
    assert audit["total_changed"] == 0


def test_symlink_target_not_followed(tmp_path):
    external = tmp_path.parent / f"external-{tmp_path.name}"
    external.mkdir()
    put(external, "outside.txt", "one")
    link = tmp_path / "linked"
    try:
        os.symlink(external, link, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    sampler = WorkspaceTransitionSampler()
    sample(sampler, tmp_path, 0)
    put(external, "outside.txt", "two")
    _, audit = sample(sampler, tmp_path, 1)
    assert audit["total_changed"] == 0


@pytest.mark.parametrize("dcec_enabled", [True, False])
def test_worker_samples_initial_ordinary_and_root_review(tmp_path, monkeypatch, dcec_enabled):
    """Use actual worker wake routing, with only provider/monitor responses faked."""
    import monitor_agent_core.agent as agent_module
    import monitor_agent_core.provider as provider_module

    reviews = []

    class FakeClient:
        def __init__(self, *args):
            pass

    class FakeMonitor:
        def __init__(self, client, workspace, *args, **kwargs):
            pass

        def review(self, context, completion_pending=False):
            reviews.append((context, completion_pending))
            return type("Action", (), {"kind": "wait", "payload": {"after_turns": 1, "mode": "patrol"}})()

    FakeMonitor.dcec_enabled = dcec_enabled

    class Value:
        value = 0

        def get_lock(self):
            return threading.Lock()

    monkeypatch.setattr(provider_module, "MonitorProviderClient", FakeClient)
    monkeypatch.setattr(agent_module, "MonitorAgent", FakeMonitor)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    put(workspace, "initial.txt", "baseline")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    private = tmp_path / "private"
    commands, outputs = queue.Queue(), queue.Queue()
    active_completion = Value()
    config = {
        "config_name": "offline", "model_config": {"monitor_live_intervention": False},
        "evidence_root": str(evidence), "private_root": str(private),
        "task_workspace": str(workspace), "max_review_turns": 2,
        "stop_event": threading.Event(), "active_completion": active_completion,
        "completion_cursor": Value(), "latest_task_turn": Value(),
    }
    worker = threading.Thread(target=_worker, args=(config, commands, outputs), daemon=True)
    worker.start()
    assert outputs.get(timeout=5)["kind"] == "ready"
    assert len(reviews) == 1
    assert ("baseline established" in reviews[0][0]) == dcec_enabled

    def await_reviews(count):
        deadline = time.monotonic() + 5
        while len(reviews) < count and time.monotonic() < deadline:
            time.sleep(.01)
        assert len(reviews) == count

    put(workspace, "initial.txt", "changed")
    commands.put({"kind": "boundary", "cursor": 10, "task_turn": 1})
    await_reviews(2)
    assert len(reviews) == 2
    assert ("modified:" in reviews[1][0]) == dcec_enabled
    active_completion.value = 1
    put(workspace, "new.txt", "added")
    commands.put({"kind": "completion", "cursor": 20, "task_turn": 2,
                  "generation": 1, "request_id": "completion-1"})
    await_reviews(3)
    assert len(reviews) == 3 and reviews[2][1]
    assert ("task/workspace/new.txt" in reviews[2][0]) == dcec_enabled
    commands.put({"kind": "close"})
    worker.join(timeout=5)
    assert not worker.is_alive()
    audit_path = private / "audit" / "workspace_transitions.jsonl"
    if dcec_enabled:
        audits = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]
        assert len(audits) == 3
        assert [event["to_cursor"] for event in audits] == [0, 10, 20]
        assert audits[2]["added"] == ["task/workspace/new.txt"]
    else:
        assert not audit_path.exists()


def test_incomplete_scan_does_not_claim_unchanged_or_advance_baseline(tmp_path, monkeypatch):
    put(tmp_path, "sub/file.txt", "old")
    sampler = WorkspaceTransitionSampler()
    sample(sampler, tmp_path, 1)
    put(tmp_path, "sub/file.txt", "new content")
    original = os.scandir

    def denied(path):
        if Path(path).name == "sub":
            raise PermissionError("synthetic scan denial")
        return original(path)

    monkeypatch.setattr(os, "scandir", denied)
    view, audit = sample(sampler, tmp_path, 2)
    assert not audit["sample_complete"]
    assert audit["error_types"] == ["PermissionError"]
    assert "sample incomplete" in view and "delta unavailable" in view
    monkeypatch.setattr(os, "scandir", original)
    _, audit = sample(sampler, tmp_path, 3)
    assert audit["from_cursor"] == 1
    assert audit["modified"] == ["task/workspace/sub/file.txt"]


def test_path_cap_preserves_full_audit(tmp_path):
    sampler = WorkspaceTransitionSampler()
    sample(sampler, tmp_path, 0)
    for index in range(70):
        put(tmp_path, f"f{index:03}.txt", "x")
    view, audit = sample(sampler, tmp_path, 1)
    assert audit["total_changed"] == 70
    assert len(audit["added"]) == 70
    assert audit["model_visible_truncated"]
    assert "view truncated: showing 64 of 70" in view
    assert "task/workspace/f069.txt" not in view


@pytest.mark.parametrize("count", [100, 1000, 3000])
def test_sampling_telemetry(tmp_path, count):
    sampler = WorkspaceTransitionSampler()
    for index in range(count):
        put(tmp_path, f"part/{index:04}.txt", "a")
    start = time.perf_counter()
    _, baseline = sample(sampler, tmp_path, 0)
    baseline_ms = (time.perf_counter() - start) * 1000
    put(tmp_path, "part/0000.txt", "larger replacement")
    start = time.perf_counter()
    _, incremental = sample(sampler, tmp_path, 1)
    incremental_ms = (time.perf_counter() - start) * 1000
    assert baseline["sample_complete"] and incremental["sample_complete"]
    assert incremental["modified"] == ["task/workspace/part/0000.txt"]
    print(json.dumps({"files": count, "baseline_wall_ms": round(baseline_ms, 3),
                      "incremental_wall_ms": round(incremental_ms, 3)}))
