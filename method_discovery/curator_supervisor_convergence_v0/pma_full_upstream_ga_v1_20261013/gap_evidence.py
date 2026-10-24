"""Host-owned literal provenance primitives; no inference or entailment claims.

Adapted from this repository's SourceMemory register_source/resolve_refs/hash
validation and SourceMemoryV2 leaf identities/handles. Conceptual credits only:
Graphiti 8ce6d633, graphiti_core/utils/maintenance/combined_extraction.py:48-55
(model selects, program resolves); OpenWiki 305599f8,
src/claims/core/mutations.ts:45-166 (prevalidate before publishing mutations).
No upstream framework code, permissive alignment, or fallback is imported.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from types import MappingProxyType
from typing import Mapping


class SourceScopeError(ValueError):
    """Bounded per-call rejection, never a task-engine exception contract."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _key(*parts) -> str:
    return json.dumps(parts, ensure_ascii=False, separators=(",", ":"))


def _require(condition, code):
    if not condition:
        raise SourceScopeError(code)


def _text(value):
    return isinstance(value, str) and bool(value)


def _digest(value):
    return isinstance(value, str) and len(value) == 64 and all(
        c in "0123456789abcdef" for c in value)


@dataclass(frozen=True)
class TextBlob:
    text_sha256: str
    text: str


@dataclass(frozen=True)
class SourceRecord:
    namespace: str
    source_id: str
    handle: str
    event_id: str
    field_path: str
    role: str
    order: int
    text_sha256: str
    record_digest: str
    record_digest_kind: str
    source_kind: str = "public"
    parent_revision_id: str | None = None
    parent_wrapper_source_id: str | None = None
    tool_call_id: str | None = None


@dataclass(frozen=True)
class SourceSnapshot:
    record: SourceRecord
    blob: TextBlob
    parent_wrapper: SourceSnapshot | None = None


class SourceRegistry:
    """Transient host cache; immutable rows/blobs can be retained by reference.

    Registration is append-only in this cache. A bank retains cited snapshots
    before replacing a window cache; snapshots never reference the cache itself.
    No per-cycle history clone or automatic forever-retention is performed here.
    """

    def __init__(self, namespace: str):
        _require(_text(namespace), "invalid_namespace")
        self.namespace = namespace
        self._sources = {}
        self._handles = {}
        self._blobs = {}

    @property
    def sources(self) -> Mapping[str, SourceSnapshot]:
        return MappingProxyType(self._sources)

    def snapshot(self, source_id: str) -> SourceSnapshot:
        return self._sources[source_id]

    def _register(self, row, text, parent=None):
        old = self._sources.get(row.source_id)
        if old is not None:
            _require(old.record == row and old.blob.text == text and
                     old.parent_wrapper == parent, "source_identity_changed")
            return self, old.record
        _require(self._handles.get(row.handle, row.source_id) == row.source_id,
                 "source_handle_collision")
        blob = self._blobs.get(row.text_sha256, TextBlob(row.text_sha256, text))
        _require(blob.text == text, "source_digest_collision")
        snapshot = SourceSnapshot(row, blob, parent)
        _require(_snapshot_valid(snapshot), "invalid_source_snapshot")
        self._blobs[row.text_sha256] = blob
        self._handles[row.handle] = row.source_id
        self._sources[row.source_id] = snapshot
        return self, row


def register_public_source(registry, *, event_id, role, text, order,
                           field_path, record_digest, record_digest_kind,
                           parent_wrapper_source_id=None, tool_call_id=None):
    _require(isinstance(role, str) and role in {"task_instruction", "tool_observation", "agent_report",
                     "tool_command"}, "invalid_public_role")
    _require(all(_text(x) for x in (event_id, field_path, text, record_digest_kind))
             and type(order) is int and order >= 0 and _digest(record_digest),
             "invalid_public_identity")
    source_id = _key(registry.namespace, "public", event_id, field_path)
    row = SourceRecord(registry.namespace, source_id, "s" + sha256(source_id)[:12],
                       event_id, field_path, role, order, sha256(text),
                       record_digest, record_digest_kind,
                       parent_wrapper_source_id=parent_wrapper_source_id, tool_call_id=tool_call_id)
    parent = None
    if parent_wrapper_source_id is not None:
        parent = registry.sources.get(parent_wrapper_source_id)
        _require(parent is not None, "missing_wrapper_parent")
    return registry._register(row, text, parent)


def register_memory_source(registry, *, revision_id, text, order=0):
    """Host supplies an existing pre-cycle revision, never model-assigned IDs.

    Text is a shared Python string; persistence should store revision text once
    and resolve this snapshot through parent_revision_id, not serialize it twice.
    """
    _require(_text(revision_id) and _text(text) and type(order) is int and order >= 0,
             "invalid_memory_identity")
    source_id = _key(registry.namespace, "memory", revision_id)
    row = SourceRecord(registry.namespace, source_id, "s" + sha256(source_id)[:12],
                       revision_id, "content", "memory_derived", order,
                       sha256(text), sha256(text), "revision_content",
                       "memory", revision_id)
    return registry._register(row, text)


def _snapshot_valid(snapshot):
    r, b = snapshot.record, snapshot.blob
    if not (_text(r.namespace) and _text(b.text) and type(r.order) is int and
            r.order >= 0 and r.text_sha256 == b.text_sha256 == sha256(b.text) and
            _digest(r.record_digest) and _text(r.record_digest_kind)):
        return False
    if r.source_kind == "memory":
        identity = _key(r.namespace, "memory", r.parent_revision_id)
        valid = (_text(r.parent_revision_id) and r.event_id == r.parent_revision_id
                 and r.role == "memory_derived" and r.field_path == "content"
                 and r.record_digest == r.text_sha256
                 and r.record_digest_kind == "revision_content")
    else:
        identity = _key(r.namespace, "public", r.event_id, r.field_path)
        valid = (r.source_kind == "public" and r.parent_revision_id is None and
                 _text(r.event_id) and _text(r.field_path) and r.role in
                 {"task_instruction", "tool_observation", "agent_report", "tool_command"})
    if r.tool_call_id is not None and (r.role != "tool_observation" or not _text(r.tool_call_id)):
        return False
    if not (valid and r.source_id == identity and r.handle == "s" + sha256(identity)[:12]):
        return False
    p = snapshot.parent_wrapper
    if r.parent_wrapper_source_id is None:
        return p is None
    if p is None or p.parent_wrapper is not None or not _snapshot_valid(p):
        return False
    pr = p.record
    if not (r.source_kind == pr.source_kind == "public" and
            r.role == pr.role == "tool_observation" and r.namespace == pr.namespace
            and r.parent_wrapper_source_id == pr.source_id and
            (r.event_id, r.order, r.record_digest, r.record_digest_kind) ==
            (pr.event_id, pr.order, pr.record_digest, pr.record_digest_kind) and
            r.field_path.rsplit("/", 1)[0] == pr.field_path):
        return False
    try:
        envelope = json.loads(p.blob.text)
        return isinstance(envelope, dict) and envelope.get(r.field_path.rsplit("/", 1)[-1]) == b.text
    except (ValueError, TypeError):
        return False


@dataclass(frozen=True)
class RenderBlock:
    snapshot: SourceSnapshot
    spans: tuple[tuple[int, int], ...] | None = None
    display_id: str | None = None


@dataclass(frozen=True)
class VisibleSource:
    snapshot: SourceSnapshot
    visible_spans: tuple[tuple[int, int], ...]
    visibility_ref: str
    display_transform: str = "literal"
    cycle_id: str = ""
    request_sha256: str = ""

    def __post_init__(self):
        object.__setattr__(self, "visible_spans", tuple(tuple(s) for s in self.visible_spans))


@dataclass(frozen=True)
class BoundRef:
    source_id: str
    source_kind: str
    role: str
    order: int
    start: int
    end: int
    source_text_sha256: str
    snippet_sha256: str
    visibility_ref: str
    parent_revision_id: str | None = None
    parent_wrapper_source_id: str | None = None


@dataclass(frozen=True)
class RequestManifest:
    cycle_id: str
    request_sha256: str
    ordered_source_refs: tuple[str, ...]
    visible_spans: tuple[tuple[tuple[int, int], ...], ...]
    visibility_refs: tuple[str, ...]
    pre_cycle_revision_refs: tuple[str, ...]


@dataclass(frozen=True)
class RenderedPhase1Parts:
    text: str
    catalog: Mapping[str, VisibleSource]
    manifest: RequestManifest


def render_source_blocks(blocks, *, cycle_id, prefix="", suffix=""):
    """Seal the final submitted text; callers must not subsequently truncate it.

    Blocks are explicit host projections, not registry membership. Raw wrapper
    only is supported by omitting decoded child blocks. Spans are Unicode indices.
    """
    _require(_text(cycle_id) and isinstance(prefix, str) and isinstance(suffix, str),
             "invalid_render_context")
    parts, rows, by_handle = [prefix], [], {}
    for block in blocks:
        snap = block.snapshot
        _require(_snapshot_valid(snap), "invalid_source_snapshot")
        r, text = snap.record, snap.blob.text
        spans = ((0, len(text)),) if block.spans is None else tuple(tuple(s) for s in block.spans)
        _require(bool(spans) and all(len(s) == 2 and all(type(i) is int for i in s)
                 and 0 <= s[0] < s[1] <= len(text) for s in spans), "invalid_visible_spans")
        handle = r.handle if block.display_id is None else block.display_id
        _require(_text(handle) and not any(c.isspace() or c in "[]" for c in handle),
                 "invalid_display_id")
        _require(r.source_kind == "memory" or handle == r.handle, "public_alias_forbidden")
        previous = by_handle.get(handle)
        _require(previous is None or previous[0] == snap, "source_handle_collision")
        combined = (() if previous is None else previous[1]) + spans
        by_handle[handle] = (snap, combined)
        parts.append(f"\n[{handle} {r.role} event_order={r.order} field={r.field_path}]\n")
        parts.append("\n[hidden gap]\n".join(text[a:b] for a, b in spans))
        rows.append((r.source_id, spans, handle))
    parts.append(suffix)
    request = "".join(parts)
    request_hash = sha256(request)
    catalog = {}
    for handle, (snap, spans) in by_handle.items():
        visibility = sha256(_key(cycle_id, request_hash, snap.record.source_id, spans))
        catalog[handle] = VisibleSource(snap, spans, visibility, "literal", cycle_id, request_hash)
    manifest = RequestManifest(cycle_id, request_hash, tuple(r[0] for r in rows),
        tuple(r[1] for r in rows),
        tuple(catalog[r[2]].visibility_ref for r in rows),
        tuple(dict.fromkeys(v.snapshot.record.parent_revision_id for v in catalog.values()
                            if v.snapshot.record.parent_revision_id is not None)))
    return RenderedPhase1Parts(request, MappingProxyType(catalog), manifest)


def bind_evidence(evidence, catalog) -> tuple[BoundRef, ...]:
    _require(isinstance(evidence, list) and bool(evidence), "empty_evidence")
    result = []
    for item in evidence:
        _require(isinstance(item, dict) and set(item) == {"source", "quote"}
                 and _text(item["source"]) and _text(item["quote"]), "invalid_evidence_item")
        visible = catalog.get(item["source"])
        _require(visible is not None, "source_not_visible")
        snap, quote = visible.snapshot, item["quote"]
        _require(_snapshot_valid(snap), "invalid_source_snapshot")
        starts = set()
        for a, b in visible.visible_spans:
            start = snap.blob.text.find(quote, a, b)
            while start >= 0:
                starts.add(start)
                _require(len(starts) <= 1, "ambiguous_quote")
                start = snap.blob.text.find(quote, start + 1, b)
        _require(len(starts) == 1, "quote_not_visible")
        start = next(iter(starts))
        r = snap.record
        ref = BoundRef(r.source_id, r.source_kind, r.role, r.order, start,
                       start + len(quote), r.text_sha256, sha256(quote),
                       visible.visibility_ref, r.parent_revision_id, r.parent_wrapper_source_id)
        if ref not in result:
            result.append(ref)
    return tuple(result)


def bound_ref_valid(ref, resolver) -> bool:
    """Resolver maps a retained visibility_ref to its immutable VisibleSource."""
    try:
        if not isinstance(ref, BoundRef):
            return False
        visible = resolver.get(ref.visibility_ref)
        if visible is None or visible.visibility_ref != ref.visibility_ref:
            return False
        snap, a, b = visible.snapshot, ref.start, ref.end
        r = snap.record
        expected_visibility = sha256(_key(visible.cycle_id, visible.request_sha256,
                                          r.source_id, visible.visible_spans))
        return (_snapshot_valid(snap) and type(ref.order) is int and
                _text(visible.cycle_id) and _digest(visible.request_sha256) and
                visible.visibility_ref == expected_visibility and
                visible.display_transform == "literal" and
                type(a) is int and type(b) is int and 0 <= a < b <= len(snap.blob.text) and
                any(x <= a < b <= y for x, y in visible.visible_spans) and
                (ref.source_id, ref.source_kind, ref.role, ref.order,
                 ref.source_text_sha256, ref.parent_revision_id, ref.parent_wrapper_source_id) ==
                (r.source_id, r.source_kind, r.role, r.order, r.text_sha256,
                 r.parent_revision_id, r.parent_wrapper_source_id) and
                ref.snippet_sha256 == sha256(snap.blob.text[a:b]))
    except (AttributeError, TypeError, ValueError):
        return False


def excerpt(ref, resolver) -> str:
    _require(bound_ref_valid(ref, resolver), "invalid_bound_ref")
    return resolver[ref.visibility_ref].snapshot.blob.text[ref.start:ref.end]


@dataclass(frozen=True)
class Receipt:
    receipt_id: str
    run_id: str
    cycle_id: str
    op_index: int
    action: str
    target_revision_id: str
    bound_refs: tuple[BoundRef, ...]

    def __post_init__(self):
        object.__setattr__(self, "bound_refs", tuple(self.bound_refs))
        _require(all(isinstance(r, BoundRef) for r in self.bound_refs), "invalid_receipt_refs")


@dataclass(frozen=True)
class AppendChunk:
    previous: AppendChunk | None
    rows: tuple

    def __post_init__(self):
        object.__setattr__(self, "rows", tuple(self.rows))


def append_chunk(previous, delta):
    """Caller supplies immutable records; history is shared, never cloned."""
    rows = tuple(delta)
    return AppendChunk(previous, rows) if rows else previous


def record_to_dict(record):
    """JSON-safe detached serialization; never use on an entire staged bank."""
    return asdict(record)
