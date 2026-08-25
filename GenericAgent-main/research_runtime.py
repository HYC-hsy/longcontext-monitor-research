"""Opt-in telemetry and completion interfaces for long-horizon research.

The module is deliberately dependency-free and disabled unless a sink is
installed.  It must not change normal GenericAgent behaviour.
"""
from __future__ import annotations

import contextlib
import contextvars
import dataclasses
import datetime
import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping, Optional


SCHEMA_VERSION = "method-discovery-event/1"
_context: contextvars.ContextVar[dict[str, Any]] = contextvars.ContextVar(
    "ga_research_context", default={}
)
_sink: contextvars.ContextVar[Optional[Callable[[dict[str, Any]], None]]] = (
    contextvars.ContextVar("ga_research_sink", default=None)
)
_pending_intervention: contextvars.ContextVar[Optional[dict[str, Any]]] = contextvars.ContextVar(
    "ga_pending_intervention", default=None
)
_last_provider_call: contextvars.ContextVar[Optional[dict[str, Any]]] = contextvars.ContextVar(
    "ga_last_provider_call", default=None
)
_exporters: list[Callable[[dict[str, Any]], None]] = []
_exporters_lock = threading.Lock()


def telemetry_enabled() -> bool:
    """Return whether the current execution has any telemetry destination."""
    return _sink.get() is not None or bool(_exporters)


def current_identity() -> dict[str, Any]:
    return dict(_context.get())


def register_pending_intervention(event: Mapping[str, Any], occurrence_id: str) -> None:
    """Associate one intervention occurrence with the next provider request."""
    _pending_intervention.set({
        "intervention_event_id": event["event_id"],
        "injection_occurrence_id": occurrence_id,
    })


def consume_pending_intervention() -> Optional[dict[str, Any]]:
    value = _pending_intervention.get()
    _pending_intervention.set(None)
    return dict(value) if value else None


def register_provider_call(call: Mapping[str, Any]) -> None:
    _last_provider_call.set(dict(call))


def current_provider_call() -> Optional[dict[str, Any]]:
    """Return provider-call identity without consuming the completion link."""
    value = _last_provider_call.get()
    return dict(value) if value else None


def consume_provider_call() -> Optional[dict[str, Any]]:
    value = _last_provider_call.get()
    _last_provider_call.set(None)
    return dict(value) if value else None


def register_exporter(exporter: Callable[[dict[str, Any]], None]) -> None:
    """Register a process-wide destination, such as the OTel bridge."""
    with _exporters_lock:
        if exporter not in _exporters:
            _exporters.append(exporter)


def unregister_exporter(exporter: Callable[[dict[str, Any]], None]) -> None:
    with _exporters_lock:
        if exporter in _exporters:
            _exporters.remove(exporter)


@contextlib.contextmanager
def temporary_exporter(exporter: Callable[[dict[str, Any]], None]) -> Iterator[None]:
    register_exporter(exporter)
    try:
        yield
    finally:
        unregister_exporter(exporter)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def sha256_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def payload_summary(payload: Mapping[str, Any], capture_content: bool = False) -> dict[str, Any]:
    """Describe a final provider payload without recording secrets by default."""
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    result = {
        "content_availability": "complete" if capture_content else "hash_only",
        "sha256": hashlib.sha256(raw).hexdigest(),
        "bytes": len(raw),
        "model": payload.get("model"),
        "stream": payload.get("stream"),
        "message_count": len(payload.get("messages", payload.get("input", [])))
        if isinstance(payload.get("messages", payload.get("input", [])), list) else None,
        "tool_count": len(payload.get("tools", [])) if isinstance(payload.get("tools"), list) else 0,
    }
    if capture_content:
        result["content"] = payload
    return result


class JsonlEventSink:
    """Thread-safe append-only JSONL sink."""

    def __init__(self, path: os.PathLike[str] | str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def __call__(self, event: dict[str, Any]) -> None:
        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"
        with self._lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(line)


class OtelEventExporter:
    """Adapt unified research events to the currently active OTel span.

    The adapter uses duck typing so GenericAgent does not require the OTel SDK
    unless the existing OTel plugin is explicitly enabled.
    """

    def __init__(self, span_resolver: Callable[[str], Any]):
        self._span_resolver = span_resolver

    @staticmethod
    def _attribute(value: Any) -> Any:
        if isinstance(value, (str, bool, int, float)):
            return value
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)

    def __call__(self, event: dict[str, Any]) -> None:
        span = self._span_resolver(event["event_type"])
        if span is None or (hasattr(span, "is_recording") and not span.is_recording()):
            return
        context = span.get_span_context()
        if getattr(context, "trace_id", 0):
            event["trace_id"] = format(context.trace_id, "032x")
        if getattr(context, "span_id", 0):
            event["span_id"] = format(context.span_id, "016x")
        attributes = {
            "ga.research.event_id": event["event_id"],
            "ga.research.schema_version": event["schema_version"],
            "ga.research.experiment_id": event["experiment_id"],
            "ga.research.condition_id": event["condition_id"],
            "ga.research.task_id": event["task_id"],
            "ga.research.run_id": event["run_id"],
            "ga.research.branch_id": event["branch_id"],
        }
        for key in ("user_turn", "internal_turn", "llm_call_id", "parent_event_id"):
            if event.get(key) is not None:
                attributes[f"ga.research.{key}"] = event[key]
        for key, value in event.get("payload", {}).items():
            if value is not None and key != "content":
                attributes[f"ga.research.{key}"] = self._attribute(value)
        if event["event_type"] == "provider_request_ready" and event.get("llm_call_id"):
            span.set_attribute("ga.research.llm_call_id", event["llm_call_id"])
        span.add_event(f"ga.research.{event['event_type']}", attributes=attributes)


@contextlib.contextmanager
def research_context(
    identity: Optional[Mapping[str, Any]] = None,
    sink: Optional[Callable[[dict[str, Any]], None]] = None,
) -> Iterator[None]:
    """Install run identity and an event sink for the current context."""
    context_token = _context.set(dict(identity or {}))
    sink_token = _sink.set(sink)
    intervention_token = _pending_intervention.set(None)
    provider_token = _last_provider_call.set(None)
    try:
        yield
    finally:
        _last_provider_call.reset(provider_token)
        _pending_intervention.reset(intervention_token)
        _sink.reset(sink_token)
        _context.reset(context_token)


def wrap_generator(generator: Iterator[Any], identity: Mapping[str, Any], sink: Optional[Callable[[dict[str, Any]], None]] = None) -> Iterator[Any]:
    """Run a generator inside a context, including execution between yields."""
    with research_context(identity, sink):
        return (yield from generator)


def emit(event_type: str, payload: Optional[Mapping[str, Any]] = None, **identity: Any) -> Optional[dict[str, Any]]:
    """Emit an event if enabled; telemetry failures are fail-open."""
    sink = _sink.get()
    with _exporters_lock:
        exporters = tuple(_exporters)
    if sink is None and not exporters:
        return None
    inherited = {**_context.get(), **{k: v for k, v in identity.items() if v is not None}}
    required = ("experiment_id", "condition_id", "task_id", "run_id", "branch_id")
    ids = {key: inherited.get(key) or "unassigned" for key in required}
    optional = {key: inherited[key] for key in ("user_turn", "internal_turn", "llm_call_id", "parent_event_id")
                if key in inherited}
    envelope = {
        "schema_version": SCHEMA_VERSION,
        "event_id": new_id("evt"),
        "event_type": event_type,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        **ids,
        **optional,
        "payload": dict(payload or {}),
    }
    delivered = False
    for exporter in exporters + ((sink,) if sink is not None else ()):
        try:
            exporter(envelope)
            delivered = True
        except Exception:
            continue
    if not delivered:
        return None
    return envelope


@dataclasses.dataclass(frozen=True)
class CompletionProposal:
    proposal_id: str
    origin: str
    turn: int
    response_sha256: str
    response_preview: str
    stop_reason: Optional[str] = None

    @classmethod
    def from_response(cls, response: Any, turn: int) -> "CompletionProposal":
        content = getattr(response, "content", "") or ""
        return cls(
            proposal_id=new_id("proposal"),
            origin="no_tool",
            turn=turn,
            response_sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            response_preview=content[:240],
            stop_reason=getattr(response, "stop_reason", None),
        )

    def as_payload(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True)
class CompletionDecision:
    decision: str = "ALLOW_COMPLETE"
    reason_codes: tuple[str, ...] = ("DEFAULT_ALLOW",)
    next_prompt: Optional[str] = None
    target_obligation_ids: tuple[str, ...] = ()
    checker_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        allowed = {
            "ALLOW_COMPLETE", "CONTINUE", "VERIFY", "REPAIR", "REMIND",
            "REOBSERVE", "ABSTAIN", "ERROR_FAIL_OPEN", "ERROR_FAIL_CLOSED",
        }
        if self.decision not in allowed:
            raise ValueError(f"Unknown completion decision: {self.decision}")

    def as_payload(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def decide_completion(handler: Any, proposal: CompletionProposal) -> CompletionDecision:
    """Invoke an explicit optional gate, otherwise preserve legacy completion."""
    gate = getattr(handler, "completion_gate", None)
    if gate is None:
        return CompletionDecision()
    try:
        value = gate(proposal)
        if value is None:
            return CompletionDecision()
        if not isinstance(value, CompletionDecision):
            raise TypeError("completion_gate must return CompletionDecision")
        return value
    except Exception as exc:
        emit("completion_gate_error", {"error_type": type(exc).__name__, "message": str(exc)[:500]})
        return CompletionDecision(decision="ERROR_FAIL_OPEN", reason_codes=("GATE_EXCEPTION",))
