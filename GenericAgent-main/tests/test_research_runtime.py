import json
from pathlib import Path
from types import SimpleNamespace

import pytest
import jsonschema

from research_runtime import (
    CompletionDecision,
    CompletionProposal,
    JsonlEventSink,
    OtelEventExporter,
    decide_completion,
    emit,
    payload_summary,
    research_context,
    temporary_exporter,
    wrap_generator,
)


def test_jsonl_sink_and_identity(tmp_path):
    path = tmp_path / "events.jsonl"
    with research_context({"run_id": "r1", "task_id": "t1"}, JsonlEventSink(path)):
        event = emit("intervention", {"value": 3}, internal_turn=2)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved == event
    assert saved["run_id"] == "r1"
    assert saved["internal_turn"] == 2
    schema_path = Path(__file__).parents[2] / "method_discovery" / "schemas" / "event_envelope.schema.json"
    jsonschema.validate(saved, json.loads(schema_path.read_text(encoding="utf-8")))


def test_disabled_emit_is_noop():
    assert emit("disabled") is None


def test_payload_summary_defaults_to_hash_only():
    summary = payload_summary({"model": "mock", "messages": [{"role": "user", "content": "secret"}]})
    assert summary["content_availability"] == "hash_only"
    assert "content" not in summary
    assert summary["message_count"] == 1


def test_default_completion_gate_preserves_allow():
    proposal = CompletionProposal.from_response(SimpleNamespace(content="done"), 4)
    decision = decide_completion(SimpleNamespace(), proposal)
    assert decision.decision == "ALLOW_COMPLETE"
    assert decision.next_prompt is None


def test_custom_completion_gate():
    proposal = CompletionProposal.from_response(SimpleNamespace(content="done"), 4)
    handler = SimpleNamespace(completion_gate=lambda _: CompletionDecision(
        decision="CONTINUE", reason_codes=("MISSING_EVIDENCE",), next_prompt="verify first"
    ))
    assert decide_completion(handler, proposal).next_prompt == "verify first"


def test_bad_gate_fails_open(tmp_path):
    events = []
    handler = SimpleNamespace(completion_gate=lambda _: (_ for _ in ()).throw(RuntimeError("bad")))
    proposal = CompletionProposal.from_response(SimpleNamespace(content="done"), 1)
    with research_context({}, events.append):
        decision = decide_completion(handler, proposal)
    assert decision.decision == "ERROR_FAIL_OPEN"
    assert events[0]["event_type"] == "completion_gate_error"


def test_unknown_decision_is_rejected():
    with pytest.raises(ValueError):
        CompletionDecision(decision="UNKNOWN")


def test_wrapped_generator_keeps_context_across_yields():
    events = []
    def source():
        emit("sample", {"position": "before"})
        yield 1
        emit("sample", {"position": "after"})
        return 2
    wrapped = wrap_generator(source(), {"run_id": "wrapped"}, events.append)
    assert next(wrapped) == 1
    with pytest.raises(StopIteration) as stopped:
        next(wrapped)
    assert stopped.value.value == 2
    assert [event["run_id"] for event in events] == ["wrapped", "wrapped"]


def test_global_exporter_and_artifact_receive_same_event_object():
    exported = []
    artifacts = []
    def exporter(event):
        event["trace_id"] = "a" * 32
        event["span_id"] = "b" * 16
        exported.append(event)
    with temporary_exporter(exporter), research_context({"run_id": "r"}, artifacts.append):
        emitted = emit("intervention", {"kind": "test"})
    assert exported[0] is artifacts[0] is emitted
    assert artifacts[0]["trace_id"] == "a" * 32


def test_process_exporter_enables_telemetry_without_artifact_sink():
    exported = []
    with temporary_exporter(exported.append), research_context({"run_id": "otel-only"}):
        emitted = emit("termination", {"result": "CURRENT_TASK_DONE"})
    assert exported == [emitted]


def test_otel_exporter_adds_span_context_without_reserializing_event():
    class Context:
        trace_id = int("12" * 16, 16)
        span_id = int("34" * 8, 16)
    class Span:
        def __init__(self): self.events = []
        def is_recording(self): return True
        def get_span_context(self): return Context()
        def add_event(self, name, attributes): self.events.append((name, attributes))
        def set_attribute(self, key, value): setattr(self, key.replace('.', '_'), value)
    span = Span()
    artifacts = []
    with temporary_exporter(OtelEventExporter(lambda _: span)), research_context({}, artifacts.append):
        event = emit("completion_decision", {"decision": "ALLOW_COMPLETE", "content": "not-an-attribute"})
    assert event["trace_id"] == "12" * 16
    assert event["span_id"] == "34" * 8
    assert span.events[0][0] == "ga.research.completion_decision"
    assert "ga.research.content" not in span.events[0][1]
    assert artifacts[0] is event
