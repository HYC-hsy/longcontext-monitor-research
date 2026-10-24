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
Deletion uses only memory_id. A malformed operation rejects the entire batch.
"""
WRITERS = {
    "memory_save_knowledge": "knowledge",
    "memory_save_procedural": "procedural",
    "memory_update_status": "status",
    "memory_save_gap": "gap",
}


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
                  "system": PHASE1_SYSTEM + MAINTENANCE + EVIDENCE_RULES}
        if self.use_structured_tools:
            kwargs["tools"] = self.get_tools_schema()
        try:
            return await self.llm.call(**kwargs)
        except Exception as exc:
            self.last_gap_report["transport_errors"].append(
                {"phase": "maintenance", "type": type(exc).__name__})
            raise

    def _parse_batch(self, response):
        calls = getattr(response, "tool_calls", None)
        if calls:
            # A nonempty canonical sequence wins, including delete-only batches.
            # Invalid structured arguments must not be replaced by a second plan.
            return [self._extract_tool_call(call) for call in calls]
        raw = self._strip_thinking(getattr(response, "content", None) or "")
        if "<tool_call" not in raw and "</tool_call" not in raw:
            return []
        blocks = list(re.finditer(r"<tool_call>(.*?)</tool_call>", raw, re.DOTALL))
        if len(blocks) != raw.count("<tool_call") or len(blocks) != raw.count("</tool_call"):
            raise ValueError("malformed XML tool batch")
        parsed = []
        for block in blocks:
            match = re.fullmatch(r"\s*<function=(\w+)>(.*?)</function>\s*",
                                 block.group(1), re.DOTALL)
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
            parsed.append((name, args))
        return parsed

    def _execute_tool_calls(self, response):
        prepared = None
        committed_report = None
        operations = []
        try:
            calls = self._parse_batch(response)
            if not calls:
                self.last_evidence_report["accepted"] = True
                return []
            if self._parts is None or self._draft is None:
                raise ValueError("no_valid_visible_context")
            planned, deletes = [], set()
            for name, args in calls:
                if not isinstance(args, dict):
                    raise ValueError("tool arguments must be an object")
                if name == "memory_delete":
                    key = args.get("memory_id")
                    if set(args) != {"memory_id"} or not isinstance(key, str) or not key:
                        raise ValueError("delete requires memory_id")
                    if key == "status" or key in deletes:
                        raise ValueError("invalid or repeated delete ID")
                    self._draft._content(key)
                    deletes.add(key)
                    planned.append((name, key, None))
                elif name in WRITERS:
                    content = args.get("content")
                    if (set(args) != {"content", "evidence"} or
                            not isinstance(content, str) or not content.strip()):
                        raise ValueError("write requires nonempty content and evidence")
                    refs = bind_evidence(args["evidence"], self._parts.catalog)
                    planned.append((name, content, refs))
                else:
                    raise ValueError("unknown memory operation")
            draft = self._draft
            draft.retain_manifest(self._parts)
            operations = []
            cycle = self._parts.manifest.cycle_id
            for index, (name, value, refs) in enumerate(planned):
                if name == "memory_delete":
                    if not draft.delete_bound(value, cycle_id=cycle, op_index=index):
                        raise ValueError("delete failed")
                    action = "delete_gap" if value.startswith("gap_") else "delete"
                    operations.append(MemoryOperation(action, value))
                else:
                    kind = WRITERS[name]
                    key, _ = draft.apply_bound_write(kind, value, refs,
                                                     cycle_id=cycle, op_index=index)
                    action = "update_status" if kind == "status" else "save_" + kind
                    operations.append(MemoryOperation(action, key, value))
            prepared = self.memory.prepare_publication(draft)
            committed_report = {**self.last_evidence_report, "accepted": True}
            self.memory.publish(prepared)
            self.last_evidence_report = committed_report
            return operations
        except Exception as exc:
            if (prepared is not None and self.memory.__dict__ is prepared
                    and prepared.owner is self.memory
                    and self.memory._generation == prepared.generation + 1):
                # Publication is the commit point. A subsequent reporting failure
                # cannot turn a committed transaction into a rejected batch.
                self.last_evidence_report = committed_report
                self.last_evidence_report["post_commit_error"] = str(exc)
                return operations
            self.last_evidence_report["errors"].append(str(exc))
            return [MemoryOperation("evidence_batch", success=False, error=str(exc))]
        finally:
            self._draft = None
            self._parts = None
