"""Generate complete, redacted provider-ready request originals without network access."""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from test_experimental_control import make_agent, tool, frozen_agent_class


def _write_sample(destination, name, request, root):
    # Only a synthetic filesystem locator is redacted; no semantic text or tool
    # schema is removed. Provider-ready structure is otherwise complete.
    root_forms = [str(root)]
    for _ in range(3):
        root_forms.append(json.dumps(root_forms[-1], ensure_ascii=False)[1:-1])

    def redact(value):
        if isinstance(value, str):
            for form in reversed(root_forms):
                value = value.replace(form, "<OFFLINE_ROOT>")
            return value
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        return value
    sanitized = redact(request)
    encoded = (json.dumps(sanitized, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    assert all(form not in encoded.decode("utf-8") for form in root_forms)
    assert "apikey" not in encoded.decode("utf-8")
    assert "https://invalid.example" not in encoded.decode("utf-8")
    path = destination / f"{name}.json"
    path.write_bytes(encoded)
    return {"file": path.name, "sha256": hashlib.sha256(encoded).hexdigest(),
            "characters": len(encoded.decode("utf-8")), "utf8_bytes": len(encoded)}


def generate_samples(destination):
    destination.mkdir(parents=True, exist_ok=True)
    samples = {}
    with tempfile.TemporaryDirectory(prefix="uc-r5-offline-") as directory:
        root = Path(directory)
        answer = tool("wait", after_turns=1)
        base, _, frozen_requests, ws = make_agent(root / "off", [answer],
                                                  klass=frozen_agent_class())
        candidate, _, candidate_requests, _ = make_agent(root / "off2", [answer],
                                                          same_workspace=ws)
        base.review("Ordinary public wake")
        candidate.review("Ordinary public wake")
        assert {k: v for k, v in frozen_requests[0].items() if k != "review_id"} == {
            k: v for k, v in candidate_requests[0].items() if k != "review_id"}
        samples["off_frozen"] = _write_sample(destination, "off_frozen", frozen_requests[0], root)
        samples["off_candidate"] = _write_sample(destination, "off_candidate", candidate_requests[0], root)

        for mode, label in (("flat", "R_flat"), ("framed", "A_framed")):
            scripted = [tool("work_context", action="select", question="Does observed behavior meet the public task?",
                             sources=[{"path": "task/original_task.txt"},
                                      {"path": "task/workspace/component.py"}]), answer]
            agent, _, sent, _ = make_agent(root / label, scripted, view=mode)
            agent.review("Ordinary public wake")
            samples[label] = _write_sample(destination, label, sent[1], root)

        for mode, label in (("note", "P_note"), ("routed", "B_routed")):
            scripted = [tool("work_intent", action="set", text="Check actual behavior"), answer]
            agent, _, sent, _ = make_agent(root / label, scripted, intent=mode)
            agent.review("Ordinary public wake")
            samples[label] = _write_sample(destination, label, sent[1], root)

        combo_root = root / "combined"
        scripted = [tool("work_context", action="select", question="Q" * 1200,
                         sources=[{"path": f"task/workspace/part{i}.txt", "count": 1000}
                                  for i in range(4)])
                    + tool("work_intent", action="set", text="I" * 1200, watch_session="s"),
                    tool("file_read", path="task/original_task.txt"),
                    tool("file_read", path="task/original_task.txt"), answer]
        agent, _, sent, ws = make_agent(combo_root, scripted, view="framed", intent="routed", window=1)
        for index in range(4):
            (ws.task_mounts["workspace"] / f"part{index}.txt").write_text(
                ('\\"\n\t' * 1100) + "多" * 500, encoding="utf-8")
        class Event:
            def is_set(self): return False
        class Process:
            def poll(self): return None
        output = combo_root / "output.log"
        output.write_bytes(b"unread")
        agent.analysis.sessions["s"] = {"done": Event(), "process": Process(), "output": output,
                                         "cursor": 0, "reason": None}
        agent.review("Ordinary public wake")
        samples["combined_budget"] = _write_sample(destination, "combined_budget", sent[2], root)

        temporal_root = root / "return"
        scripted = [tool("work_intent", action="set", text="Observe", watch_session="s"),
                    tool("work_intent", action="return"), tool("allow_complete")]
        agent, _, sent, _ = make_agent(temporal_root, scripted, intent="routed")
        pending = {"value": None}
        agent.completion_state = lambda: pending["value"]
        class MutableEvent:
            done = False
            def is_set(self): return self.done
        class MutableProcess:
            def poll(self): return 0 if done.done else None
        done = MutableEvent()
        output = temporal_root / "output.log"
        output.write_bytes(b"unread")
        agent.analysis.sessions["s"] = {"done": done, "process": MutableProcess(),
                                         "output": output, "cursor": 1, "reason": None}
        original_dispatch = agent.dispatch
        def after_return(name, arguments):
            outcome = original_dispatch(name, arguments)
            if name == "work_intent" and arguments["action"] == "return":
                pending["value"] = {"generation": 1, "request_id": "scripted-root", "cursor": 4}
                done.done = True
            return outcome
        agent.dispatch = after_return
        agent.review("Ordinary public wake")
        samples["return_boundary"] = _write_sample(destination, "return_boundary", sent[2], root)

    manifest = {"kind": "scripted_offline_provider_ready_requests",
                "frozen_parent": "6c72477fce3350c82baf74a9ca8a96c87742be5b",
                "off_off_equality": {"equal": True, "normalized_fields": ["review_id"]},
                "redaction": "Only the synthetic absolute root is replaced by <OFFLINE_ROOT>; semantic text is unchanged.",
                "real_model_requests": 0, "samples": samples}
    encoded = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    (destination / "MANIFEST.json").write_bytes(encoded)
    return manifest


def test_complete_redacted_samples_have_recomputable_hashes(tmp_path, monkeypatch):
    monkeypatch.setattr(requests.Session, "request", lambda *_args, **_kwargs: (
        _ for _ in ()).throw(AssertionError("sample generation attempted network")))
    manifest = generate_samples(tmp_path / "samples")
    assert set(manifest["samples"]) == {"off_frozen", "off_candidate", "R_flat", "A_framed",
                                        "P_note", "B_routed", "combined_budget", "return_boundary"}
    for item in manifest["samples"].values():
        content = (tmp_path / "samples" / item["file"]).read_bytes()
        assert hashlib.sha256(content).hexdigest() == item["sha256"]
        parsed = json.loads(content)
        assert set(parsed) >= {"system", "messages", "tools", "model_parameters", "root_handoff"}


def test_synthetic_root_is_redacted_inside_nested_json_strings(tmp_path):
    root = Path("E:/offline-synthetic-root")
    plain = str(root)
    embedded = json.dumps({"task/workspace/": plain})
    twice = json.dumps({"environment": embedded})
    request = {"plain": plain, "environment": embedded, "nested": twice}
    item = _write_sample(tmp_path, "nested", request, root)
    raw = (tmp_path / item["file"]).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == item["sha256"]
    saved = json.loads(raw)
    assert saved["plain"] == "<OFFLINE_ROOT>"
    assert json.loads(saved["environment"])["task/workspace/"] == "<OFFLINE_ROOT>"
    assert json.loads(json.loads(saved["nested"])["environment"])["task/workspace/"] == "<OFFLINE_ROOT>"


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("usage: python tests/test_experimental_control_samples.py OUTPUT_DIRECTORY")
    requests.Session.request = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("offline sample generation attempted network"))
    generate_samples(Path(sys.argv[1]))
