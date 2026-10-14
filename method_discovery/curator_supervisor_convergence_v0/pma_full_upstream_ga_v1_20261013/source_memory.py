"""Research-only provenance extension of upstream UniversalMemory (S and R).

The upstream active lists and BM25 implementation remain the retrieval path.
Historical versions are deliberately separate and never indexed.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from pathlib import Path

from memory_agent.memory.universal_memory import MemoryEntry, UniversalMemory


class SourceMemory(UniversalMemory):
    TYPES = {"task_requirement", "tool_observation", "agent_report", "inference"}
    COORDINATION = {"unreviewed", "retain", "unresolved", "revised"}

    def __init__(self):
        super().__init__()
        self.sources: dict[str, dict] = {}
        self.metadata: dict[str, dict] = {}
        self.history: list[dict] = []
        self.current_source_ids: list[str] = []

    def _used_ids(self) -> set[str]:
        return (set(self.metadata) | {e.id for e in self.knowledge + self.procedural}
                | {h["id"] for h in self.history if isinstance(h, dict) and "id" in h})

    def _generate_id(self) -> str:
        used = self._used_ids()
        for _ in range(32):
            candidate = super()._generate_id()
            if candidate not in used:
                return candidate
        while True:
            candidate = uuid.uuid4().hex[:16]
            if candidate not in used:
                return candidate

    def register_source(self, event_id: str, role: str, text: str, order: int) -> None:
        if role not in {"task_instruction", "tool_observation", "agent_report", "tool_command"}:
            raise ValueError("invalid public source role")
        if not event_id or not isinstance(text, str) or type(order) is not int:
            raise ValueError("invalid public source")
        row = {"event_id": event_id, "role": role, "text": text, "order": order,
               "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        if event_id in self.sources and self.sources[event_id] != row:
            raise ValueError("public source identity changed")
        self.sources[event_id] = row
        if event_id not in self.current_source_ids:
            self.current_source_ids.append(event_id)

    def resolve_refs(self, refs: object, statement_type: str) -> list[dict]:
        if statement_type not in self.TYPES or not isinstance(refs, list) or not refs:
            raise ValueError("statement type and nonempty source_refs required")
        resolved = []
        for ref in refs:
            if not isinstance(ref, dict) or set(ref) != {"event_id", "role", "quote"}:
                raise ValueError("source ref requires event_id, role, quote")
            source = self.sources.get(ref["event_id"])
            if source is None or source["event_id"] not in self.current_source_ids:
                raise ValueError("source was not in this visible context")
            if source["role"] != ref["role"]:
                raise ValueError("source role mismatch")
            quote = ref["quote"]
            if not isinstance(quote, str) or not quote or source["text"].count(quote) != 1:
                raise ValueError("quote must occur exactly once in visible source")
            start = source["text"].index(quote)
            resolved.append({"event_id": source["event_id"], "role": source["role"],
                             "order": source["order"], "start": start,
                             "end": start + len(quote), "event_sha256": source["sha256"],
                             "snippet_sha256": hashlib.sha256(quote.encode()).hexdigest()})
        roles = {r["role"] for r in resolved}
        if statement_type == "task_requirement" and "task_instruction" not in roles:
            raise ValueError("task requirement requires instruction source")
        if statement_type == "tool_observation" and "tool_observation" not in roles:
            raise ValueError("Task report cannot become tool observation")
        if statement_type == "agent_report" and "agent_report" not in roles:
            raise ValueError("agent report requires public agent response")
        return resolved

    def source_ref_valid(self, ref: dict) -> bool:
        if not isinstance(ref, dict):
            return False
        source = self.sources.get(ref.get("event_id"))
        if source is None or source["role"] != ref.get("role"):
            return False
        if hashlib.sha256(source["text"].encode()).hexdigest() != source["sha256"]:
            return False
        if source["sha256"] != ref.get("event_sha256") or source["order"] != ref.get("order"):
            return False
        start, end = ref.get("start"), ref.get("end")
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(source["text"]):
            return False
        return hashlib.sha256(source["text"][start:end].encode()).hexdigest() == ref.get("snippet_sha256")

    def excerpt(self, ref: dict) -> str:
        if not self.source_ref_valid(ref):
            raise ValueError("invalid bound source excerpt")
        source = self.sources[ref["event_id"]]
        return source["text"][ref["start"]:ref["end"]]

    def _check_roles(self, refs: list[dict], statement_type: str) -> None:
        if statement_type not in self.TYPES or not refs:
            raise ValueError("invalid statement type or empty sources")
        roles = {ref["role"] for ref in refs}
        required = {"task_requirement": "task_instruction",
                    "tool_observation": "tool_observation",
                    "agent_report": "agent_report"}.get(statement_type)
        if required and required not in roles:
            raise ValueError(f"{statement_type} requires {required} source")

    def validate_bank(self) -> None:
        active = [(e, category) for category, entries in
                  (("knowledge", self.knowledge), ("procedural", self.procedural))
                  for e in entries]
        ids = [e.id for e, _ in active]
        if len(ids) != len(set(ids)) or set(ids) != set(self.metadata):
            raise ValueError("active IDs or metadata do not match uniquely")
        retired = {h.get("id") for h in self.history if isinstance(h, dict)
                   and h.get("action") in {"revise", "retract", "upstream_delete"}}
        if retired.intersection(ids):
            raise ValueError("retired version is active")
        for entry, category in active:
            meta = self.metadata[entry.id]
            if not isinstance(meta, dict) or meta.get("category") != category:
                raise ValueError("invalid memory category")
            if type(meta.get("version")) is not int or meta["version"] < 1:
                raise ValueError("invalid memory version")
            refs = meta.get("source_refs")
            if not isinstance(refs, list) or not refs or not all(self.source_ref_valid(r) for r in refs):
                raise ValueError("invalid or empty bound source refs")
            self._check_roles(refs, meta.get("statement_type"))
            state = meta.get("coordination")
            if (not isinstance(state, dict) or state.get("decision") not in self.COORDINATION
                    or type(state.get("revision")) is not int or state["revision"] < 0
                    or not isinstance(state.get("reason"), str)
                    or not isinstance(state.get("evidence_refs"), list)
                    or not all(self.source_ref_valid(r) for r in state["evidence_refs"])):
                raise ValueError("invalid coordination state")
            if state["decision"] != "unreviewed" and (not state["reason"] or not state["evidence_refs"]):
                raise ValueError("coordination lacks current reason/evidence")

    @staticmethod
    def _unreviewed() -> dict:
        return {"decision": "unreviewed", "revision": 0, "reason": "", "evidence_refs": []}

    def save_sourced(self, category: str, content: str, statement_type: str,
                     source_refs: object) -> str:
        if category not in {"knowledge", "procedural"} or not isinstance(content, str) or not content.strip():
            raise ValueError("invalid sourced memory")
        refs = self.resolve_refs(source_refs, statement_type)
        memory_id = (super().save_knowledge(content) if category == "knowledge"
                     else super().save_procedural(content))
        self.metadata[memory_id] = {"version": 1, "category": category,
                                    "statement_type": statement_type, "source_refs": refs,
                                    "coordination": self._unreviewed()}
        return memory_id

    def coordinate(self, memory_id: str, decision: str, reason: str,
                   evidence: list[dict]) -> None:
        if decision not in {"retain", "unresolved"} or self.get(memory_id) is None:
            raise ValueError("invalid coordination target")
        if not isinstance(reason, str) or not reason or not evidence or not all(
                self.source_ref_valid(r) for r in evidence):
            raise ValueError("invalid coordination evidence")
        meta = self.metadata[memory_id]
        previous = meta["coordination"]
        current = {"decision": decision, "reason": reason,
                   "evidence_refs": evidence, "revision": previous["revision"] + 1}
        self.history.append({"action": "coordinate", "id": memory_id,
                             "version": meta["version"], "previous": previous,
                             "current": current})
        meta["coordination"] = current

    def retract(self, memory_id: str, reason: str, evidence: list[dict]) -> bool:
        entry = self.get(memory_id)
        if entry is None:
            return any(h["id"] == memory_id and h["action"] == "retract" for h in self.history)
        if not reason or not evidence:
            raise ValueError("retraction requires reason and current evidence")
        self.history.append({"action": "retract", "id": memory_id,
                             "entry": entry.to_dict(), "meta": self.metadata[memory_id],
                             "reason": reason, "evidence": evidence})
        super().delete(memory_id)
        del self.metadata[memory_id]
        return True

    def revise(self, memory_id: str, content: str, statement_type: str,
               source_refs: object, reason: str, evidence: list[dict],
               inherit_indices: object = None) -> str:
        old = self.get(memory_id)
        if (old is None or not isinstance(content, str) or not content.strip()
                or not isinstance(reason, str) or not reason or not evidence):
            raise ValueError("revision requires active entry, replacement and evidence")
        meta = self.metadata[memory_id]
        if not all(self.source_ref_valid(r) for r in evidence):
            raise ValueError("invalid revision evidence")
        indices = [] if inherit_indices is None else inherit_indices
        if (not isinstance(indices, list) or any(type(i) is not int or i < 0
                or i >= len(meta["source_refs"]) for i in indices)
                or len(set(indices)) != len(indices)):
            raise ValueError("invalid inherited source indices")
        inherited = [meta["source_refs"][i] for i in indices]
        if not all(self.source_ref_valid(r) for r in inherited):
            raise ValueError("invalid inherited source")
        if source_refs is None:
            source_refs = []
        if not isinstance(source_refs, list):
            raise ValueError("revision source refs must be a list")
        new_refs = (self.resolve_refs(source_refs, "inference") if source_refs else [])
        refs = inherited + new_refs
        self._check_roles(refs, statement_type)
        category = meta["category"]
        entries = self.knowledge if category == "knowledge" else self.procedural
        index = next(i for i, e in enumerate(entries) if e.id == memory_id)
        new_id = self._generate_id()
        replacement = MemoryEntry(id=new_id, content=content)
        new_meta = {"version": meta["version"] + 1, "category": category,
                    "statement_type": statement_type, "source_refs": refs,
                    "supersedes": memory_id,
                    "source_inheritance": {"from": memory_id, "indices": indices,
                                           "new_refs": new_refs},
                    "coordination": {"decision": "revised", "revision": 1,
                                     "reason": reason, "evidence_refs": evidence}}
        # Validate everything before changing the active list. No I/O in this switch.
        self.history.append({"action": "revise", "id": memory_id,
                             "entry": old.to_dict(), "meta": meta,
                             "reason": reason, "evidence": evidence, "replaced_by": new_id,
                             "inherited_refs": inherited, "new_refs": new_refs})
        entries[index] = replacement
        del self.metadata[memory_id]
        self.metadata[new_id] = new_meta
        self._invalidate_indices(category)
        return new_id

    def delete(self, memory_id: str) -> bool:
        entry = self.get(memory_id)
        if entry is None:
            return False
        self.history.append({"action": "upstream_delete", "id": memory_id,
                             "entry": entry.to_dict(), "meta": self.metadata[memory_id]})
        del self.metadata[memory_id]
        return super().delete(memory_id)

    def to_dict(self) -> dict:
        self.validate_bank()
        base = super().to_dict()
        base.update({"source_memory_schema": 1, "sources": self.sources,
                     "metadata": self.metadata, "history": self.history})
        return base

    @classmethod
    def from_dict(cls, data: dict) -> SourceMemory:
        if data.get("source_memory_schema") != 1:
            raise ValueError("not a source-memory bank")
        base = UniversalMemory.from_dict(data)
        memory = cls()
        memory._status = base._status
        memory._knowledge = base.knowledge
        memory._procedural = base.procedural
        memory.sources = data["sources"]
        memory.metadata = data["metadata"]
        memory.history = data["history"]
        memory.validate_bank()
        return memory

    def save_to_file(self, path: Path | str) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=".sourced-memory-")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(self.to_dict(), stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
