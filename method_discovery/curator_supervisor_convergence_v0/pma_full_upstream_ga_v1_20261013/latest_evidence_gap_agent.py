"""Latest-content revisions with graded source alignment, not semantic proof."""
import json
import re

from aligned_evidence_gap_agent import AlignedEvidenceGapMemoryAgent
from evidence_gap_agent import EvidenceGapMemoryAgent, GAP_REVISION_REPLACEMENTS, WRITERS
from gap_evidence import BoundRef, SourceScopeError, cached_source_validation
from gap_evidence_alignment import EvidenceAlignment, _validate_catalog
from graded_evidence_alignment import align_graded_evidence
from gap_prompts import MAINTENANCE
from latest_evidence_gap_store import LatestEvidenceGapMemory
from memory_agent.memory.memory_agent import MemoryOperation, PHASE1_SYSTEM


LATEST_EVIDENCE_RULES = """
Write content normally; evidence is optional: [{"quote": "visible text"}].
An optional source hint does not restrict the host's visible-source search.
For XML tools encode evidence as a JSON array. Supply content and optional quotes,
not hashes, offsets, revision IDs, alignment scores or other host metadata.
To revise an entry, use its displayed stable memory_id with the same-category
save tool. Every valid save becomes the latest content regardless of binding.
Omit memory_id only for a new entry. Status updates replace the current status.
There are no pending proposals or proposal IDs. Unmentioned entries remain.
Never delete then save to express a revision. memory_delete explicitly retires
an entry; no save implicitly deletes or cleans up other entries.
Bindings are exact_unique, exact_multiple, normalized_unique, normalized_multiple,
fuzzy_candidate, unbound, or error. None proves truth or entailment. Normalized
matches are not verbatim quotes; fuzzy candidates are approximate locations, not
verified support. Multiple locations are alternatives, not corroboration.
Alignment scores describe text matching, not probabilities that content is true.
Malformed evidence records binding error while valid content is still committed;
invalid content, targets or source integrity fail the operation instead.
Reports remain reports, commands intentions, and derived memory is not a fresh
observation or semantic proof. Keep uncertainty, scope and version boundaries in
content. Each operation is independent and atomic. Use no extra review phase.
"""


def latest_phase1_system():
    system = PHASE1_SYSTEM.replace(
        "Delete entries that are superseded by newer information",
        "Revise superseded entries using their stable memory_id; delete only to retire an entry")
    maintenance = MAINTENANCE
    for old, new in GAP_REVISION_REPLACEMENTS:
        maintenance = maintenance.replace(old, new, 1)
    maintenance = maintenance.replace("replacement content, and evidence in one operation",
                                      "replacement content, and optional evidence in one operation")
    maintenance = maintenance.replace("and evidence to revise it in place",
                                      "and optional evidence to revise it in place")
    return system + maintenance + LATEST_EVIDENCE_RULES


class LatestEvidenceGapMemoryAgent(AlignedEvidenceGapMemoryAgent):
    policy = LatestEvidenceGapMemory.policy
    expected_alignment_policy = policy

    def __init__(self, *, memory, **kwargs):
        if not isinstance(memory, LatestEvidenceGapMemory):
            raise TypeError("latest adapter requires LatestEvidenceGapMemory")
        super().__init__(memory=memory, **kwargs)

    def _pending_view(self):
        return ""

    async def _call_llm_phase1(self, user_prompt):
        self.transport_phase = "maintenance"
        kwargs = {"prompt": user_prompt, "system": latest_phase1_system()}
        if self.use_structured_tools:
            kwargs["tools"] = self.get_tools_schema()
        try:
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self.last_gap_report["transport_errors"].append(
                {"phase": "maintenance", "type": type(exc).__name__})
            raise

    def _binding_text(self, key, *, include_quotes=True):
        row = self.memory.binding(key)
        if row is None:
            return "legacy memory; binding not recorded; not semantic proof"
        text = (f"content_status=committed; binding_status={row.status}; "
                f"disposition={row.disposition}; source alignment, NOT semantic proof")
        if row.reason:
            text += "; reason=" + row.reason
        for index, item in enumerate(json.loads(row.alignment_json)["items"], 1):
            text += f"\nEvidence {index}: binding_status={item['status']}"
            candidates = item["candidates"]
            text += f"; candidate count={len(candidates)} (alternatives, not corroboration)"
            if not include_quotes:
                continue
            text += "; model-supplied quote=" + json.dumps(item["quote"], ensure_ascii=False)
            if item["source_hint"] is not None:
                text += "; supplied source hint=" + json.dumps(item["source_hint"], ensure_ascii=False)
            # All candidates/metadata remain in storage. Bound the displayed view,
            # and obtain source text from the retained visibility, never the quote.
            for raw_ref in candidates[:3]:
                ref = BoundRef(**raw_ref)
                visible = self.memory.visibility[ref.visibility_ref]
                source = visible.snapshot.record
                excerpt = visible.snapshot.blob.text[ref.start:ref.end]
                if source.source_kind == "memory":
                    parent = self.memory.revisions[source.parent_revision_id]
                    role = f"derived memory [{parent.memory_id}], not independent observation"
                else:
                    role = f"{source.role}, event order {source.order}, field {source.field_path}"
                text += (f"; {role}, span [{ref.start},{ref.end}); actual source excerpt="
                         + json.dumps(excerpt, ensure_ascii=False))
            if len(candidates) > 3:
                text += "; additional candidate locations retained, not displayed"
            metadata = item.get("metadata", {})
            summary = {key: value for key, value in metadata.items() if key != "candidate_details"}
            details = metadata.get("candidate_details", [])
            if details:
                summary["representative_match"] = details[0]
                summary["retained_candidate_details"] = len(details)
            if summary:
                text += "; matching metadata (NOT truth probabilities)=" + json.dumps(summary, ensure_ascii=False)
            if not candidates:
                text += "; no visible source match"
        return text

    def _parse_item(self, item):
        try:
            return super()._parse_item(item)
        except json.JSONDecodeError:
            if item[0] != "xml":
                raise
            # The inherited parser has already checked the complete XML shape.
            # An invalid evidence JSON value is evidence failure, not content
            # failure. Reuse its parser with a null sentinel for that field only.
            repaired = re.sub(r"(<parameter=evidence>).*?(</parameter>)",
                              r"\g<1>null\g<2>", item[1], count=1, flags=re.DOTALL)
            return super()._parse_item(("xml", repaired))

    def _apply_operation(self, draft, name, args, index):
        if not isinstance(args, dict):
            raise ValueError("tool arguments must be an object")
        if name == "memory_delete":
            return super()._apply_operation(draft, name, args, index)
        if name not in WRITERS:
            raise ValueError("unknown memory operation")
        kind = WRITERS[name]
        allowed = {"content", "evidence"}
        if kind != "status":
            allowed.add("memory_id")
        content, target = args.get("content"), args.get("memory_id")
        if (not set(args) <= allowed or not isinstance(content, str) or not content.strip()
                or ("memory_id" in args and (not isinstance(target, str) or not target))):
            raise ValueError("write requires nonempty content and valid arguments")
        # Target validity precedes evidence handling; malformed evidence cannot
        # turn an invalid update into a new entry or mask a category mismatch.
        if target is not None:
            if draft._content(target)[0] != kind:
                raise ValueError("update target must be an existing same-category memory ID")
        try:
            alignment = align_graded_evidence(args.get("evidence", []), self._parts.catalog)
        except SourceScopeError as exc:
            if str(exc) not in {"invalid_evidence", "invalid_evidence_item"}:
                raise
            # Invalid evidence must not hide corrupt internal source state.
            _validate_catalog(self._parts.catalog)
            alignment = EvidenceAlignment("error", str(exc), (), ())
        key, revision_id, disposition = draft.apply_aligned_write(
            kind, content, alignment, cycle_id=self._parts.manifest.cycle_id,
            op_index=index, memory_id=target)
        operation = MemoryOperation("update_status" if kind == "status" else "save_" + kind, key, content)
        operation.content_status = "committed"
        operation.binding_status = alignment.status
        operation.binding_disposition = disposition
        operation.binding_error = alignment.reason if alignment.status == "error" else None
        operation.revision_id = revision_id
        return operation

    @cached_source_validation
    def _execute_tool_calls(self, response):
        # Reuse the original parse/validate/per-operation atomic publish loop,
        # bypassing only the old pending-proposal outcome vocabulary.
        operations = EvidenceGapMemoryAgent._execute_tool_calls(self, response)
        self.last_evidence_report["binding_policy"] = self.policy
        for outcome, operation in zip(self.last_evidence_report["operations"], operations):
            outcome["content_status"] = "committed" if operation.success else "rejected"
            if operation.success and hasattr(operation, "binding_status"):
                outcome.update(binding_status=operation.binding_status,
                    binding_disposition=operation.binding_disposition,
                    binding_error=operation.binding_error, revision_id=operation.revision_id)
        return operations
