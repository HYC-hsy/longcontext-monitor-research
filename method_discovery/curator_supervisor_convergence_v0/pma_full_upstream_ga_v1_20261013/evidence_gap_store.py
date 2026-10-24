"""Opt-in evidence bank. Serial atomic publication; task-end durability only."""
from collections import ChainMap
from collections.abc import Mapping
from dataclasses import asdict, dataclass, replace
from types import MappingProxyType
import uuid

from gap_store import GapMemory
from gap_evidence import (BoundRef, Receipt, RequestManifest, SourceRecord,
    SourceSnapshot, TextBlob, VisibleSource, bound_ref_valid, register_memory_source,
    sha256, _snapshot_valid, _key)
from source_memory import SourceMemory
from rpds import HashTrieMap


@dataclass(frozen=True, init=False)
class History(Mapping):
    """Immutable delta chunks indexed by the mature rpds.HashTrieMap HAMT."""
    previous: object
    rows: Mapping
    _index: Mapping

    def __init__(self, previous=None, rows=()):
        rows = dict(rows)
        index = previous._index if previous is not None else HashTrieMap()
        for key, value in rows.items():
            if previous is not None and key in previous:
                raise ValueError("duplicate immutable history identity")
            index = index.insert(key, value)
        object.__setattr__(self, "previous", previous)
        object.__setattr__(self, "rows", MappingProxyType(rows))
        object.__setattr__(self, "_index", index)

    def __getitem__(self, key):
        return self._index[key]

    def items(self):
        return self._index.items()

    def values(self):
        return self._index.values()

    def __iter__(self):
        return iter(self._index)

    def __len__(self):
        return len(self._index)

    def add(self, key, value):
        if key in self:
            if self[key] != value:
                raise ValueError("immutable history identity changed")
            return self
        return History(self, ((key, value),))

    def delta(self, base):
        node = self
        while node is not base:
            if node is None:
                raise ValueError("history does not extend draft base")
            yield from node.rows.items()
            node = node.previous


@dataclass(frozen=True)
class Revision:
    revision_id: str
    memory_id: str
    category: str
    content_sha256: str
    receipt_id: str | None = None
    proposal_sha256: str | None = None
    entry_snapshot: tuple = ()
    previous_revision_id: str | None = None


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
        self._reserved_ids = History()
        self._retired_ids = History()
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

    def _id_in_use(self, key):
        return (key == "status" or key in self._reserved_ids or
                any(e.id == key for e in self._knowledge + self._procedural + self._gap_entries))

    def _generate_id(self):
        for _ in range(32):
            key = super()._generate_id()
            if not self._id_in_use(key) and not key.startswith("gap_"):
                return key
        return uuid.uuid4().hex

    def save_knowledge(self, content):
        key = super().save_knowledge(content)
        self._reserved_ids = self._reserved_ids.add(key, True)
        self._generation += 1
        return key

    def save_procedural(self, content):
        key = super().save_procedural(content)
        self._reserved_ids = self._reserved_ids.add(key, True)
        self._generation += 1
        return key

    def update_status(self, content):
        super().update_status(content)
        self.active_revisions.pop("status", None)
        self._generation += 1

    def save_gap(self, content):
        key = super().save_gap(content)
        self._generation += 1
        if key in self._reserved_ids:
            key = "gap_" + uuid.uuid4().hex
            self._gap_entries[-1].id = key
        self._reserved_ids = self._reserved_ids.add(key, True)
        return key

    def _revision(self, key, receipt_id=None, proposal=None, previous_revision_id=None):
        category, content = self._content(key)
        self._reserved_ids = self._reserved_ids.add(key, True)
        digest = sha256(content)
        self.blobs = self.blobs.add(digest, content)
        snapshot = {}
        if key != "status":
            entry = next(e for e in self._knowledge + self._procedural + self._gap_entries if e.id == key)
            snapshot = entry.to_dict()
            snapshot.pop("content")
            snapshot["content_sha256"] = digest
        row = Revision("rev_" + uuid.uuid4().hex, key, category, digest,
                       receipt_id, sha256(proposal) if proposal is not None else None,
                       tuple(snapshot.items()), previous_revision_id)
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

    def apply_bound_write(self, kind, content, refs, *, cycle_id, op_index, run_id="",
                          memory_id=None):
        resolver = ChainMap(getattr(self, "_pending_visibility", {}), self.visibility)
        if (kind not in {"knowledge", "procedural", "gap", "status"}
                or not isinstance(content, str) or not content.strip() or not refs
                or not all(bound_ref_valid(ref, resolver) for ref in refs)):
            raise ValueError("invalid bound write")
        manifest = self.manifests.get(cycle_id)
        if manifest is None or any(ref.visibility_ref not in manifest.visibility_refs for ref in refs):
            raise ValueError("write references another request")
        previous = None
        if memory_id is not None:
            if (not isinstance(memory_id, str) or not memory_id or kind == "status"
                    or self._content(memory_id)[0] != kind):
                raise ValueError("update target must be an existing same-category memory ID")
            previous = self.active_revisions.get(memory_id)
            if previous is None:
                previous = self._revision(memory_id).revision_id
        elif kind == "status" and self.status:
            previous = self.active_revisions.get("status")
            if previous is None:
                previous = self._revision("status").revision_id
        for ref in refs:
            visible = resolver[ref.visibility_ref]
            self._retain_source(visible.snapshot)
            self.visibility = self.visibility.add(ref.visibility_ref, visible)
        if kind == "status":
            self.update_status(content)
            key = "status"
        elif memory_id is not None:
            key = memory_id
            entries = getattr(self, {"gap": "_gap_entries"}.get(kind, "_" + kind))
            index = next(i for i, entry in enumerate(entries) if entry.id == key)
            # Draft lists share entries with the owner: replace, never mutate.
            entries[index] = replace(entries[index], content=content)
            self._invalidate_indices(kind)
            self._generation += 1
        else:
            key = getattr(self, "save_" + kind)(content)
        receipt_id = "receipt_" + uuid.uuid4().hex
        revision = self._revision(key, receipt_id, content, previous)
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
        self._retired_ids = self._retired_ids.add(memory_id, True)
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
        draft.validate_draft(self)
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

    def validate_draft(self, base):
        """Validate active state and this draft's deltas, never rehash old history."""
        rows = {name: dict(getattr(self, name).delta(getattr(base, name)))
                for name in self._HISTORIES}
        for name in ("_reserved_ids", "_retired_ids"):
            if any(value is not True for _, value in getattr(self, name).delta(getattr(base, name))):
                raise ValueError("invalid ID index")
        new_ids = {e.id for e in self._knowledge + self._procedural + self._gap_entries}
        old_ids = {e.id for e in base._knowledge + base._procedural + base._gap_entries}
        deleted = {row.memory_id for row in rows["tombstones"].values() if isinstance(row, Tombstone)}
        reserved = {key for key, _ in self._reserved_ids.delta(base._reserved_ids)}
        revision_ids = {row.memory_id for row in rows["revisions"].values() if isinstance(row, Revision)}
        if (not old_ids.difference(new_ids).issubset(deleted) or
                not reserved.issubset(new_ids | revision_ids) or
                {key for key, _ in self._retired_ids.delta(base._retired_ids)} != deleted):
            raise ValueError("untracked active or ID-index mutation")
        latest = {}
        for row in rows["revisions"].values():
            if isinstance(row, Revision):
                latest.setdefault(row.memory_id, row.revision_id)
        for key in new_ids | ({"status"} if self.status else set()):
            if key in latest and self.active_revisions.get(key) != latest[key]:
                raise ValueError("new revision missing from active map")
        self._validate_records(rows)
        # An old revision cannot be retargeted to a newly created receipt/revision.
        # New memory sources must point to revisions that existed before this cycle,
        # except legacy snapshots materialized from the unchanged active base.
        for source in rows["sources"].values():
            if source.source_kind == "memory" and source.parent_revision_id not in base.revisions:
                parent = self.revisions[source.parent_revision_id]
                if parent.receipt_id is not None or base._content(parent.memory_id)[1] != self.blobs[parent.content_sha256]:
                    raise ValueError("memory source was not pre-cycle")

    def validate_bank(self):
        self._validate_records({name: getattr(self, name) for name in self._HISTORIES})
        self._validate_lineage()

    def _validate_lineage(self):
        """Iterative DFS rejects cyclic ancestry even in internally consistent files."""
        done = set()
        for start in self.revisions:
            stack, visiting = [(start, False)], set()
            while stack:
                key, finish = stack.pop()
                if finish:
                    visiting.remove(key)
                    done.add(key)
                    continue
                if key in visiting:
                    raise ValueError("cyclic memory ancestry")
                if key in done:
                    continue
                visiting.add(key)
                stack.append((key, True))
                row = self.revisions[key]
                if row.previous_revision_id is not None:
                    stack.append((row.previous_revision_id, False))
                if row.receipt_id is not None:
                    for ref in self.receipts[row.receipt_id].bound_refs:
                        if ref.parent_revision_id is not None:
                            stack.append((ref.parent_revision_id, False))

    def _validate_records(self, rows):
        entries = self._knowledge + self._procedural + self._gap_entries
        ids = [e.id for e in entries]
        if (len(ids) != len(set(ids)) or "status" in ids or
                any(not e.id.startswith("gap_") for e in self._gap_entries) or
                any(e.id.startswith("gap_") for e in self._knowledge + self._procedural)):
            raise ValueError("invalid bank identities")
        if any(key in self._retired_ids for key in ids):
            raise ValueError("retired ID is active")
        for digest, content in rows["blobs"].items():
            if not isinstance(content, str) or sha256(content) != digest:
                raise ValueError("invalid content blob")
        constructors = {"sources": SourceRecord, "visibility": VisibleSource,
                        "manifests": RequestManifest, "revisions": Revision,
                        "receipts": Receipt, "tombstones": Tombstone}
        for name, constructor in constructors.items():
            for key, row in rows[name].items():
                identity = {"sources": "source_id", "visibility": "visibility_ref",
                            "manifests": "cycle_id"}.get(name, name[:-1] + "_id")
                if not isinstance(row, constructor) or getattr(row, identity) != key:
                    raise ValueError("invalid historical record identity")
        successors = {}
        for row in rows["revisions"].values():
            if row.previous_revision_id is not None:
                parent = self.revisions.get(row.previous_revision_id)
                if (parent is None or parent.memory_id != row.memory_id
                        or parent.category != row.category
                        or row.previous_revision_id in successors):
                    raise ValueError("invalid revision predecessor")
                successors[row.previous_revision_id] = row.revision_id
        for key, revision_id in self.active_revisions.items():
            if revision_id in successors:
                raise ValueError("active revision is not latest")
            kind, content = self._content(key)
            row = self.revisions[revision_id]
            if (row.memory_id, row.category, row.content_sha256) != (key, kind, sha256(content)):
                raise ValueError("active revision mismatch")
        for row in rows["revisions"].values():
            if (not isinstance(row.memory_id, str) or not row.memory_id or
                    (row.proposal_sha256 is not None and (not isinstance(row.proposal_sha256, str)
                     or len(row.proposal_sha256) != 64 or any(c not in "0123456789abcdef" for c in row.proposal_sha256)))):
                raise ValueError("invalid revision metadata")
            if row.memory_id not in self._reserved_ids:
                raise ValueError("unreserved historical memory ID")
            if row.category not in {"knowledge", "procedural", "status", "gap"} or row.content_sha256 not in self.blobs:
                raise ValueError("invalid revision")
            if type(row.entry_snapshot) is not tuple or any(type(item) is not tuple for item in row.entry_snapshot):
                raise ValueError("mutable revision snapshot")
            if row.entry_snapshot:
                snapshot = dict(row.entry_snapshot)
                if (len(snapshot) != len(row.entry_snapshot) or set(snapshot) != {"id", "content_sha256", "created_at", "access_count", "last_accessed"}
                        or snapshot["id"] != row.memory_id or snapshot["content_sha256"] != row.content_sha256
                        or not isinstance(snapshot["created_at"], str)
                        or type(snapshot["access_count"]) is not int or snapshot["access_count"] < 0
                        or (snapshot["last_accessed"] is not None and not isinstance(snapshot["last_accessed"], str))):
                    raise ValueError("invalid revision snapshot")
            if row.receipt_id is not None and self.receipts[row.receipt_id].target_revision_id != row.revision_id:
                raise ValueError("invalid revision receipt")
        for row in rows["sources"].values():
            snapshot = self._snapshot(row.source_id)
            if not _snapshot_valid(snapshot):
                raise ValueError("invalid retained source")
            if row.source_kind == "memory" and self.revisions[row.parent_revision_id].content_sha256 != row.text_sha256:
                raise ValueError("invalid retained memory source")
        for ref, visible in rows["visibility"].items():
            row = visible.snapshot.record
            spans = visible.visible_spans
            if (type(spans) is not tuple or any(type(span) is not tuple for span in spans)
                    or visible.snapshot != self._snapshot(row.source_id)):
                raise ValueError("mutable or noncanonical visibility")
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
        for manifest in rows["manifests"].values():
            if any(type(getattr(manifest, field)) is not tuple for field in
                   ("ordered_source_refs", "visible_spans", "visibility_refs", "pre_cycle_revision_refs")):
                raise ValueError("mutable manifest")
            if (not isinstance(manifest.cycle_id, str) or not manifest.cycle_id or
                    not isinstance(manifest.request_sha256, str) or len(manifest.request_sha256) != 64 or
                    any(c not in "0123456789abcdef" for c in manifest.request_sha256) or
                    len(manifest.ordered_source_refs) != len(manifest.visible_spans) or
                    any(key not in self.revisions for key in manifest.pre_cycle_revision_refs)):
                raise ValueError("invalid request manifest")
            combined = {}
            for source, spans in zip(manifest.ordered_source_refs, manifest.visible_spans):
                if (not isinstance(source, str) or not source or type(spans) is not tuple or not spans
                        or any(type(span) is not tuple or len(span) != 2 or
                               any(type(i) is not int for i in span) or not 0 <= span[0] < span[1]
                               for span in spans)):
                    raise ValueError("invalid manifest spans")
                combined[source] = combined.get(source, ()) + spans
            if len(manifest.ordered_source_refs) != len(manifest.visibility_refs):
                raise ValueError("invalid manifest visibility count")
            expected_refs = {source: sha256(_key(manifest.cycle_id, manifest.request_sha256,
                                                source, spans)) for source, spans in combined.items()}
            for source, ref in zip(manifest.ordered_source_refs, manifest.visibility_refs):
                if ref != expected_refs[source]:
                    raise ValueError("invalid per-block visibility reference")
                visible = self.visibility.get(ref)
                if visible is not None and (visible.snapshot.record.source_id != source or
                        visible.visible_spans != combined[source] or visible.cycle_id != manifest.cycle_id):
                    raise ValueError("manifest visibility pairing mismatch")
        for row in rows["receipts"].values():
            if type(row.bound_refs) is not tuple:
                raise ValueError("mutable receipt")
            revision = self.revisions[row.target_revision_id]
            manifest = self.manifests[row.cycle_id]
            if (row.action != "save_" + revision.category or type(row.op_index) is not int
                    or row.op_index < 0 or not isinstance(row.run_id, str)):
                raise ValueError("invalid receipt operation")
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
        for row in rows["tombstones"].values():
            if type(row.op_index) is not int or row.op_index < 0 or not isinstance(row.cycle_id, str):
                raise ValueError("invalid tombstone operation")
            if row.memory_id not in self._retired_ids or self.revisions[row.revision_id].memory_id != row.memory_id:
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
            memory._reserved_ids = History(rows=((e.id, True) for e in memory._knowledge + memory._procedural + memory._gap_entries))
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
                    if name == "revisions" and "entry_snapshot" in value:
                        value["entry_snapshot"] = tuple(tuple(item) for item in value["entry_snapshot"])
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
            memory._reserved_ids = History(rows=dict.fromkeys(
                [e.id for e in memory._knowledge + memory._procedural + memory._gap_entries] +
                [r.memory_id for r in memory.revisions.values()], True).items())
            memory._retired_ids = History(rows=dict.fromkeys(
                (r.memory_id for r in memory.tombstones.values()), True).items())
            memory.validate_bank()
        except (KeyError, TypeError, AttributeError, RecursionError) as exc:
            raise ValueError("malformed evidence bank") from exc
        return memory

    # Reuse the established temporary-file/flush/fsync/replace checkpoint writer.
    save_to_file = SourceMemory.save_to_file
