"""Five-tool, two-phase PMA adapter with deterministic literal alignment.

The strict evidence adapter remains available unchanged. No repair/review model
call is introduced; phase 2 uses its original selection system and retrieval.
Phase 1 shows binding summaries, not historical quotation strings outside its
eligible catalog. Only current selected memory bodies and recent typed originals
are writable evidence. Phase 2 can consume labelled stored source excerpts; it
has no write tools. No historical raw-source retrieval is introduced.
"""
import json
import uuid

from aligned_evidence_gap_store import AlignedEvidenceGapMemory
from evidence_gap_agent import EvidenceGapMemoryAgent, WRITERS, GAP_REVISION_REPLACEMENTS
from gap_evidence import RenderBlock, render_source_blocks, sha256, cached_source_validation
from gap_evidence_alignment import align_evidence
from gap_prompts import MAINTENANCE
from memory_agent.memory.memory_agent import MemoryOperation, PHASE1_SYSTEM


ALIGNED_EVIDENCE_RULES = """
Write content normally. Where useful, add evidence as [{"quote": "visible text"}].
The optional source field is only a hint; the host searches all displayed sources.
For XML tools encode evidence as a JSON array. Missing/empty evidence and unmatched
quotes are retained but explicitly labelled unbound, not discarded. Exact-unique
and exact-multiple refer only to literal locations, never truth or entailment.
Multiple locations are alternative matches, not independent corroboration.
Reports remain reports, commands intentions, and derived memory is not a fresh
observation. Claims derived from unbound memory remain unbound. Keep uncertainty,
scope, source roles and version boundaries in content. Never call unbound verified.
Use the existing save tool with a displayed memory_id to revise a same-category
entry. An unbound replacement cannot overwrite a bound entry: the host keeps one
pending proposal for that target. Revise that displayed proposal ID or target ID;
use memory_delete with the proposal ID to discard it. A bound replacement resolves
its pending proposal. Status proposals use memory_update_status and can be deleted
by their proposal ID. Do not delete a bound original to force an unbound update.
Each operation is independent and atomic. Invalid targets or malformed arguments
are errors, not unbound evidence. No extra tools or review phase are used.
"""


class AlignedEvidenceGapMemoryAgent(EvidenceGapMemoryAgent):
    policy = AlignedEvidenceGapMemory.policy
    expected_alignment_policy = policy

    def __init__(self, *, memory, **kwargs):
        if not isinstance(memory, AlignedEvidenceGapMemory):
            raise TypeError("aligned adapter requires AlignedEvidenceGapMemory")
        super().__init__(memory=memory, **kwargs)
        for tool in self._tools:
            params = tool["function"]["parameters"]
            if tool["function"]["name"] in WRITERS:
                evidence = params["properties"]["evidence"]
                evidence.pop("minItems", None)
                evidence["items"]["required"] = ["quote"]
                evidence["items"]["properties"]["quote"].pop("minLength", None)
                params["required"] = ["content"]

    def _binding_text(self, key, *, include_quotes=True):
        row = self.memory.binding(key)
        if row is None:
            return "legacy memory; binding not recorded"
        text = f"literal_binding={row.status}; disposition={row.disposition}"
        if row.reason:
            text += "; reason=" + row.reason
        value = json.loads(row.alignment_json)
        for index, item in enumerate(value["items"], 1):
            text += f"\nEvidence {index}: literal_binding={item['status']}"
            if include_quotes:
                label = "stored source excerpt" if item["candidates"] else "model-attempted quote, NOT source evidence"
                text += f"; {label}=" + json.dumps(item["quote"], ensure_ascii=False)
                if item["source_hint"] is not None:
                    text += "; supplied source hint=" + json.dumps(item["source_hint"], ensure_ascii=False)
            if item["candidates"]:
                text += "; candidate locations (alternatives, not independent proof): "
                groups = {}
                for ref in item["candidates"]:
                    groups.setdefault(ref["source_id"], []).append(ref)
                descriptions = []
                for source_id, refs in groups.items():
                    source = self.memory.sources[source_id]
                    if source.source_kind == "memory":
                        memory_id = self.memory.revisions[source.parent_revision_id].memory_id
                        label = f"derived memory [{memory_id}]"
                    else:
                        label = f"{source.role}, event order {source.order}, field {source.field_path}"
                    if len(refs) == 1:
                        ref = refs[0]
                        positions = f"span [{ref['start']},{ref['end']})"
                    else:
                        ordered = sorted(refs, key=lambda ref: (ref["start"], ref["end"]))
                        first, last = ordered[0], ordered[-1]
                        positions = (f"{len(refs)} candidate spans; first=[{first['start']},{first['end']}); "
                                     f"last=[{last['start']},{last['end']}) (position summary; all candidates retained)")
                    descriptions.append(label + ", " + positions)
                text += "; ".join(descriptions)
            else:
                text += "; no visible source match"
        return text

    def _format_memory_list(self, entries):
        text = super()._format_memory_list(entries)
        if not getattr(self, "_collect_phase1", False):
            details = [f"[{entry.id}] {self._binding_text(entry.id)}" for entry in entries]
            if details:
                text += "\nBinding labels and source excerpts:\n" + "\n".join(details)
        return text

    def _pending_view(self):
        rows = []
        for key, row in self.memory.pending_proposals.items():
            rows.append(f"[{key}] PENDING UNBOUND replacement for {row.target_id} ({row.category}); original unchanged\n"
                        + row.content + "\n" + self._binding_text(key))
        return "\n\n## Pending unbound proposals\n" + ("\n".join(rows) if rows else "(none)")

    def _build_phase2_prompt(self, observation, step_count):
        prompt = super()._build_phase2_prompt(observation, step_count)
        if self.memory.status:
            prompt += "\nStatus binding: " + self._binding_text("status")
        return prompt + self._pending_view()

    async def _call_llm_phase1(self, user_prompt):
        self.transport_phase = "maintenance"
        maintenance = MAINTENANCE
        for old, new in GAP_REVISION_REPLACEMENTS:
            maintenance = maintenance.replace(old, new, 1)
        kwargs = {"prompt": user_prompt, "system": PHASE1_SYSTEM + maintenance + ALIGNED_EVIDENCE_RULES}
        if self.use_structured_tools:
            kwargs["tools"] = self.get_tools_schema()
        try:
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self.last_gap_report["transport_errors"].append({"phase": "maintenance", "type": type(exc).__name__})
            raise

    def _apply_operation(self, draft, name, args, index):
        if not isinstance(args, dict):
            raise ValueError("tool arguments must be an object")
        if name == "memory_delete":
            return super()._apply_operation(draft, name, args, index)
        if name not in WRITERS:
            raise ValueError("unknown memory operation")
        allowed = {"content", "evidence"}
        if name != "memory_update_status":
            allowed.add("memory_id")
        content = args.get("content")
        if (not set(args) <= allowed or not isinstance(content, str) or not content.strip() or
                ("memory_id" in args and (not isinstance(args["memory_id"], str) or not args["memory_id"]))):
            raise ValueError("write requires nonempty content and valid arguments")
        # Only missing or an empty array relaxes evidence. Explicit malformed
        # evidence (including null, scalar, or malformed items) still rejects.
        alignment = align_evidence(args.get("evidence", []), self._parts.catalog)
        kind = WRITERS[name]
        key, revision_id, disposition = draft.apply_aligned_write(kind, content, alignment,
            cycle_id=self._parts.manifest.cycle_id, op_index=index, memory_id=args.get("memory_id"))
        operation = MemoryOperation("update_status" if kind == "status" else "save_" + kind, key, content)
        operation.binding_status = alignment.status
        operation.binding_disposition = disposition
        operation.write_outcome = "retained_unbound" if disposition == "unbound" else "bound_write"
        operation.pending_target = draft.pending_proposals[key].target_id if key in draft.pending_proposals else None
        return operation

    @cached_source_validation
    def _execute_tool_calls(self, response):
        operations = super()._execute_tool_calls(response)
        self.last_evidence_report.update(binding_policy=self.policy,
            bound_writes=sum(getattr(op, "binding_disposition", None) == "bound" and op.success for op in operations),
            retained_unbound=sum(getattr(op, "binding_disposition", None) == "unbound" and op.success for op in operations))
        for outcome, operation in zip(self.last_evidence_report["operations"], operations):
            if operation.success and hasattr(operation, "binding_status"):
                outcome.update(binding_status=operation.binding_status, binding_disposition=operation.binding_disposition,
                    write_outcome=operation.write_outcome, pending_target=operation.pending_target)
        return operations

    def _build_phase1_prompt(self, observation, step_count):
        self._parts = None
        self._draft = None
        self.last_evidence_report = {"accepted": False, "errors": [], "binding_policy": self.policy}
        prepared, self._prepared = self._prepared, None
        try:
            if prepared is None:
                raise ValueError("visible_context_not_prepared")
            raw_hash, registry, public, error = prepared
            if error:
                raise ValueError(error)
            if raw_hash != sha256(observation):
                raise ValueError("visible_context_hash_mismatch")
            self._selected = []
            self._collect_phase1 = True
            try:
                # Reuse the original retrieval threshold and the untouched raw query.
                self._format_memory_bank(observation)
                self._format_memory_list(self.gaps.entries)
            finally:
                self._collect_phase1 = False
            draft = self.memory.fork_write_draft()
            memory_ids = (["status"] if self.memory.status else [])
            memory_ids += [entry.id for entry in self._selected]
            memory_ids += list(self.memory.pending_proposals)
            memory_blocks, labels = [], []
            totals = {"knowledge": len(self.memory.knowledge),
                      "procedural": len(self.memory.procedural),
                      "gap": len(self.gaps.entries), "status": int(bool(self.memory.status))}
            for pending in self.memory.pending_proposals.values():
                totals[pending.category] += 1
            selected = dict.fromkeys(totals, 0)
            for key in dict.fromkeys(memory_ids):
                row = draft.memory_source(registry, key)
                category = draft._content(key)[0]
                selected[category] += 1
                pending = self.memory.pending_proposals.get(key)
                target_label = f"; PENDING UNBOUND replacement for {pending.target_id}; original unchanged" if pending else ""
                labels.append(f"{key} ({category}; derived memory{target_label}); " + self._binding_text(key, include_quotes=False))
                memory_blocks.append(RenderBlock(registry.snapshot(row.source_id), display_id=key))
            prefix = f"## Step {step_count}\n## Current Memory Bank IDs\n"
            prefix += "\n".join(labels) or "(empty)"
            prefix += "\nSelected / total entries: " + "; ".join(
                f"{category} {selected[category]}/{total}" for category, total in totals.items())
            if any(selected[category] < total for category, total in totals.items()):
                prefix += "\nPartial retrieval view; unshown entries remain in the bank."
            else:
                prefix += "\nComplete current memory view."
            prefix += "\n## Visible Memory and Task / Recent Trajectory\n"
            suffix = ("\n## Your Task\nAnalyze the trajectory and update the memory bank. "
                      "Save important facts, record experiences, delete outdated entries. "
                      "Be selective.\n")
            if self._previous_failures:
                summary = "; ".join(f"#{row['index']} {row['tool']}: {row['error_code']}"
                                    for row in self._previous_failures[:3])
                suffix += ("Previous maintenance errors (host diagnostics, not evidence): "
                           + summary + f"; total failed={len(self._previous_failures)}.\n")
            suffix += self._maintenance_control_suffix()
            self._parts = render_source_blocks(memory_blocks + public,
                cycle_id="cycle_" + uuid.uuid4().hex, prefix=prefix, suffix=suffix)
            self._draft = draft
            return self._parts.text
        except (ValueError, TypeError, KeyError) as exc:
            self.last_evidence_report["errors"].append(str(exc))
            # No binding catalog survives failure; unchanged phase 2 still runs.
            return super()._build_phase1_prompt(observation, step_count)

