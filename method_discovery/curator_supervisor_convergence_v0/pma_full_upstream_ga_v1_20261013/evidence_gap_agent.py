"""Opt-in literal evidence binding over the unchanged two-phase gap agent."""
import json
import re
import uuid

from evidence_gap_store import EvidenceGapMemory
from gap_evidence import (RenderBlock, SourceRegistry, bind_evidence,
                          register_public_source, render_source_blocks, sha256)
from gap_memory_agent import GapMemoryAgent
from gap_prompts import MAINTENANCE
from memory_agent.memory.memory_agent import MemoryOperation, PHASE1_SYSTEM


EVIDENCE_RULES = """
Every save or status update requires evidence: a nonempty array of objects with
source (the displayed memory ID or raw-event source handle) and quote (an exact, uniquely matching visible
substring). For XML tools, encode that array as JSON in parameter=evidence.
Use only displayed sources. Source labels are host-assigned; do not invent roles
or offsets. Agent reports are reports, tool commands are intentions, and derived
memory is not independent observation. Preserve inference, uncertainty, scope,
and version boundaries in your content; literal binding does not prove truth or
entailment. When revising, cite the relevant visible observations or prior memory.
For an existing knowledge, procedural, or gap entry, pass its displayed memory_id
in the same save tool to revise it in place. The category cannot change. Omit
memory_id only for a new entry. Do not delete then save to express an update.
Deletion uses only memory_id. Each operation is atomic and independent: a failed operation does not undo other
successful operations. An explicit delete is not coupled to a later save.
"""
# Evidence-only adaptations of the two legacy gap replacement instructions.
# Exact anchors are checked against the inherited text in regression tests;
# ordinary pma-gap and the vendor prompt remain untouched.
GAP_REVISION_REPLACEMENTS = (
    (
        "Save and delete update the view immediately. To revise, delete the displayed real gap\n"
        "ID and save a new entry; never guess a new ID. Unmentioned entries remain.",
        "Save and delete update the view immediately. To revise a gap, use memory_save_gap\n"
        "with its displayed memory_id, replacement content, and evidence in one operation;\n"
        "never delete it first or guess a new ID. Unmentioned entries remain.",
    ),
    (
        "ID. If only part is resolved, revise it using the existing delete-and-save tools\n"
        "so the unresolved part remains.",
        "ID. If only part is resolved, use memory_save_gap with that displayed memory_id,\n"
        "content describing the unresolved part, and evidence to revise it in place.",
    ),
)


def evidence_phase1_system():
    maintenance = MAINTENANCE
    for old, new in GAP_REVISION_REPLACEMENTS:
        maintenance = maintenance.replace(old, new, 1)
    return PHASE1_SYSTEM + maintenance + EVIDENCE_RULES


WRITERS = {
    "memory_save_knowledge": "knowledge",
    "memory_save_procedural": "procedural",
    "memory_update_status": "status",
    "memory_save_gap": "gap",
}


# Only static host diagnostics may be fed back into a subsequent model request.
_ERROR_CODES = {
    text: text.replace(" ", "_") for text in (
        "empty_evidence", "invalid_source_snapshot", "invalid_evidence_item",
        "invalid_source", "invalid_quote", "source_not_visible", "quote_not_visible",
        "ambiguous_quote", "memory ID not found", "status cannot be deleted by ID",
        "update target must be an existing same-category memory ID",
        "delete requires memory_id", "write requires nonempty content and evidence",
        "tool arguments must be an object", "unknown memory operation",
        "no_valid_visible_context", "malformed XML tool call", "malformed XML function",
        "malformed XML parameters", "invalid bound write", "stale publication")}


class EvidenceGapMemoryAgent(GapMemoryAgent):
    def __init__(self, *, memory, **kwargs):
        if not isinstance(memory, EvidenceGapMemory):
            raise TypeError("evidence adapter requires EvidenceGapMemory")
        super().__init__(memory=memory, **kwargs)
        self._namespace = "gap_evidence_" + uuid.uuid4().hex
        self._prepared = None
        self._parts = None
        self._draft = None
        self.last_evidence_report = {}
        self._previous_failures = []
        for tool in self._tools:
            function = tool["function"]
            if function["name"] not in WRITERS:
                continue
            params = function["parameters"]
            params["properties"]["content"]["minLength"] = 1
            params["properties"]["evidence"] = {
                "type": "array", "minItems": 1,
                "items": {"type": "object", "properties": {
                    "source": {"type": "string", "minLength": 1},
                    "quote": {"type": "string", "minLength": 1}},
                    "required": ["source", "quote"], "additionalProperties": False}}
            if function["name"] != "memory_update_status":
                params["properties"]["memory_id"] = {"type": "string", "minLength": 1,
                    "description": "Existing same-category memory ID to update; omit to create."}
            params["required"] = ["content", "evidence"]
            params["additionalProperties"] = False

    def prepare_visible_context(self, raw_observation: str, blocks: list[dict]):
        """Host supplies public projections; never decode a tool wrapper twice."""
        self._prepared = None
        try:
            if not isinstance(raw_observation, str) or not isinstance(blocks, list):
                raise ValueError("invalid visible context")
            registry = SourceRegistry(self._namespace)
            rendered, registered = [], {}
            for block in blocks:
                if not isinstance(block, dict):
                    raise ValueError("invalid source block")
                parent = None
                if "parent_field_path" in block:
                    parent = registered[(block["source_id"], block["parent_field_path"])]
                _, row = register_public_source(
                    registry, event_id=block["source_id"], role=block["role"],
                    text=block["text"], order=block["order"],
                    field_path=block["field_path"], record_digest=block["record_digest"],
                    record_digest_kind=block["record_digest_kind"],
                    tool_call_id=block.get("tool_call_id"),
                    parent_wrapper_source_id=parent)
                registered[(block["source_id"], block["field_path"])] = row.source_id
                spans = block.get("render_spans")
                if spans is None or spans:
                    rendered.append(RenderBlock(registry.snapshot(row.source_id), spans))
            self._prepared = (sha256(raw_observation), registry, rendered, None)
        except (ValueError, TypeError, KeyError) as exc:
            self._prepared = (None, None, None, str(exc))

    def _format_memory_list(self, entries):
        if getattr(self, "_collect_phase1", False):
            self._selected.extend(entries)
        return super()._format_memory_list(entries)

    def _build_phase1_prompt(self, observation, step_count):
        self._parts = None
        self._draft = None
        self.last_evidence_report = {"accepted": False, "errors": []}
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
            memory_blocks, labels = [], []
            totals = {"knowledge": len(self.memory.knowledge),
                      "procedural": len(self.memory.procedural),
                      "gap": len(self.gaps.entries), "status": int(bool(self.memory.status))}
            selected = dict.fromkeys(totals, 0)
            for key in dict.fromkeys(memory_ids):
                row = draft.memory_source(registry, key)
                category = draft._content(key)[0]
                selected[category] += 1
                labels.append(f"{key} ({category}; derived memory)")
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
            self._parts = render_source_blocks(memory_blocks + public,
                cycle_id="cycle_" + uuid.uuid4().hex, prefix=prefix, suffix=suffix)
            self._draft = draft
            return self._parts.text
        except (ValueError, TypeError, KeyError) as exc:
            self.last_evidence_report["errors"].append(str(exc))
            # No binding catalog survives failure; unchanged phase 2 still runs.
            return super()._build_phase1_prompt(observation, step_count)

    async def _call_llm_phase1(self, user_prompt):
        self.transport_phase = "maintenance"
        kwargs = {"prompt": user_prompt,
                  "system": evidence_phase1_system()}
        if self.use_structured_tools:
            kwargs["tools"] = self.get_tools_schema()
        try:
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self.last_gap_report["transport_errors"].append(
                {"phase": "maintenance", "type": type(exc).__name__})
            raise

    def _tool_items(self, response):
        calls = getattr(response, "tool_calls", None)
        if calls:
            # Canonical structured calls win, including malformed/delete-only calls.
            return [("structured", call) for call in calls]
        raw = self._strip_thinking(getattr(response, "content", None) or "")
        items, start, depth, malformed = [], None, 0, False
        for marker in re.finditer(r"<tool_call\b[^>]*(?:>|$)|</tool_call\s*(?:>|$)", raw):
            if marker[0].startswith("<tool_call"):
                if depth == 0:
                    start, malformed = marker.end(), marker[0] != "<tool_call>"
                else:
                    # A nested action may be quoted argument text, not a sibling.
                    # Quarantine the whole outer region instead of salvaging it.
                    malformed = True
                depth += 1
            elif depth:
                depth -= 1
                malformed = malformed or marker[0] != "</tool_call>"
                if depth == 0:
                    items.append(("invalid", "malformed XML tool call") if malformed
                                 else ("xml", raw[start:marker.start()]))
            else:
                items.append(("invalid", "malformed XML tool call"))
        if depth or (not items and ("<tool_call" in raw or "</tool_call" in raw)):
            items.append(("invalid", "malformed XML tool call"))
        return items

    def _parse_item(self, item):
        mode, value = item
        if mode == "structured":
            return self._extract_tool_call(value)
        if mode == "invalid":
            raise ValueError(value)
        match = re.fullmatch(r"\s*<function=(\w+)>(.*?)</function>\s*", value, re.DOTALL)
        if match is None:
            raise ValueError("malformed XML function")
        name, body = match.groups()
        args, end = {}, 0
        for parameter in re.finditer(r"<parameter=(\w+)>(.*?)</parameter>", body, re.DOTALL):
            if body[end:parameter.start()].strip() or parameter[1] in args:
                raise ValueError("malformed XML parameters")
            args[parameter[1]] = parameter[2].strip()
            end = parameter.end()
        if body[end:].strip():
            raise ValueError("malformed XML parameters")
        if "evidence" in args:
            args["evidence"] = json.loads(args["evidence"])
        return name, args

    def _operation_draft(self):
        if self._parts is None or self._draft is None:
            raise ValueError("no_valid_visible_context")
        draft = self.memory.fork_write_draft()
        # P1 snapshots are fixed. Retain their legacy revisions once, including
        # an entry deleted by an earlier successful operation in this response.
        if self._parts.manifest.cycle_id not in draft.manifests:
            for revision_id in self._parts.manifest.pre_cycle_revision_refs:
                row = self._draft.revisions[revision_id]
                draft.revisions = draft.revisions.add(revision_id, row)
                draft.blobs = draft.blobs.add(row.content_sha256,
                                              self._draft.blobs[row.content_sha256])
                draft._reserved_ids = draft._reserved_ids.add(row.memory_id, True)
                draft.active_revisions.setdefault(row.memory_id, revision_id)
        draft.retain_manifest(self._parts)
        return draft

    def _apply_operation(self, draft, name, args, index):
        if not isinstance(args, dict):
            raise ValueError("tool arguments must be an object")
        cycle = self._parts.manifest.cycle_id
        if name == "memory_delete":
            key = args.get("memory_id")
            if set(args) != {"memory_id"} or not isinstance(key, str) or not key:
                raise ValueError("delete requires memory_id")
            draft.delete_bound(key, cycle_id=cycle, op_index=index)
            return MemoryOperation("delete_gap" if key.startswith("gap_") else "delete", key)
        if name not in WRITERS:
            raise ValueError("unknown memory operation")
        allowed = {"content", "evidence"}
        if name != "memory_update_status":
            allowed.add("memory_id")
        content = args.get("content")
        if (not {"content", "evidence"}.issubset(args) or not set(args) <= allowed or
                ("memory_id" in args and
                 (not isinstance(args["memory_id"], str) or not args["memory_id"])) or
                not isinstance(content, str) or not content.strip()):
            raise ValueError("write requires nonempty content and evidence")
        refs = bind_evidence(args["evidence"], self._parts.catalog)
        kind = WRITERS[name]
        key, _ = draft.apply_bound_write(kind, content, refs, cycle_id=cycle,
                                         op_index=index, memory_id=args.get("memory_id"))
        return MemoryOperation("update_status" if kind == "status" else "save_" + kind,
                               key, content)

    def _execute_tool_calls(self, response):
        """Adapt PMA 89e5c0d memory_agent.py:480-513 per-call try/dispatch loop.

        Parsing moves inside the try; each evidence operation publishes its own
        draft. There is no batch rollback, dependency guessing, or repair call.
        """
        operations, outcomes = [], []
        try:
            try:
                calls = self._tool_items(response)
            except Exception as exc:
                calls = [("invalid", str(exc))]
            for index, tool_call in enumerate(calls):
                name, prepared, operation = "invalid_memory_operation", None, None
                try:
                    if tool_call[0] == "structured":
                        candidate = getattr(getattr(tool_call[1], "function", tool_call[1]),
                                            "name", None)
                        if isinstance(candidate, str) and candidate in {*WRITERS, "memory_delete"}:
                            name = candidate
                    name, args = self._parse_item(tool_call)
                    draft = self._operation_draft()
                    operation = self._apply_operation(draft, name, args, index)
                    prepared = self.memory.prepare_publication(draft)
                    self.memory.publish(prepared)
                except Exception as exc:
                    if (prepared is not None and self.memory.__dict__ is prepared
                            and prepared.owner is self.memory
                            and self.memory._generation == prepared.generation + 1):
                        # A reporting failure cannot undo an already committed op.
                        self.last_evidence_report["post_commit_error"] = str(exc)
                    else:
                        operation = MemoryOperation(name, success=False, error=str(exc))
                        self.last_evidence_report["errors"].append(str(exc))
                        outcomes.append({"index": index, "tool": name if isinstance(name, str) and name in
                            {*WRITERS, "memory_delete"} else "invalid_memory_operation",
                            "success": False, "error_code": _ERROR_CODES.get(str(exc), type(exc).__name__)})
                operations.append(operation)
                if operation.success:
                    outcomes.append({"index": index, "tool": name, "success": True})
            succeeded = sum(op.success for op in operations)
            failed = len(operations) - succeeded
            self.last_evidence_report.update(accepted=failed == 0,
                partial_success=bool(succeeded and failed), succeeded=succeeded,
                failed=failed, operations=outcomes)
            self._previous_failures = [row for row in outcomes if not row["success"]]
            return operations
        finally:
            self._draft = None
            self._parts = None
