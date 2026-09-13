import json

import pytest

from monitor_agent_core.agent import MONITOR_TOOLS, MonitorAgent
from monitor_agent_core.grounded_context import read_with_sources
from monitor_agent_core.workspace import MonitorWorkspace
from test_monitor_agent import SequenceClient, response


@pytest.fixture
def ws(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    (evidence / "original_task.txt").write_text("Keep X.\nAllow Y.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "private")


def note(ws, content="Hypothesis, not requirement. [task](task/original_task.txt#L1-L1)"):
    ws.write_text("monitor/inquiry.md", content)
    return "monitor/inquiry.md"


def test_reads_actual_sources_and_preserves_original_note(ws):
    path = note(ws)
    result = read_with_sources(ws, path)
    source = result["sources"][0]
    assert source["source"]["content"] == "Keep X.\n"
    assert source["excerpt_changed"] is None
    assert "Hypothesis" in result["note"]["content"]
    assert result["note"]["content"] == ws.read_text(path)["content"]
    archived = json.loads(ws.resolve_read(result["archive"]).read_text(encoding="utf-8"))
    assert archived["result"]["sources"] == result["sources"]


def test_distinguishes_whole_file_and_selected_text_changes_across_restarts(ws):
    path = note(ws)
    first = read_with_sources(ws, path)
    source = ws.evidence_root / "original_task.txt"
    source.write_text("Keep X.\nDifferent elsewhere.\n", encoding="utf-8")
    restarted = MonitorWorkspace(ws.evidence_root, ws.private_root)
    second = read_with_sources(restarted, path)["sources"][0]
    assert second["file_changed"] is True
    assert second["excerpt_changed"] is False
    assert second["previous_read"] == first["archive"]
    source.write_text("Changed here.\n", encoding="utf-8")
    assert read_with_sources(restarted, path)["sources"][0]["excerpt_changed"] is True
    old = json.loads(ws.resolve_read(first["archive"]).read_text(encoding="utf-8"))
    assert old["result"]["sources"][0]["source"]["content"] == "Keep X.\n"


def test_bad_source_does_not_hide_good_source_or_approve_note(ws):
    path = note(ws, "[bad](task/missing) [escape](task/../secret) "
                    "[web](https://example.com) [ok](task/original_task.txt#L1-L2)")
    result = read_with_sources(ws, path)
    assert [s["status"] for s in result["sources"]] == ["error"] * 3 + ["read"]
    assert "semantic verdicts" in result["notice"]


def test_visible_bounds_and_no_recursive_expansion(ws):
    ws.write_text("monitor/other.md", "[nested](task/original_task.txt)")
    path = note(ws, "[private](monitor/other.md)\n" + "\n".join(
        f"[s{i}](task/original_task.txt#L{i})" for i in range(1, 10)))
    result = read_with_sources(ws, path)
    assert len(result["sources"]) == 8
    assert len(result["unexpanded_links"]) == 2
    assert "nested" in result["sources"][0]["source"]["content"]
    assert result["sources"][-1]["warning"]
    partial = read_with_sources(ws, path, count=1)
    assert partial["note_has_more"] is True
    assert len(partial["sources"]) == 1


def test_no_links_is_valid_and_task_note_cannot_be_written(ws):
    assert read_with_sources(ws, note(ws, "Still investigating."))["sources"] == []
    with pytest.raises(ValueError):
        read_with_sources(ws, "task/original_task.txt")


@pytest.mark.parametrize("value,expected", [("1", True), ("0", False), (None, None)])
def test_launch_adapter_preserves_and_forwards_candidate_without_mutating_config(tmp_path, monkeypatch, value, expected):
    import ga_monitor_adapter as adapter
    monkeypatch.delenv("GA_MONITOR_GROUNDED_CONTEXT", raising=False)
    if value is not None:
        monkeypatch.setenv("GA_MONITOR_GROUNDED_CONTEXT", value)
    captured = {}
    monkeypatch.setattr(adapter, "MonitorRuntime", lambda **kwargs: captured.update(kwargs))
    config = {"model": "fixture"}
    adapter.GenericAgentMonitorAdapter(task_workspace=tmp_path, public_task='Task', model_config=config)
    assert captured["model_config"].get("monitor_grounded_context") is expected
    assert config == {"model": "fixture"}


def test_enabled_review_restores_sources_then_can_immediately_intervene(ws):
    path = note(ws)
    client = SequenceClient([
        response("read_with_sources", {"path": path}),
        response("intervene", {"message": "Keep X."}),
    ])
    client.config = {"monitor_grounded_context": True}
    monitor = MonitorAgent(client, ws)
    assert monitor.review("Continue investigating.").kind == "intervene"
    records = [json.loads(line) for line in
               (ws.private_root / "audit/dialogue.jsonl").read_text(encoding="utf-8").splitlines()]
    assert "Keep X." in json.dumps(records)
    assert "read_with_sources" in json.dumps(client.history)


@pytest.mark.parametrize("enabled", [False, True])
def test_no_mandatory_source_read_or_extra_call(ws, enabled):
    client = SequenceClient([response("intervene", {"message": "Direct correction."})])
    client.config = {"monitor_grounded_context": enabled}
    seen_tools = []
    complete = client.complete

    def recording(messages, tools):
        seen_tools.append(tools)
        return complete(messages, tools)

    client.complete = recording
    monitor = MonitorAgent(client, ws)
    assert monitor.review("Evidence already available.").kind == "intervene"
    assert len(seen_tools) == 1
    assert len(seen_tools[0]) == len(MONITOR_TOOLS) + int(enabled)
    assert not (ws.private_root / "audit/source_reads").exists()
    if not enabled:
        assert monitor.dispatch("read_with_sources", {"path": "monitor/a.md"}).data["status"] == "error"
