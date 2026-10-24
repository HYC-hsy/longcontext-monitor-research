"""Opt-in evidence bank. Serial atomic publication; task-end durability only."""
from collections import ChainMap
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from types import MappingProxyType
import uuid

from gap_store import GapMemory
from gap_evidence import (BoundRef, Receipt, RequestManifest, SourceRecord,
    SourceSnapshot, TextBlob, VisibleSource, bound_ref_valid, register_memory_source,
    sha256, _snapshot_valid)
from source_memory import SourceMemory


class History(Mapping):
    """Persistent immutable map: adding a delta never copies historical rows."""
    def __init__(self, previous=None, rows=()):
        self.previous = previous
        self.rows = MappingProxyType(dict(rows))

    def __getitem__(self, key):
        node = self
        while node is not None:
            if key in node.rows:
                return node.rows[key]
            node = node.previous
        raise KeyError(key)

    def __iter__(self):
        seen, node = set(), self
        while node is not None:
            for key in node.rows:
                if key not in seen:
                    seen.add(key)
                    yield key
            node = node.previous

    def __len__(self):
        return sum(1 for _ in self)

    def add(self, key, value):
        if key in self:
            if self[key] != value:
                raise ValueError("immutable history identity changed")
            return self
        return History(self, ((key, value),))


@dataclass(frozen=True)
class Revision:
    revision_id: str
    memory_id: str
    category: str
    content_sha256: str
    receipt_id: str | None = None
    proposal_sha256: str | None = None


@dataclass(frozen=True)
class Tombstone:
    tombstone_id: str
    memory_id: str
    revision_id: str
    cycle_id: str
    op_index: int


class PreparedPublication(dict):
    pass


class EvidenceGapMemory(GapMemory):
    _HISTORIES = ("blobs", "sources", "visibility", "manifests", "revisions",
                  "receipts", "tombstones")

    def __init__(self, max_status_length=2000):
        super().__init__(max_status_length)
        for name in self._HISTORIES:
            setattr(self, name, History())
        self.active_revisions = {}
        self._generation = 0

    def _content(self, key):
        if key == "status":
            return "status", self.status
        for kind, entries in (("knowledge", self._knowledge),
                              ("procedural", self._procedural), ("gap", self._gap_entries)):
            for entry in entries:
                if entry.id == key:
                    return kind, entry.content
        raise ValueError("memory ID not found")

    def _used_ids(self):
        return ({e.id for e in self._knowledge + self._procedural + self._gap_entries}
                | {r.memory_id for r in self.revisions.values()} | {"status"})

    def _generate_id(self):
        used = self._used_ids()
        for _ in range(32):
            key = super()._generate_id()
            if key not in used and not key.startswith("gap_"):
                return key
        return uuid.uuid4().hex

    def save_knowledge(self, content):
        key = super().save_knowledge(content)
        self._generation += 1
        return key

    def save_procedural(self, content):
        key = super().save_procedural(content)
        self._generation += 1
        return key

    def update_status(self, content):
        super().update_status(content)
        self.active_revisions.pop("status", None)
        self._generation += 1

    def save_gap(self, content):
        used = self._used_ids()
        key = super().save_gap(content)
        self._generation += 1
        if key in used:
            key = "gap_" + uuid.uuid4().hex
            self._gap_entries[-1].id = key
        return key

    def _revision(self, key, receipt_id=None, proposal=None):
        category, content = self._content(key)
        digest = sha256(content)
        self.blobs = self.blobs.add(digest, content)
        row = Revision("rev_" + uuid.uuid4().hex, key, category, digest,
                       receipt_id, sha256(proposal) if proposal is not None else None)
        self.revisions = self.revisions.add(row.revision_id, row)
        self.active_revisions[key] = row.revision_id
        return row

    def memory_source(self, registry, memory_id, order=0):
        category, content = self._content(memory_id)
        current = self.active_revisions.get(memory_id)
        if current is None:
            current = self._revision(memory_id).revision_id
        row = self.revisions[current]
        if row.content_sha256 != sha256(content) or row.category != category:
            raise ValueError("active content changed outside evidence writers")
        return register_memory_source(registry, revision_id=current,
                                      text=content, order=order)[1]

    def retain_manifest(self, parts):
        self._pending_visibility = {v.visibility_ref: v for v in parts.catalog.values()}
        self.manifests = self.manifests.add(parts.manifest.cycle_id, parts.manifest)

    def _retain_source(self, snapshot):
        if not _snapshot_valid(snapshot):
            raise ValueError("invalid source snapshot")
        if snapshot.parent_wrapper is not None:
            self._retain_source(snapshot.parent_wrapper)
        row = snapshot.record
        if row.source_kind == "memory":
            parent = self.revisions.get(row.parent_revision_id)
            if parent is None or parent.content_sha256 != row.text_sha256:
                raise ValueError("unknown memory source revision")
        self.blobs = self.blobs.add(row.text_sha256, snapshot.blob.text)
        self.sources = self.sources.add(row.source_id, row)

    def fork_write_draft(self):
        draft = object.__new__(type(self))
        draft.__dict__ = self.__dict__.copy()
        for name in ("_knowledge", "_procedural", "_gap_entries"):
            setattr(draft, name, list(getattr(self, name)))
        draft.active_revisions = self.active_revisions.copy()
        draft._draft_owner = self
        draft._draft_generation = self._generation
        return draft

    def apply_bound_write(self, kind, content, refs, *, cycle_id, op_index, run_id=""):
        resolver = ChainMap(getattr(self, "_pending_visibility", {}), self.visibility)
        if (kind not in {"knowledge", "procedural", "gap", "status"}
                or not isinstance(content, str) or not content.strip() or not refs
                or not all(bound_ref_valid(ref, resolver) for ref in refs)):
            raise ValueError("invalid bound write")
        manifest = self.manifests.get(cycle_id)
        if manifest is None or any(ref.visibility_ref not in manifest.visibility_refs for ref in refs):
            raise ValueError("write references another request")
        for ref in refs:
            visible = resolver[ref.visibility_ref]
            self._retain_source(visible.snapshot)
            self.visibility = self.visibility.add(ref.visibility_ref, visible)
        if kind == "status":
            self.update_status(content)
            key = "status"
        else:
            key = getattr(self, "save_" + kind)(content)
        receipt_id = "receipt_" + uuid.uuid4().hex
        revision = self._revision(key, receipt_id, content)
        receipt = Receipt(receipt_id, run_id, cycle_id, op_index, "save_" + kind,
                          revision.revision_id, tuple(refs))
        self.receipts = self.receipts.add(receipt_id, receipt)
        return key, revision.revision_id

    def delete_bound(self, memory_id, *, cycle_id="", op_index=0):
        if memory_id == "status":
            raise ValueError("status cannot be deleted by ID")
        self._content(memory_id)
        revision = self.active_revisions.get(memory_id)
        if revision is None:
            revision = self._revision(memory_id).revision_id
        deleted = (super().delete_gap(memory_id) if memory_id.startswith("gap_")
                   else super().delete(memory_id))
        if not deleted:
            raise ValueError("memory ID not found")
        row = Tombstone("tomb_" + uuid.uuid4().hex, memory_id, revision, cycle_id, op_index)
        self.tombstones = self.tombstones.add(row.tombstone_id, row)
        self.active_revisions.pop(memory_id, None)
        self._generation += 1
        return True

    def delete(self, memory_id):
        if self.get(memory_id) is None:
            return False
        return self.delete_bound(memory_id)

    def delete_gap(self, memory_id):
        if not any(e.id == memory_id for e in self._gap_entries):
            return False
        return self.delete_bound(memory_id)

    def clear(self, keep_status=False):
        for entry in list(self._knowledge + self._procedural + self._gap_entries):
            self.delete_bound(entry.id)
        self._generation += 1
        if not keep_status:
            self._status = ""
            self.active_revisions.pop("status", None)
        self._invalidate_indices("knowledge")
        self._invalidate_indices("procedural")

    def prepare_publication(self, draft):
        if (getattr(draft, "_draft_owner", None) is not self or
                draft._draft_generation != self._generation):
            raise ValueError("stale or foreign draft")
        draft.validate_bank()
        prepared = PreparedPublication(draft.__dict__)
        prepared.owner = self
        prepared.generation = self._generation
        prepared.pop("_pending_visibility", None)
        prepared.pop("_draft_owner")
        prepared.pop("_draft_generation")
        prepared["_generation"] = self._generation + 1
        return prepared

    def publish(self, prepared):
        if (not isinstance(prepared, PreparedPublication) or prepared.owner is not self
                or prepared.generation != self._generation):
            raise ValueError("stale publication")
        self.__dict__ = prepared

    def validate_bank(self):
        entries = self._knowledge + self._procedural + self._gap_entries
        ids = [e.id for e in entries]
        if (len(ids) != len(set(ids)) or "status" in ids or
                any(not e.id.startswith("gap_") for e in self._gap_entries) or
                any(e.id.startswith("gap_") for e in self._knowledge + self._procedural)):
            raise ValueError("invalid bank identities")
        retired = {r.memory_id for r in self.tombstones.values()}
        if retired.intersection(ids):
            raise ValueError("retired ID is active")
        for digest, content in self.blobs.items():
            if not isinstance(content, str) or sha256(content) != digest:
                raise ValueError("invalid content blob")
        for key, revision_id in self.active_revisions.items():
            kind, content = self._content(key)
            row = self.revisions[revision_id]
            if (row.memory_id, row.category, row.content_sha256) != (key, kind, sha256(content)):
                raise ValueError("active revision mismatch")
        for row in self.revisions.values():
            if row.category not in {"knowledge", "procedural", "status", "gap"} or row.content_sha256 not in self.blobs:
                raise ValueError("invalid revision")
            if row.receipt_id is not None and self.receipts[row.receipt_id].target_revision_id != row.revision_id:
                raise ValueError("invalid revision receipt")
        for row in self.sources.values():
            snapshot = self._snapshot(row.source_id)
            if not _snapshot_valid(snapshot):
                raise ValueError("invalid retained source")
            if row.source_kind == "memory" and self.revisions[row.parent_revision_id].content_sha256 != row.text_sha256:
                raise ValueError("invalid retained memory source")
        for ref, visible in self.visibility.items():
            row = visible.snapshot.record
            spans = visible.visible_spans
            if (ref != visible.visibility_ref or not spans or
                    not all(len(span) == 2 and all(type(i) is int for i in span)
                            and 0 <= span[0] < span[1] <= len(visible.snapshot.blob.text)
                            for span in spans)):
                raise ValueError("invalid visibility")
            a, b = spans[0]
            probe = BoundRef(row.source_id, row.source_kind, row.role, row.order, a, b,
                row.text_sha256, sha256(visible.snapshot.blob.text[a:b]), ref,
                row.parent_revision_id, row.parent_wrapper_source_id)
            manifest = self.manifests[visible.cycle_id]
            if (not bound_ref_valid(probe, self.visibility) or
                    manifest.request_sha256 != visible.request_sha256 or
                    ref not in manifest.visibility_refs or row.source_id not in manifest.ordered_source_refs):
                raise ValueError("invalid visibility manifest")
        for manifest in self.manifests.values():
            if (not isinstance(manifest.cycle_id, str) or not manifest.cycle_id or
                    len(manifest.request_sha256) != 64 or
                    len(manifest.ordered_source_refs) != len(manifest.visible_spans) or
                    any(key not in self.revisions for key in manifest.pre_cycle_revision_refs)):
                raise ValueError("invalid request manifest")
        for row in self.receipts.values():
            revision = self.revisions[row.target_revision_id]
            manifest = self.manifests[row.cycle_id]
            if (revision.receipt_id != row.receipt_id or not row.bound_refs or
                    not all(bound_ref_valid(ref, self.visibility) and ref.visibility_ref in
                            manifest.visibility_refs for ref in row.bound_refs)):
                raise ValueError("invalid receipt")
            for ref in row.bound_refs:
                if ref.parent_revision_id is not None:
                    parent = self.revisions[ref.parent_revision_id]
                    if (parent.revision_id not in manifest.pre_cycle_revision_refs or
                            (parent.receipt_id is not None and
                             self.receipts[parent.receipt_id].cycle_id == row.cycle_id)):
                        raise ValueError("non-pre-cycle memory parent")
        for row in self.tombstones.values():
            if self.revisions[row.revision_id].memory_id != row.memory_id:
                raise ValueError("invalid tombstone")

    def _snapshot(self, source_id):
        row = self.sources[source_id]
        parent = self._snapshot(row.parent_wrapper_source_id) if row.parent_wrapper_source_id else None
        return SourceSnapshot(row, TextBlob(row.text_sha256, self.blobs[row.text_sha256]), parent)

    def to_dict(self):
        self.validate_bank()
        data = super().to_dict()
        evidence = {"schema": 1, "active_revisions": self.active_revisions.copy(),
                    "blobs": dict(self.blobs), "max_status_length": self._max_status_length}
        for name in ("sources", "manifests", "revisions", "receipts", "tombstones"):
            evidence[name] = {key: asdict(row) for key, row in getattr(self, name).items()}
        evidence["visibility"] = {key: {"source_id": v.snapshot.record.source_id,
            "visible_spans": v.visible_spans, "visibility_ref": v.visibility_ref,
            "display_transform": v.display_transform, "cycle_id": v.cycle_id,
            "request_sha256": v.request_sha256} for key, v in self.visibility.items()}
        return {**data, "gap_evidence": evidence}

    @classmethod
    def from_dict(cls, data):
        memory = super().from_dict(data)
        evidence = data.get("gap_evidence")
        if "gap_evidence" not in data:
            memory.validate_bank()
            return memory
        required = {"schema", "active_revisions", "max_status_length", *cls._HISTORIES}
        if not isinstance(evidence, dict) or set(evidence) != required or type(evidence["schema"]) is not int or evidence["schema"] != 1:
            raise ValueError("unknown or malformed evidence schema")
        try:
            limit = evidence["max_status_length"]
            if type(limit) is not int or limit < 0:
                raise ValueError("invalid status limit")
            memory._max_status_length = limit
            memory.active_revisions = dict(evidence["active_revisions"])
            memory.blobs = History(rows=evidence["blobs"].items())
            for name, constructor in (("sources", SourceRecord), ("revisions", Revision),
                                      ("receipts", Receipt), ("tombstones", Tombstone),
                                      ("manifests", RequestManifest)):
                rows = {}
                for key, value in evidence[name].items():
                    value = dict(value)
                    if name == "receipts":
                        value["bound_refs"] = tuple(BoundRef(**r) for r in value["bound_refs"])
                    if name == "manifests":
                        for field in ("ordered_source_refs", "visibility_refs", "pre_cycle_revision_refs"):
                            value[field] = tuple(value[field])
                        value["visible_spans"] = tuple(tuple(tuple(s) for s in spans) for spans in value["visible_spans"])
                    row = constructor(**value)
                    identity = getattr(row, {"sources": "source_id", "manifests": "cycle_id"}.get(name, name[:-1] + "_id"))
                    if identity != key:
                        raise ValueError("history identity mismatch")
                    rows[key] = row
                setattr(memory, name, History(rows=rows.items()))
            for value in evidence["visibility"].values():
                if set(value) != {"source_id", "visible_spans", "visibility_ref",
                                  "display_transform", "cycle_id", "request_sha256"}:
                    raise ValueError("malformed visibility record")
            memory.visibility = History(rows=((key, VisibleSource(memory._snapshot(v["source_id"]),
                tuple(tuple(s) for s in v["visible_spans"]), v["visibility_ref"], v["display_transform"],
                v["cycle_id"], v["request_sha256"]))
                for key, v in evidence["visibility"].items()))
            memory.validate_bank()
        except (KeyError, TypeError, AttributeError, RecursionError) as exc:
            raise ValueError("malformed evidence bank") from exc
        return memory

    # Reuse the established temporary-file/flush/fsync/replace checkpoint writer.
    save_to_file = SourceMemory.save_to_file
