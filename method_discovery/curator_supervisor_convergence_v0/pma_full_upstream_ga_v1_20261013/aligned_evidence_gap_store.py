"""Literal alignment policy over the strict immutable evidence storage primitives.

Unbound new entries share the ordinary bank. Protected replacements live in one
pending slot per target, using the same immutable revisions, blobs and tombstones.
"""
from collections import ChainMap
from dataclasses import asdict, dataclass, replace
import json
import uuid

from evidence_gap_store import EvidenceGapMemory, History, Revision, Tombstone
from gap_evidence import BoundRef, bound_ref_valid, sha256, cached_source_validation


@dataclass(frozen=True)
class AlignmentRecord:
    revision_id: str
    status: str
    disposition: str
    reason: str
    alignment_json: str
    cycle_id: str
    target_id: str | None = None
    target_revision_id: str | None = None


@dataclass(frozen=True)
class PendingProposal:
    id: str
    target_id: str
    category: str
    content: str


class AlignedEvidenceGapMemory(EvidenceGapMemory):
    policy = "literal_alignment_with_explicit_unbound_v1"

    def __init__(self, max_status_length=2000):
        super().__init__(max_status_length)
        self.alignments = History()
        self.pending_proposals = {}

    def fork_write_draft(self):
        draft = super().fork_write_draft()
        draft.pending_proposals = self.pending_proposals.copy()
        return draft

    def _content(self, key):
        if key in self.pending_proposals:
            row = self.pending_proposals[key]
            return row.category, row.content
        return super()._content(key)

    def _id_in_use(self, key):
        return key in self.pending_proposals or super()._id_in_use(key)

    def _revision(self, key, receipt_id=None, proposal=None, previous_revision_id=None):
        if key not in self.pending_proposals:
            return super()._revision(key, receipt_id, proposal, previous_revision_id)
        kind, content = self._content(key)
        self._reserved_ids = self._reserved_ids.add(key, True)
        digest = sha256(content)
        self.blobs = self.blobs.add(digest, content)
        row = Revision("rev_" + uuid.uuid4().hex, key, kind, digest, receipt_id,
                       sha256(proposal) if proposal is not None else None,
                       (), previous_revision_id)
        self.revisions = self.revisions.add(row.revision_id, row)
        self.active_revisions[key] = row.revision_id
        return row

    def binding(self, key):
        return self.alignments.get(self.active_revisions.get(key))

    def _parent_unbound(self, revision_id):
        row = self.alignments.get(revision_id)
        return (row.disposition == "unbound" if row is not None
                else self.revisions[revision_id].receipt_id is None)

    def _is_unbound(self, key):
        row = self.binding(key)
        return row is not None and row.disposition == "unbound"

    def _close_pending(self, target, cycle_id, op_index):
        for key, row in list(self.pending_proposals.items()):
            if row.target_id == target:
                self.delete_bound(key, cycle_id=cycle_id, op_index=op_index)

    def delete_bound(self, memory_id, *, cycle_id="", op_index=0):
        if memory_id not in self.pending_proposals:
            result = super().delete_bound(memory_id, cycle_id=cycle_id, op_index=op_index)
            self._close_pending(memory_id, cycle_id, op_index)
            return result
        revision = self.active_revisions.pop(memory_id)
        self.pending_proposals.pop(memory_id)
        row = Tombstone("tomb_" + uuid.uuid4().hex, memory_id, revision, cycle_id, op_index)
        self.tombstones = self.tombstones.add(row.tombstone_id, row)
        self._retired_ids = self._retired_ids.add(memory_id, True)
        self._generation += 1
        return True

    def clear(self, keep_status=False):
        for key in list(self.pending_proposals):
            if not keep_status or self.pending_proposals[key].target_id != "status":
                self.delete_bound(key)
        super().clear(keep_status=keep_status)

    @cached_source_validation
    def apply_aligned_write(self, kind, content, alignment, *, cycle_id, op_index,
                            memory_id=None):
        if kind not in {"knowledge", "procedural", "gap", "status"} or not isinstance(content, str) or not content.strip():
            raise ValueError("invalid aligned write")
        # A supplied target is validated before any evidence fallback.
        if memory_id is not None and (not isinstance(memory_id, str) or not memory_id or
                kind == "status" or self._content(memory_id)[0] != kind):
            raise ValueError("update target must be an existing same-category memory ID")
        target = memory_id
        if target in self.pending_proposals:
            target = self.pending_proposals[target].target_id
        if kind == "status":
            target = "status"
        target_revision_id = self.active_revisions.get(target) if target is not None else None
        if target is not None and target_revision_id is None and (target != "status" or self.status):
            target_revision_id = self._revision(target).revision_id
        manifest = self.manifests.get(cycle_id)
        if manifest is None:
            raise ValueError("write references another request")
        resolver = ChainMap(getattr(self, "_pending_visibility", {}), self.visibility)
        for ref in alignment.bound_refs:
            if not bound_ref_valid(ref, resolver) or ref.visibility_ref not in manifest.visibility_refs:
                raise ValueError("invalid aligned reference")
            visible = resolver[ref.visibility_ref]
            self._retain_source(visible.snapshot)
            self.visibility = self.visibility.add(ref.visibility_ref, visible)
        inherited_unbound = any(self._parent_unbound(ref.parent_revision_id)
            for ref in alignment.bound_refs if ref.parent_revision_id)
        disposition = "unbound" if alignment.status == "unbound" or inherited_unbound else "bound"
        reason = "derived_from_unbound_memory" if inherited_unbound else alignment.reason
        if disposition == "bound":
            key, revision_id = super().apply_bound_write(kind, content, alignment.bound_refs,
                cycle_id=cycle_id, op_index=op_index,
                memory_id=target if kind != "status" else None)
            if target is not None:
                self._close_pending(target, cycle_id, op_index)
        elif target is not None and (target == "status" or not self._is_unbound(target)):
            # At most one live alternative per protected target. Supersession is
            # a revision of that same proposal ID, not another accumulating row.
            existing = next((p for p in self.pending_proposals.values() if p.target_id == target), None)
            key = existing.id if existing else "proposal_" + uuid.uuid4().hex
            previous = self.active_revisions.get(key)
            self.pending_proposals[key] = PendingProposal(key, target, kind, content)
            revision_id = self._revision(key, proposal=content, previous_revision_id=previous).revision_id
            self._generation += 1
        else:
            if target is None:
                key = getattr(self, "save_" + kind)(content)
                previous = None
            else:
                key = target
                previous = self.active_revisions.get(key)
                entries = getattr(self, {"gap": "_gap_entries"}.get(kind, "_" + kind))
                index = next(i for i, entry in enumerate(entries) if entry.id == key)
                entries[index] = replace(entries[index], content=content)
                self._invalidate_indices(kind)
                self._generation += 1
            revision_id = self._revision(key, proposal=content, previous_revision_id=previous).revision_id
        record = AlignmentRecord(revision_id, alignment.status, disposition, reason,
            json.dumps(asdict(alignment), sort_keys=True, separators=(",", ":")), cycle_id,
            target if key in self.pending_proposals else None,
            target_revision_id if key in self.pending_proposals else None)
        self.alignments = self.alignments.add(revision_id, record)
        return key, revision_id, disposition

    def _validate_alignment(self, rows, revisions=None):
        for revision in (self.revisions if revisions is None else revisions).values():
            if revision.receipt_id is None and revision.proposal_sha256 is not None and revision.revision_id not in self.alignments:
                raise ValueError("missing unbound alignment metadata")
        for key, row in rows.items():
            if not isinstance(row, AlignmentRecord) or key != row.revision_id or key not in self.revisions:
                raise ValueError("invalid alignment identity")
            if row.status not in {"exact_unique", "exact_multiple", "unbound"} or row.disposition not in {"bound", "unbound"}:
                raise ValueError("invalid alignment disposition")
            revision = self.revisions[key]
            if row.target_id is not None:
                if not revision.memory_id.startswith("proposal_") or row.disposition != "unbound":
                    raise ValueError("invalid historical proposal target")
                if row.target_revision_id is None:
                    if row.target_id != "status":
                        raise ValueError("missing proposal target revision")
                else:
                    target_revision = self.revisions[row.target_revision_id]
                    if target_revision.memory_id != row.target_id or target_revision.category != revision.category:
                        raise ValueError("invalid historical target revision")
            elif revision.memory_id.startswith("proposal_") or row.target_revision_id is not None:
                raise ValueError("missing historical proposal target")
            if (row.disposition == "bound") != (revision.receipt_id is not None):
                raise ValueError("alignment receipt mismatch")
            if row.cycle_id not in self.manifests:
                raise ValueError("alignment missing request manifest")
            value = json.loads(row.alignment_json)
            if set(value) != {"status", "reason", "items", "bound_refs"} or value["status"] != row.status:
                raise ValueError("invalid alignment metadata")
            refs = tuple(BoundRef(**ref) for ref in value["bound_refs"])
            candidates = []
            statuses = []
            for item in value["items"]:
                if set(item) != {"quote", "source_hint", "status", "reason", "candidates"} or not isinstance(item["quote"], str):
                    raise ValueError("invalid quote alignment")
                if item["source_hint"] is not None and (not isinstance(item["source_hint"], str) or not item["source_hint"]):
                    raise ValueError("invalid source hint")
                matched = tuple(BoundRef(**ref) for ref in item["candidates"])
                expected = "exact_unique" if len(matched) == 1 else "exact_multiple" if matched else "unbound"
                if item["status"] != expected or len(set(matched)) != len(matched):
                    raise ValueError("invalid quote alignment cardinality")
                statuses.append(expected)
                for ref in matched:
                    if (not bound_ref_valid(ref, self.visibility) or
                            ref.visibility_ref not in self.manifests[row.cycle_id].visibility_refs or
                            self.blobs[ref.source_text_sha256][ref.start:ref.end] != item["quote"]):
                        raise ValueError("invalid alignment candidate")
                    if ref.parent_revision_id is not None:
                        parent = self.revisions[ref.parent_revision_id]
                        manifest = self.manifests[row.cycle_id]
                        parent_alignment = self.alignments.get(ref.parent_revision_id)
                        if (ref.parent_revision_id not in manifest.pre_cycle_revision_refs or
                                (parent_alignment is not None and parent_alignment.cycle_id == row.cycle_id) or
                                (parent.receipt_id is not None and self.receipts[parent.receipt_id].cycle_id == row.cycle_id)):
                            raise ValueError("non-pre-cycle alignment parent")
                candidates.extend(matched)
            expected = "unbound" if not statuses or "unbound" in statuses else "exact_multiple" if "exact_multiple" in statuses else "exact_unique"
            if value["status"] != expected or tuple(dict.fromkeys(candidates)) != refs:
                raise ValueError("invalid aggregate alignment")
            inherited = any(self._parent_unbound(ref.parent_revision_id) for ref in refs if ref.parent_revision_id)
            if row.disposition != ("unbound" if expected == "unbound" or inherited else "bound"):
                raise ValueError("unbound lineage was promoted")
            if revision.receipt_id is not None and self.receipts[revision.receipt_id].bound_refs != refs:
                raise ValueError("alignment receipt references differ")
        native_ids = {e.id for e in self._knowledge + self._procedural + self._gap_entries}
        if native_ids.intersection(self.pending_proposals):
            raise ValueError("pending identity shadows native entry")
        targets = set()
        for key, row in self.pending_proposals.items():
            if (not isinstance(row, PendingProposal) or row.id != key or not key.startswith("proposal_")
                    or key in self._retired_ids or row.target_id in targets or row.target_id in self.pending_proposals
                    or key not in self.active_revisions or not self._is_unbound(key)):
                raise ValueError("invalid pending proposal")
            if row.target_id != "status" and self._content(row.target_id)[0] != row.category:
                raise ValueError("invalid pending target")
            if row.target_id == "status" and row.category != "status":
                raise ValueError("invalid status proposal")
            alignment = self.binding(key)
            if alignment.target_id != row.target_id:
                raise ValueError("pending target history mismatch")
            targets.add(row.target_id)

    @cached_source_validation
    def validate_draft(self, base):
        super().validate_draft(base)
        self._validate_alignment(dict(self.alignments.delta(base.alignments)),
                                 dict(self.revisions.delta(base.revisions)))
        removed = set(base.pending_proposals) - set(self.pending_proposals)
        tombstoned = {r.memory_id for _, r in self.tombstones.delta(base.tombstones)}
        if not removed <= tombstoned:
            raise ValueError("untracked pending removal")

    @cached_source_validation
    def validate_bank(self):
        super().validate_bank()
        self._validate_alignment(self.alignments)
        # Unbound refs have no Receipt: include their ancestry explicitly.
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
                    raise ValueError("cyclic alignment ancestry")
                if key in done:
                    continue
                visiting.add(key)
                stack.append((key, True))
                revision = self.revisions[key]
                if revision.previous_revision_id:
                    stack.append((revision.previous_revision_id, False))
                alignment = self.alignments.get(key)
                if alignment:
                    refs = json.loads(alignment.alignment_json)["bound_refs"]
                    stack.extend((ref["parent_revision_id"], False) for ref in refs if ref["parent_revision_id"])
                elif revision.receipt_id:
                    stack.extend((ref.parent_revision_id, False) for ref in self.receipts[revision.receipt_id].bound_refs if ref.parent_revision_id)

    def to_dict(self):
        data = super().to_dict()
        data["gap_alignment_policy"] = self.policy
        data["gap_alignment"] = {"schema": 1, "policy": self.policy,
            "alignments": {key: asdict(row) for key, row in self.alignments.items()},
            "pending_proposals": {key: asdict(row) for key, row in self.pending_proposals.items()}}
        return data

    @classmethod
    @cached_source_validation
    def from_dict(cls, data):
        # Strict loader still validates every retained source/receipt/revision.
        # Pending IDs are temporarily omitted from its ordinary-bank active map.
        extra = data.get("gap_alignment")
        if "gap_alignment" not in data:
            if "gap_alignment_policy" in data:
                raise ValueError("missing alignment schema")
            base = EvidenceGapMemory.from_dict(data)
            if any(row.memory_id.startswith("proposal_") or (row.receipt_id is None and row.proposal_sha256 is not None) for row in base.revisions.values()):
                raise ValueError("missing alignment schema for proposal history")
            base.__class__ = cls
            base.alignments, base.pending_proposals = History(), {}
            return base
        if data.get("gap_alignment_policy") != cls.policy:
            raise ValueError("missing or unknown alignment policy")
        if not isinstance(extra, dict) or set(extra) != {"schema", "policy", "alignments", "pending_proposals"} or extra["schema"] != 1 or extra["policy"] != cls.policy:
            raise ValueError("unknown alignment schema")
        try:
            pending = {key: PendingProposal(**row) for key, row in extra["pending_proposals"].items()}
            stripped = dict(data)
            evidence = dict(data["gap_evidence"])
            active = dict(evidence["active_revisions"])
            evidence["active_revisions"] = {key: value for key, value in active.items() if key not in pending}
            stripped["gap_evidence"] = evidence
            base = EvidenceGapMemory.from_dict(stripped)
            base.__class__ = cls
            base.active_revisions = active
            base.pending_proposals = pending
            base.alignments = History(rows=((key, AlignmentRecord(**row)) for key, row in extra["alignments"].items()))
            base.validate_bank()
            return base
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("malformed alignment bank") from exc
