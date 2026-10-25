"""Latest content revisions with independent, graded citation metadata.

This is a new policy, not a migration of the archived pending-proposal policy.
Revision predecessors record edit history only; citation parents are explicit.
"""
from collections import ChainMap
from dataclasses import asdict, dataclass, replace
import json

from aligned_evidence_gap_store import AlignedEvidenceGapMemory, AlignmentRecord
from evidence_gap_store import EvidenceGapMemory, History
from gap_evidence import BoundRef, bound_ref_valid, cached_source_validation
from gap_evidence_alignment import _validate_catalog


@dataclass(frozen=True)
class LatestAlignmentRecord(AlignmentRecord):
    provenance_summary: str = "none"
    candidate_provenance_json: str = "[]"


class LatestEvidenceGapMemory(AlignedEvidenceGapMemory):
    policy = "latest_revision_with_graded_alignment_v1"
    _GRADES = {"exact_unique", "exact_multiple", "normalized_unique",
               "normalized_multiple", "fuzzy_candidate", "unbound", "error"}

    def _provenance(self, refs):
        rows = []
        for ref in refs:
            parent = ref.parent_revision_id
            rows.append({"ref": asdict(ref),
                         "origin": "derived" if parent else "raw",
                         "parent_disposition": ("unbound" if self._parent_unbound(parent)
                                                 else "bound") if parent else None})
        origins = {row["origin"] for row in rows}
        summary = "mixed" if len(origins) > 1 else next(iter(origins), "none")
        return summary, json.dumps(rows, sort_keys=True, separators=(",", ":"))

    def _disposition(self, value):
        # Alternative candidates are not independent proof and a contaminated
        # alternative cannot erase a clean original location for the same quote.
        clean = lambda ref: not ref.parent_revision_id or not self._parent_unbound(ref.parent_revision_id)
        if not value["items"]:
            return "unbound"
        for item in value["items"]:
            if item["status"] not in {"exact_unique", "exact_multiple",
                                      "normalized_unique", "normalized_multiple"}:
                return "unbound"
            if not any(clean(BoundRef(**ref)) for ref in item["candidates"]):
                return "unbound"
        return "bound"

    @cached_source_validation
    def apply_aligned_write(self, kind, content, alignment, *, cycle_id, op_index,
                            memory_id=None):
        if (kind not in {"knowledge", "procedural", "gap", "status"}
                or not isinstance(content, str) or not content.strip()
                or type(op_index) is not int or op_index < 0):
            raise ValueError("invalid aligned write")
        if memory_id is not None and (not isinstance(memory_id, str) or not memory_id
                or kind == "status" or self._content(memory_id)[0] != kind):
            raise ValueError("update target must be an existing same-category memory ID")
        if self.pending_proposals:
            raise ValueError("legacy pending proposals require explicit migration")
        manifest = self.manifests.get(cycle_id)
        if manifest is None:
            raise ValueError("write references another request")
        pending = getattr(self, "_pending_visibility", {})
        if any(key != visible.visibility_ref or visible.cycle_id != cycle_id
               or key not in manifest.visibility_refs for key, visible in pending.items()):
            raise ValueError("invalid request visibility")
        _validate_catalog({v.snapshot.record.handle: v for v in pending.values()})
        value = asdict(alignment)
        resolver = ChainMap(pending, self.visibility)
        self._validate_value(value, cycle_id, resolver)
        refs = tuple(BoundRef(**ref) for ref in value["bound_refs"])
        disposition = self._disposition(value)
        for ref in refs:
            visible = resolver[ref.visibility_ref]
            self._retain_source(visible.snapshot)
            self.visibility = self.visibility.add(ref.visibility_ref, visible)
        if disposition == "bound":
            key, revision_id = EvidenceGapMemory.apply_bound_write(self, kind, content, refs,
                cycle_id=cycle_id, op_index=op_index, memory_id=memory_id)
        else:
            key = "status" if kind == "status" else memory_id
            previous = self.active_revisions.get(key)
            if key is not None and previous is None and (key != "status" or self.status):
                previous = self._revision(key).revision_id
            if kind == "status":
                self.update_status(content)
            elif key is None:
                key = getattr(self, "save_" + kind)(content)
            else:
                entries = getattr(self, {"gap": "_gap_entries"}.get(kind, "_" + kind))
                index = next(i for i, entry in enumerate(entries) if entry.id == key)
                entries[index] = replace(entries[index], content=content)
                self._invalidate_indices(kind)
                self._generation += 1
            revision_id = self._revision(key, proposal=content,
                                         previous_revision_id=previous).revision_id
        summary, provenance = self._provenance(refs)
        record = LatestAlignmentRecord(revision_id, value["status"], disposition,
            value["reason"], json.dumps(value, sort_keys=True, separators=(",", ":")),
            cycle_id, provenance_summary=summary, candidate_provenance_json=provenance)
        self.alignments = self.alignments.add(revision_id, record)
        return key, revision_id, disposition

    def _validate_value(self, value, cycle_id, resolver):
        if (not isinstance(value, dict) or set(value) != {"status", "reason", "items", "bound_refs"}
                or value["status"] not in self._GRADES
                or (value["reason"] is not None and not isinstance(value["reason"], str))):
            raise ValueError("invalid alignment metadata")
        if value["status"] == "error":
            if value["reason"] not in {"invalid_evidence", "invalid_evidence_item"} or value["items"] or value["bound_refs"]:
                raise ValueError("invalid binding error")
            return
        manifest = self.manifests[cycle_id]
        refs = tuple(BoundRef(**ref) for ref in value["bound_refs"])
        candidates, statuses = [], []
        for item in value["items"]:
            if (not isinstance(item, dict) or not {"quote", "source_hint", "status", "reason", "candidates"} <= set(item)
                    or set(item) - {"quote", "source_hint", "status", "reason", "candidates", "metadata"}
                    or not isinstance(item["quote"], str)
                    or (item["source_hint"] is not None and
                        (not isinstance(item["source_hint"], str) or not item["source_hint"]))
                    or (item["reason"] is not None and not isinstance(item["reason"], str))):
                raise ValueError("invalid quote alignment")
            matched = tuple(BoundRef(**ref) for ref in item["candidates"])
            grade = item["status"]
            if (grade not in self._GRADES - {"error"}
                    or len(set(matched)) != len(matched)
                    or (grade.endswith("_unique") and len(matched) != 1)
                    or (grade.endswith("_multiple") and len(matched) < 2)
                    or (grade == "unbound" and matched)
                    or (grade == "fuzzy_candidate" and not matched)):
                raise ValueError("invalid quote alignment cardinality")
            from graded_evidence_alignment import quote_metadata_valid
            if not quote_metadata_valid(item, resolver):
                raise ValueError("invalid quote alignment metadata")
            statuses.append(grade)
            for ref in matched:
                if not bound_ref_valid(ref, resolver) or ref.visibility_ref not in manifest.visibility_refs:
                    raise ValueError("invalid alignment candidate")
                if ref.parent_revision_id:
                    parent = self.revisions[ref.parent_revision_id]
                    parent_alignment = self.alignments.get(parent.revision_id)
                    if (parent.revision_id not in manifest.pre_cycle_revision_refs or
                            (parent_alignment is not None and parent_alignment.cycle_id == cycle_id) or
                            (parent.receipt_id is not None and self.receipts[parent.receipt_id].cycle_id == cycle_id)):
                        raise ValueError("non-pre-cycle alignment parent")
                self._validate_candidate(item, ref, resolver)
            candidates.extend(matched)
        expected = self._aggregate(statuses)
        if value["status"] != expected or tuple(dict.fromkeys(candidates)) != refs:
            raise ValueError("invalid aggregate alignment")

    @staticmethod
    def _aggregate(statuses):
        if not statuses or "unbound" in statuses:
            return "unbound"
        for grade in ("fuzzy_candidate", "normalized_multiple", "normalized_unique", "exact_multiple"):
            if grade in statuses:
                return grade
        return "exact_unique"

    @staticmethod
    def _validate_candidate(item, ref, resolver):
        from graded_evidence_alignment import candidate_grade_valid
        text = resolver[ref.visibility_ref].snapshot.blob.text[ref.start:ref.end]
        if not candidate_grade_valid(item["quote"], text, item["status"]):
            raise ValueError("invalid candidate alignment grade")

    def _validate_alignment(self, rows, revisions=None):
        if self.pending_proposals:
            raise ValueError("latest policy has no active pending proposals")
        for revision in (self.revisions if revisions is None else revisions).values():
            if (revision.proposal_sha256 is not None and revision.revision_id not in self.alignments):
                raise ValueError("missing revision alignment metadata")
            if revision.memory_id.startswith("proposal_"):
                raise ValueError("legacy proposal history requires explicit migration")
        for key, row in rows.items():
            if (not isinstance(row, LatestAlignmentRecord) or key != row.revision_id
                    or key not in self.revisions or row.target_id is not None
                    or row.target_revision_id is not None or row.cycle_id not in self.manifests):
                raise ValueError("invalid latest alignment identity")
            value = json.loads(row.alignment_json)
            self._validate_value(value, row.cycle_id, self.visibility)
            refs = tuple(BoundRef(**ref) for ref in value["bound_refs"])
            revision = self.revisions[key]
            if (row.status != value["status"] or row.reason != value["reason"]
                    or row.disposition != self._disposition(value)
                    or (row.disposition == "bound") != (revision.receipt_id is not None)
                    or (row.provenance_summary, row.candidate_provenance_json) != self._provenance(refs)):
                raise ValueError("alignment revision metadata mismatch")
            if revision.receipt_id is not None and self.receipts[revision.receipt_id].bound_refs != refs:
                raise ValueError("alignment receipt references differ")

    def to_dict(self):
        data = EvidenceGapMemory.to_dict(self)
        data["gap_alignment_policy"] = self.policy
        data["gap_alignment"] = {"schema": 2, "policy": self.policy,
            "alignments": {key: asdict(row) for key, row in self.alignments.items()}}
        return data

    @classmethod
    @cached_source_validation
    def from_dict(cls, data):
        # The upstream constructor supplies a pristine UniversalMemory bank,
        # not an archive. Accept only its exact empty serialization shape.
        if (isinstance(data, dict) and set(data) == {"status", "knowledge", "procedural"}
                and data["status"] == "" and data["knowledge"] == [] and data["procedural"] == []):
            base = EvidenceGapMemory.from_dict(data)
            if (base.status or base._knowledge or base._procedural or base._gap_entries
                    or base.active_revisions or any(getattr(base, name) for name in base._HISTORIES)):
                raise ValueError("only a pristine upstream bank can initialize latest policy")
            return cls(max_status_length=base._max_status_length)
        extra = data.get("gap_alignment")
        if (data.get("gap_alignment_policy") != cls.policy or not isinstance(extra, dict)
                or "gap_evidence" not in data
                or set(extra) != {"schema", "policy", "alignments"}
                or type(extra["schema"]) is not int or extra["schema"] != 2
                or extra["policy"] != cls.policy):
            raise ValueError("latest policy requires schema 2; load archives with their original policy")
        try:
            # Do not skip source/hash/manifest/history validation during loading.
            base = EvidenceGapMemory.from_dict(data)
            base.__class__ = cls
            base.pending_proposals = {}
            base.alignments = History(rows=((key, LatestAlignmentRecord(**row))
                                            for key, row in extra["alignments"].items()))
            base.validate_bank()
            return base
        except (KeyError, TypeError, AttributeError, RecursionError) as exc:
            raise ValueError("malformed latest alignment bank") from exc
