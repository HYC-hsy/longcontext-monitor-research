"""Offline contract checks against real Monitor review/provider assembly."""

import hashlib
import json
import subprocess
import types
from pathlib import Path

import pytest
import requests

from monitor_agent_core.agent import MonitorAgent, MONITOR_TOOLS
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
from monitor_agent_core.experimental_control.adapter import (
    ExperimentalControl, GUIDANCE, WORK_CONTEXT_TOOL, WORK_INTENT_TOOL, EXTRA_BLOCK_LIMIT,
)


BASE = "6c72477fce3350c82baf74a9ca8a96c87742be5b"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def no_external_transport(monkeypatch):
    monkeypatch.setattr(requests.Session, "request", lambda *_args, **_kwargs: (
        _ for _ in ()).throw(AssertionError("offline experimental-control test attempted network")))


def frozen_agent_class():
    source = subprocess.check_output(
        ["git", "show", f"{BASE}:GenericAgent-main/monitor_agent_core/agent.py"],
        cwd=REPO).decode("utf-8")
    module = types.ModuleType("monitor_agent_core._frozen_agent")
    module.__package__ = "monitor_agent_core"
    exec(compile(source, f"git:{BASE}:agent.py", "exec"), module.__dict__)
    return module.MonitorAgent


def tool(name, **args):
    return [{"type": "tool_use", "id": f"offline-{name}-{hashlib.sha256(repr(args).encode()).hexdigest()[:8]}",
             "name": name, "input": args}]


def make_agent(tmp_path, responses, *, view="off", intent="off", window=4, klass=MonitorAgent,
          config_extra=None, same_workspace=None):
    if same_workspace is None:
        evidence = tmp_path / "task"
        private = tmp_path / "monitor"
        mounted = tmp_path / "workspace"
        evidence.mkdir(parents=True)
        mounted.mkdir(parents=True)
        (evidence / "original_task.txt").write_text("Public request: behavior must work.\n", encoding="utf-8")
        (evidence / "public_events.jsonl").write_text('{"text":"Agent claim: complete"}\n', encoding="utf-8")
        (mounted / "component.py").write_text("def run():\n    return '行为'\n", encoding="utf-8")
        ws = MonitorWorkspace(evidence, private, {"workspace": mounted})
    else:
        ws = same_workspace
    config = {"apikey": "offline", "apibase": "https://invalid.example", "model": "offline-model",
              "monitor_dcec": True, "monitor_semantic_continuity": True,
              "monitor_dcec_working_chars": 4000, "monitor_history_char_limit": 1000000}
    if klass is MonitorAgent:
        config.update(monitor_research_view=view, monitor_research_intent=intent,
                      monitor_research_intent_window_requests=window)
    if config_extra:
        config.update(config_extra)
    client = MonitorProviderClient("openai", config)
    sent = []
    answers = iter(responses)

    def fake_transport(tools):
        sent.append(client.assembled_request_snapshot(tools))
        return next(answers), {"input_tokens": 11, "output_tokens": 3}

    client._request_with_recovery = fake_transport
    agent = klass(client, ws, max_review_turns=30)
    return agent, client, sent, ws


def active_text(request):
    return "\n".join(block.get("text", "") for message in request["messages"]
                     for block in message.get("content", []) if isinstance(block, dict))


def tool_names(request):
    return [item["function"]["name"] for item in request["tools"]]


def candidate_events(workspace, event=None):
    path = workspace.private_root / "audit" / "experimental_control.jsonl"
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return [row for row in rows if row["event"] == event] if event else rows


def artifact(workspace, reference):
    path = workspace.private_root / Path(reference["path"]).relative_to("monitor")
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == reference["sha256"]
    assert len(raw) == reference["utf8_bytes"]
    return json.loads(raw)


def test_t01_t02_frozen_off_provider_ready_equality_and_no_state(tmp_path):
    frozen = frozen_agent_class()
    answer = tool("wait", after_turns=1)
    a, _, actual, ws = make_agent(tmp_path / "same", [answer])
    # Both implementations execute the same real review -> provider assembly path.
    b, _, expected, _ = make_agent(tmp_path / "frozen", [answer], klass=frozen,
                              same_workspace=ws)
    assert a.review("Ordinary public wake.").kind == "wait"
    assert b.review("Ordinary public wake.").kind == "wait"
    # Only the nondeterministic review identity is excluded; no semantic text is normalized.
    assert {k: v for k, v in actual[0].items() if k != "review_id"} == {
        k: v for k, v in expected[0].items() if k != "review_id"}
    assert not (ws.private_root / "audit" / "experimental_control.jsonl").exists()
    assert len(actual) == len(expected) == 1
    assert tool_names(actual[0]) == [x["function"]["name"] for x in MONITOR_TOOLS]
    assert hashlib.sha256(subprocess.check_output(
        ["git", "show", f"{BASE}:GenericAgent-main/monitor_agent_core/agent.py"],
        cwd=REPO)).hexdigest()


def test_t01_dcec_disabled_off_off_matches_frozen_provider_ready_request(tmp_path):
    answer = tool("wait", after_turns=1)
    candidate, _, actual, ws = make_agent(tmp_path / "same", [answer],
                                           config_extra={"monitor_dcec": False})
    frozen, _, expected, _ = make_agent(tmp_path / "base", [answer],
                                        klass=frozen_agent_class(), same_workspace=ws,
                                        config_extra={"monitor_dcec": False})
    assert candidate.review("Plain wake").kind == frozen.review("Plain wake").kind
    assert {k: v for k, v in actual[0].items() if k != "review_id"} == {
        k: v for k, v in expected[0].items() if k != "review_id"}
    assert not (ws.private_root / "audit" / "experimental_control.jsonl").exists()


@pytest.mark.parametrize("view,intent", [("off", "off"), ("flat", "off"), ("framed", "off"),
                                         ("off", "note"), ("off", "routed"), ("flat", "note"),
                                         ("framed", "note"), ("flat", "routed"), ("framed", "routed")])
def test_t17_all_configurations_share_original_tools_and_optional_schema(tmp_path, view, intent):
    a, _, sent, _ = make_agent(tmp_path, [tool("wait", after_turns=1)], view=view, intent=intent)
    a.review("Wake.")
    names = tool_names(sent[0])
    assert names[:7] == [x["function"]["name"] for x in MONITOR_TOOLS]
    assert ("work_context" in names) == (view != "off")
    assert ("work_intent" in names) == (intent != "off")
    assert sent[0]["system"].count(GUIDANCE) == (view != "off" or intent != "off")


@pytest.mark.parametrize("bad", [dict(monitor_research_view=1), dict(monitor_research_view="other"),
                                      dict(monitor_research_intent=[]), dict(monitor_research_intent="other"),
                                      dict(monitor_dcec=False, monitor_research_view="flat"),
                                      dict(monitor_dcec=False, monitor_research_intent="note")])
def test_invalid_config_fails_before_provider_request(tmp_path, bad):
    with pytest.raises(ValueError):
        make_agent(tmp_path, [], config_extra=bad)


def test_historical_candidate_exclusion_is_unchanged(tmp_path):
    with pytest.raises(ValueError, match="historical candidates"):
        make_agent(tmp_path, [], view="flat", config_extra={"monitor_independent_c": True,
                                                         "monitor_inquiry": True})


def test_t03_t04_t05_t06_source_packet_render_and_errors(tmp_path, monkeypatch):
    flat, fc, _, ws = make_agent(tmp_path / "a", [], view="flat")
    framed, rc, _, _ = make_agent(tmp_path / "b", [], view="framed", same_workspace=ws)
    args = {"action": "select", "question": "Does the behavior hold?", "sources": [
        {"path": "task/original_task.txt"}, {"path": "task/workspace/component.py"},
        {"path": "task/public_events.jsonl"}, {"path": "monitor/working.md"}]}
    (ws.private_root / "working.md").write_text("complete is only my note", encoding="utf-8")
    monkeypatch.setattr("monitor_agent_core.experimental_control.adapter.time.time", lambda: 17.0)
    p1 = flat.dispatch("work_context", args).data["packet"]
    p2 = framed.dispatch("work_context", args).data["packet"]
    assert p1["sources"] == p2["sources"]
    assert [x["provenance_kind"] for x in p1["sources"]] == [
        "exact original_task", "mounted workspace", "public trace", "exact working.md"]
    assert "complete" in p1["sources"][-1]["content"]
    assert flat.completion_pending is False and framed.completion_pending is False
    assert flat.experimental_control.render_source(p1) != framed.experimental_control.render_source(p2)
    assert "selected_order" in framed.experimental_control.render_source(p2)
    assert "Selected material is not the whole public task" in flat.experimental_control.render_source(p1)
    assert flat.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/workspace/missing.py"}]}).data["packet"]["sources"][0]["error"]
    assert flat.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/../monitor/working.md"}]}).data["packet"]["sources"][0]["error"]
    assert flat.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/workspace/component.py", "count": 0}]}).data["status"] == "error"
    long = "中" * 2000
    (ws.task_mounts["workspace"] / "component.py").write_text(long, encoding="utf-8")
    item = flat.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/workspace/component.py"}]}).data["packet"]["sources"][0]
    assert item["content_chars"] == 1500 and item["content_utf8_bytes"] == 4500
    assert item["truncated"] and item["next_read"]["offset"] == 1500
    assert item["fragment_sha256"] == hashlib.sha256(item["content"].encode()).hexdigest()
    assert flat.dispatch("work_context", {"action": "clear"}).data["status"] == "cleared"
    assert flat.experimental_control.selection is None
    assert fc.complete_calls == rc.complete_calls == 0


def test_t07_t08_actual_dispatch_request_local_and_continuation(tmp_path):
    answers = [tool("work_context", action="select", question="Behavior?", sources=[
        {"path": "task/workspace/component.py"}]),
        tool("file_read", path="task/original_task.txt"), tool("wait", after_turns=1)]
    a, client, sent, ws = make_agent(tmp_path, answers, view="flat")
    a.review("Wake.")
    assert len(sent) == 3
    assert "Optional selected-source view" not in active_text(sent[0])
    assert sum("Optional selected-source view" in block.get("text", "")
               for msg in sent[1]["messages"] for block in msg.get("content", [])
               if isinstance(block, dict)) == 1
    assert all("Optional selected-source view" not in block.get("text", "")
               for msg in client.history for block in msg.get("content", []) if isinstance(block, dict))
    assert a.dispatch("work_context", {"action": "clear"}).data["status"] == "cleared"
    client._request_with_recovery = lambda tools: ([{"type": "text", "text": "Keep current uncertainty."}], {})
    a._prepare_continuation()
    assert "Optional selected-source view" not in json.dumps(client.history)


def test_t09_root_handoff_anchor_changes_and_existing_guard(tmp_path):
    a, client, _, _ = make_agent(tmp_path, [], view="flat", intent="routed")
    a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/original_task.txt"}]})
    a.dispatch("work_intent", {"action": "set", "text": "Investigate local behavior"})
    client.observed_root_handoff = {"generation": 1, "request_id": "p1", "cursor": 10}
    assert a.experimental_control.capture(a.experimental_control.selection)["handoff"]["request_id"] == "p1"
    packet = a.experimental_control._intent_packet()
    assert "handoff identity changed" in a.experimental_control.render_intent(packet)
    a.completion_state = lambda: {"generation": 2, "request_id": "p2", "cursor": 11}
    a._seen_completion = {"generation": 1, "request_id": "p1", "cursor": 10}
    assert a.dispatch("allow_complete", {}).data["status"] == "error"
    assert a.experimental_control.selection is not None


@pytest.mark.parametrize("window", [1, 4, 8])
def test_t10_window_counts_distinct_logical_requests(tmp_path, window):
    note, _, _, _ = make_agent(tmp_path / "note", [], intent="note", window=window)
    routed, client, _, _ = make_agent(tmp_path / "routed", [], intent="routed", window=window)
    for a in (note, routed):
        assert a.dispatch("work_intent", {"action": "set", "text": "Check public behavior"}).data["status"] == "set"
    origin = routed.experimental_control.intention
    assert note.experimental_control.intention == origin
    for n in range(1, window + 2):
        client.complete_calls = n
        packet = routed.experimental_control._intent_packet()
        rendered = routed.experimental_control.render_intent(packet)
        assert ("window elapsed" in rendered) == (n > window)
        note.client.complete_calls = n
        assert "window elapsed" not in note.experimental_control.render_intent(note.experimental_control._intent_packet())


def test_t11_t12_t13_intent_session_peek_and_return(tmp_path):
    a, client, _, _ = make_agent(tmp_path, [], intent="routed")
    assert a.dispatch("work_intent", {"action": "set", "text": "x", "watch_session": "unknown"}).data["status"] == "error"
    class Event:
        def is_set(self): return False
    class Process:
        def poll(self): return None
    out = tmp_path / "output.log"
    out.write_bytes(b"unread")
    a.analysis.sessions["s"] = {"done": Event(), "process": Process(), "output": out,
                                 "cursor": 1, "reason": None, "cancel": Event()}
    a.analysis.read = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not consume stdout"))
    assert a.dispatch("work_intent", {"action": "set", "text": "Check", "watch_session": "s"}).data["status"] == "set"
    assert a.dispatch("work_intent", {"action": "read"}).data["intention"]["watch_state"]["unread_bytes"] == 5
    assert a.analysis.sessions["s"]["cursor"] == 1
    returned = a.dispatch("work_intent", {"action": "return"}).data
    assert returned["previous"]["watch_state"]["unread_bytes"] == 5
    assert a.experimental_control.intention is None and "s" in a.analysis.sessions
    client.complete_calls = 1
    assert "Returned working intention" in a.experimental_control.active_block()
    client.complete_calls = 2
    assert a.experimental_control.active_block() is None
    assert a.dispatch("work_intent", {"action": "clear"}).data["status"] == "cleared"


def test_t14_t15_t16_multi_tool_and_no_semantic_oracle(tmp_path):
    answers = [tool("work_context", action="select", question="q", sources=[
        {"path": "task/original_task.txt"}]) + tool("allow_complete")]
    a, client, sent, _ = make_agent(tmp_path, answers, view="flat")
    action = a.review("Completion claim", completion_pending=True)
    assert action.kind == "allow_complete"
    assert len(sent) == 1
    assert a.experimental_control.selection is not None
    # Bad interpretation is not corrected by a hidden adapter oracle.
    b, _, _, _ = make_agent(tmp_path / "other", [tool("allow_complete")], intent="note")
    assert b.review("Completion claim", completion_pending=True).kind == "allow_complete"
    c, _, _, _ = make_agent(tmp_path / "third", [tool("wait", after_turns=1)], view="framed", intent="routed")
    assert c.review("Ordinary wake").kind == "wait"


def test_t18_no_network_and_t19_cost_audit(tmp_path, monkeypatch):
    monkeypatch.setattr(requests.Session, "request", lambda *_a, **_k: (_ for _ in ()).throw(
        AssertionError("network must not be used")))
    a, _, sent, ws = make_agent(tmp_path, [tool("wait", after_turns=1)], view="framed", intent="routed")
    a.review("Wake")
    audit = [json.loads(line) for line in (ws.private_root / "audit" / "experimental_control.jsonl").read_text(
        encoding="utf-8").splitlines()]
    assert audit[0]["guidance_sha256"] == hashlib.sha256(GUIDANCE.encode()).hexdigest()
    assert audit[0]["context_tool_sha256"]
    assert audit[0]["intent_tool_sha256"]
    assert sent[0]["model_parameters"]["model"] == "offline-model"
    assert all(len(x.get("block_sha256", "")) in (0, 64) for x in audit)


def test_bounded_combined_block_and_independent_clear(tmp_path):
    a, client, _, ws = make_agent(tmp_path, [], view="flat", intent="note")
    a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/original_task.txt"}]})
    a.dispatch("work_intent", {"action": "set", "text": "purpose"})
    client.complete_calls = 1
    block = a.experimental_control.active_block()
    assert len(block) <= EXTRA_BLOCK_LIMIT
    assert block.index("Optional selected-source view") < block.index("Optional working intention")
    a.dispatch("work_context", {"action": "clear"})
    client.complete_calls = 2
    assert "Optional working intention" in a.experimental_control.active_block()
    assert "Optional selected-source view" not in a.experimental_control.active_block()
    assert not (ws.private_root / "experimental_control").exists()


def test_t08_render_idempotent_per_logical_request_and_no_recapture_on_retry(tmp_path):
    a, client, _, _ = make_agent(tmp_path, [], view="flat", intent="routed")
    a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/original_task.txt"}]})
    client.complete_calls = 3
    first = a.experimental_control.active_block()
    count = a.experimental_control.capture_counts["task/original_task.txt"]
    assert a.experimental_control.active_block() == first
    assert a.experimental_control.capture_counts["task/original_task.txt"] == count
    client.complete_calls = 4
    a.experimental_control.active_block()
    assert a.experimental_control.capture_counts["task/original_task.txt"] == count + 1


def test_t04_read_after_source_moves_is_unavailable_not_positive(tmp_path):
    a, _, _, ws = make_agent(tmp_path, [], view="flat")
    a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/workspace/component.py"}]})
    (ws.task_mounts["workspace"] / "component.py").unlink()
    result = a.dispatch("work_context", {"action": "read"}).data["packet"]["sources"][0]
    assert result["error"]["type"] == "FileNotFoundError"
    assert result["sha256"] is None and result["content"] == ""
    assert result["next_read"]["path"] == "task/workspace/component.py"


def test_t14_no_tool_and_limit_preserve_production_receipts(tmp_path):
    from monitor_agent_core.loop import MonitorLoopError
    a, client, sent, ws = make_agent(tmp_path, [[{"type": "text", "text": "Considering."}]],
                                     view="flat")
    a.max_review_turns = 1
    with pytest.raises(MonitorLoopError):
        a.review("Wake")
    assert len(sent) == 1
    assert (ws.private_root / "audit" / "provider_history.json").is_file()
    b, _, _, _ = make_agent(tmp_path / "error", [tool("work_context", action="select", question="q",
                                                      sources=[]) , tool("wait", after_turns=1)], view="flat")
    assert b.review("Wake").kind == "wait"
    audit = (b.workspace.private_root / "audit" / "experimental_control.jsonl").read_text(encoding="utf-8")
    assert "operation_failed" in audit


def test_t09_mid_review_new_root_receives_current_anchor_without_new_stage(tmp_path):
    a, client, sent, _ = make_agent(tmp_path, [tool("work_intent", action="set", text="Check local state"),
                                               tool("allow_complete")], intent="routed")
    pending = {"value": None}
    a.completion_state = lambda: pending["value"]
    original_transport = client._request_with_recovery

    def change_after_first(tools):
        blocks, usage = original_transport(tools)
        if len(sent) == 1:
            pending["value"] = {"generation": 7, "request_id": "root-7", "cursor": 42}
        return blocks, usage

    client._request_with_recovery = change_after_first
    assert a.review("Ordinary wake").kind == "allow_complete"
    assert len(sent) == 2
    assert sent[0]["root_handoff"] is None
    assert sent[1]["root_handoff"]["request_id"] == "root-7"
    assert "handoff identity changed" in active_text(sent[1])
    assert "Runtime update" in active_text(sent[1])


def test_t10_actual_provider_requests_route_on_fifth_after_set(tmp_path):
    answers = [tool("work_intent", action="set", text="Observe behavior")]
    answers += [tool("file_read", path="task/original_task.txt") for _ in range(5)]
    answers += [tool("wait", after_turns=1)]
    a, client, sent, _ = make_agent(tmp_path, answers, intent="routed")
    assert a.review("Wake").kind == "wait"
    assert len(sent) == 7 and client.complete_calls == 7
    assert all("window elapsed" not in active_text(sent[n]) for n in range(1, 5))
    assert "window elapsed" in active_text(sent[5])
    assert "window elapsed" in active_text(sent[6])


def test_t14_registration_failure_does_not_replay_successful_ordinary_tool(tmp_path, monkeypatch):
    a, _, _, ws = make_agent(tmp_path, [], intent="note")
    original_audit = a.experimental_control.audit

    def fail_once(event, **fields):
        if event == "ordinary_tool_outcome":
            raise OSError("audit unavailable")
        return original_audit(event, **fields)

    monkeypatch.setattr(a.experimental_control, "audit", fail_once)
    receipt = a.dispatch("file_write", {"path": "monitor/working.md", "content": "one write"})
    assert receipt.data["sha256"] == hashlib.sha256(b"one write").hexdigest()
    assert (ws.private_root / "working.md").read_text(encoding="utf-8") == "one write"
    progress = (ws.private_root / "audit" / "progress.jsonl").read_text(encoding="utf-8")
    assert "experimental_registration_failed" in progress


def test_t19_reference_and_candidate_assembled_cost_fields_are_real(tmp_path):
    rows = []
    for view, intent in [("off", "off"), ("flat", "off"), ("framed", "off"),
                         ("off", "note"), ("off", "routed")]:
        a, _, sent, _ = make_agent(tmp_path / f"{view}_{intent}", [tool("wait", after_turns=1)],
                                   view=view, intent=intent)
        a.review("Same public wake")
        request = sent[0]
        rows.append({"view": view, "intent": intent,
                     "system_sha256": hashlib.sha256(request["system"].encode()).hexdigest(),
                     "tools_sha256": hashlib.sha256(json.dumps(
                         request["tools"], ensure_ascii=False, sort_keys=True).encode()).hexdigest(),
                     "messages_chars": len(json.dumps(request["messages"], ensure_ascii=False)),
                     "model_parameters_sha256": hashlib.sha256(json.dumps(
                         request["model_parameters"], sort_keys=True).encode()).hexdigest()})
    assert len({x["model_parameters_sha256"] for x in rows}) == 1
    assert all(x["messages_chars"] > 0 for x in rows)
    assert rows[1]["tools_sha256"] == rows[2]["tools_sha256"]
    assert rows[3]["tools_sha256"] == rows[4]["tools_sha256"]
    assert rows[0]["system_sha256"] != rows[1]["system_sha256"]


def test_t08_provider_retry_does_not_recount_or_recapture(tmp_path, monkeypatch):
    from monitor_agent_core.provider import RetryableProviderError
    a, client, _, _ = make_agent(tmp_path, [], view="flat", intent="routed")
    a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/original_task.txt"}]})
    a.dispatch("work_intent", {"action": "set", "text": "Observe"})
    del client.__dict__["_request_with_recovery"]  # execute frozen provider retry path
    client.max_retries = 1
    monkeypatch.setattr(client._cancelled, "wait", lambda _: False)
    attempts = {"n": 0}

    def transport(_tools):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RetryableProviderError("offline temporary error")
        return tool("wait", after_turns=1), {"input_tokens": 11}

    monkeypatch.setattr(client, "_request_once", transport)
    assert a.review("Wake").kind == "wait"
    assert attempts["n"] == 2 and client.complete_calls == 1
    assert a.experimental_control.capture_counts["task/original_task.txt"] == 2
    assert len(client.request_attempts) == 0  # drained into private audit at review end
    records = (a.workspace.private_root / "audit" / "request_attempts.jsonl").read_text().splitlines()
    assert len(records) == 2


def test_t13_elapsed_intent_does_not_consume_or_cancel_analysis_session(tmp_path):
    a, client, _, _ = make_agent(tmp_path, [], intent="routed", window=1)
    class Event:
        def __init__(self): self.cancelled = False
        def is_set(self): return self.cancelled
        def set(self): self.cancelled = True
    class Process:
        def poll(self): return None
    output = tmp_path / "output.log"
    output.write_bytes(b"pending output")
    cancel = Event()
    a.analysis.sessions["ongoing"] = {"done": Event(), "process": Process(), "output": output,
                                       "cursor": 0, "reason": None, "cancel": cancel}
    a.analysis.read = lambda session_id, *_args: {"status": "running", "session_id": session_id,
                                                    "stdout": "pending output", "unread_bytes": 0}
    a.dispatch("work_intent", {"action": "set", "text": "Await existing check", "watch_session": "ongoing"})
    client.complete_calls = 2
    assert "window elapsed" in a.experimental_control.render_intent(a.experimental_control._intent_packet())
    assert a.dispatch("code_run", {"session_id": "ongoing"}).data["status"] == "running"
    assert not cancel.is_set() and len(a.analysis.sessions) == 1
    a.dispatch("work_intent", {"action": "clear"})
    assert not cancel.is_set() and "ongoing" in a.analysis.sessions


def test_t04_t17_four_source_and_combined_block_budget(tmp_path):
    a, client, _, ws = make_agent(tmp_path, [], view="framed", intent="routed")
    for number in range(4):
        (ws.task_mounts["workspace"] / f"part{number}.txt").write_text("x" * 2000)
    sources = [{"path": f"task/workspace/part{number}.txt"} for number in range(4)]
    packet = a.dispatch("work_context", {"action": "select", "question": "q", "sources": sources}).data["packet"]
    assert packet["source_text_chars"] == 6000
    assert [item["content_chars"] for item in packet["sources"]] == [1500] * 4
    assert all(item["truncated"] and item["next_read"] for item in packet["sources"])
    a.dispatch("work_intent", {"action": "set", "text": "Investigate"})
    client.complete_calls = 1
    assert len(a.experimental_control.active_block()) <= EXTRA_BLOCK_LIMIT


def test_f1_select_auto_refresh_and_old_render_are_reconstructible(tmp_path):
    answers = [tool("work_context", action="select", question="Which behavior?", sources=[
        {"path": "task/workspace/component.py"}]),
        tool("work_context", action="clear"), tool("wait", after_turns=1)]
    a, _, sent, ws = make_agent(tmp_path, answers, view="framed")
    source = ws.task_mounts["workspace"] / "component.py"
    initial = source.read_text(encoding="utf-8")
    original_dispatch = a.dispatch

    def mutate_after_dispatch(name, args):
        outcome = original_dispatch(name, args)
        if name == "work_context" and args["action"] == "select":
            source.write_text("second version\n", encoding="utf-8")
        if name == "work_context" and args["action"] == "clear":
            source.write_text("third version\n", encoding="utf-8")
        return outcome

    a.dispatch = mutate_after_dispatch
    assert a.review("Public wake").kind == "wait"
    captures = candidate_events(ws, "source_capture")
    assert len(captures) == 2
    first = artifact(ws, captures[0]["capture_artifact"])["payload"]["packet"]
    refreshed = artifact(ws, captures[1]["capture_artifact"])["payload"]["packet"]
    assert first["sources"][0]["content"] == initial
    assert refreshed["sources"][0]["content"] == "second version\n"
    renders = candidate_events(ws, "request_block")
    second_render = artifact(ws, renders[1]["render_artifact"])["payload"]
    assert second_render["raw_capture_artifact"] == captures[1]["capture_artifact"]
    assert second_render["block_sha256"] == hashlib.sha256(
        second_render["block"].encode("utf-8")).hexdigest()
    assert "second version" in second_render["block"]
    assert "third version" not in second_render["block"]
    assert "second version" in active_text(sent[1])
    assert "Optional selected-source view" not in active_text(sent[2])
    assert source.read_text() == "third version\n"
    assert renders[1]["review_id"] == captures[1]["review_id"]
    assert renders[1]["request_sequence"] == 2
    assert second_render["effective_packet"]["sources"][0]["content"] == "second version\n"


def test_f2_shared_budget_preserves_same_effective_inventory_for_flat_and_framed(tmp_path, monkeypatch):
    monkeypatch.setattr("monitor_agent_core.experimental_control.adapter.time.time", lambda: 19.0)
    a, _, _, ws = make_agent(tmp_path / "one", [], view="flat")
    for index in range(4):
        (ws.task_mounts["workspace"] / f"part{index}.txt").write_text(
            ('\\"\n\t' * 1100) + "多" * 500, encoding="utf-8")
    sources = [{"path": f"task/workspace/part{index}.txt", "count": 1000} for index in range(4)]
    scripted = [tool("work_context", action="select", question="Q" * 1200, sources=sources)
                + tool("work_intent", action="set", text="I" * 1200, watch_session="s"),
                tool("file_read", path="task/original_task.txt"),
                tool("file_read", path="task/original_task.txt"),
                tool("wait", after_turns=1)]

    class Event:
        def is_set(self): return False
    class Process:
        def poll(self): return None

    results = []
    for name, mode in (("R", "flat"), ("A", "framed")):
        agent, client, sent, shared = make_agent(tmp_path / name, scripted,
                                                 view=mode, intent="routed", window=1,
                                                 same_workspace=ws)
        output = tmp_path / f"{name}.log"
        output.write_bytes(b"unread")
        agent.analysis.sessions["s"] = {"done": Event(), "process": Process(), "output": output,
                                         "cursor": 0, "reason": None}
        assert agent.review("Public wake").kind == "wait"
        rows = candidate_events(shared, "request_block")
        # Shared audit directory contains both runs; filter this live review identity.
        rows = [row for row in rows if row["review_id"] == agent.review_id]
        assert len(rows) == 4
        rendered = artifact(shared, rows[2]["render_artifact"])["payload"]
        block = rendered["block"]
        assert len(block) <= 14000
        assert "window elapsed" in block and '"unread_bytes": 6' in block
        assert "Selected material is not the whole public task" in block
        assert "Q" * 1200 in block and "I" * 1200 in block
        assert rendered["raw_capture_artifact"] is not None
        raw = artifact(shared, rendered["raw_capture_artifact"])["payload"]["packet"]
        effective = rendered["effective_packet"]
        assert raw["source_text_chars"] == 6000
        assert effective["source_text_chars"] < raw["source_text_chars"]
        assert any(item["omitted"] and item["next_read"] for item in effective["sources"])
        assert all(item["fragment_sha256"] == hashlib.sha256(
            item["content"].encode()).hexdigest() for item in effective["sources"]
                   if item["fragment_sha256"] is not None)
        assert block in active_text(sent[2])
        results.append((effective, len(block)))
    assert results[0][0] == results[1][0]
    assert results[0][1] != results[1][1]


def test_f3_return_snapshot_and_next_request_current_facts_are_distinct(tmp_path):
    scripted = [tool("work_intent", action="set", text="Observe", watch_session="s"),
                tool("work_intent", action="return"), tool("allow_complete")]
    a, client, sent, ws = make_agent(tmp_path, scripted, intent="routed")
    pending = {"value": None}
    a.completion_state = lambda: pending["value"]

    class Event:
        done = False
        cancelled = False
        def is_set(self): return self.done
        def set(self): self.cancelled = True
    class Process:
        def poll(self): return 0 if done.done else None
    done, cancel = Event(), Event()
    output = tmp_path / "output.log"
    output.write_bytes(b"unread")
    a.analysis.sessions["s"] = {"done": done, "process": Process(), "output": output,
                                 "cursor": 1, "reason": None, "cancel": cancel}
    a.analysis.read = lambda *_args, **_kwargs: (_ for _ in ()).throw(
        AssertionError("return must not consume stdout"))
    original_dispatch = a.dispatch

    def change_after_return(name, args):
        outcome = original_dispatch(name, args)
        if name == "work_intent" and args["action"] == "return":
            pending["value"] = {"generation": 1, "request_id": "new-root", "cursor": 4}
            done.done = True
        return outcome

    a.dispatch = change_after_return
    assert a.review("Ordinary wake").kind == "allow_complete"
    assert len(sent) == 3
    rows = candidate_events(ws, "request_block")
    rendered = artifact(ws, rows[2]["render_artifact"])["payload"]
    packet = rendered["intent_or_return_packet"]
    assert packet["at_return_snapshot"]["current_handoff"] is None
    assert packet["at_return_snapshot"]["watch_state"]["done"] is False
    assert packet["current_handoff"]["request_id"] == "new-root"
    assert packet["current_watch_state"]["done"] is True
    assert packet["current_watch_state"]["exit_code"] == 0
    assert '"request_id": "new-root"' in active_text(sent[2])
    assert a.analysis.sessions["s"]["cursor"] == 1 and not cancel.cancelled
    assert a.experimental_control.return_once is None
    before = len(candidate_events(ws, "request_block"))
    assert a.experimental_control.active_block() == rendered["block"]
    assert len(candidate_events(ws, "request_block")) == before
    assert any("returned" in block.get("content", "")
               for message in client.history for block in message.get("content", [])
               if isinstance(block, dict) and block.get("type") == "tool_result")


def test_f4_workspace_canonical_path_identity_and_traversal(tmp_path):
    a, _, _, ws = make_agent(tmp_path, [], view="framed")
    (ws.private_root / "working.md").write_text("own note", encoding="utf-8")
    pointers = [{"path": "task//original_task.txt"},
                {"path": "monitor//working.md"},
                {"path": "task//workspace//component.py"}]
    packet = a.dispatch("work_context", {"action": "select", "question": "q",
                                          "sources": pointers}).data["packet"]
    assert [item["path"] for item in packet["sources"]] == [x["path"] for x in pointers]
    assert [item["provenance_kind"] for item in packet["sources"]] == [
        "exact original_task", "exact working.md", "mounted workspace"]
    assert "Original task text was not expanded" not in a.experimental_control.render_source(packet)
    blocked = a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/../monitor/working.md"}]}).data["packet"]["sources"][0]
    assert blocked["provenance_kind"] == "unavailable"
    assert blocked["error"] and blocked["content"] == ""


def test_f1_error_and_unavailable_render_artifacts_match_sent_text(tmp_path, monkeypatch):
    a, _, sent, ws = make_agent(tmp_path, [tool("wait", after_turns=1)], view="flat")
    selected = a.dispatch("work_context", {"action": "select", "question": "q", "sources": [
        {"path": "task/workspace/missing.txt"}]}).data
    raw = artifact(ws, selected["capture_artifact"])["payload"]["packet"]
    assert raw["sources"][0]["error"]["type"] == "FileNotFoundError"
    monkeypatch.setattr(a.experimental_control, "render_source", lambda *_args, **_kwargs: (
        _ for _ in ()).throw(RuntimeError("offline render fault")))
    assert a.review("Wake").kind == "wait"
    block = candidate_events(ws, "request_block")[-1]
    archived = artifact(ws, block["render_artifact"])["payload"]
    assert archived["block_sha256"] == hashlib.sha256(archived["block"].encode()).hexdigest()
    assert archived["block"] in active_text(sent[0])
    assert archived["raw_capture_artifact"] is not None
