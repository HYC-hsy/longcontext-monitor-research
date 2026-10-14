"""Research-only provenance extension of upstream UniversalMemory (S and R).

The upstream active lists and BM25 implementation remain the retrieval path.
Historical versions are deliberately separate and never indexed.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from memory_agent.memory.universal_memory import MemoryEntry, UniversalMemory


class SourceMemory(UniversalMemory):
    TYPES = {"task_requirement", "tool_observation", "agent_report", "inference"}

    def __init__(self):
        super().__init__()
        self.sources: dict[str, dict] = {}
        self.metadata: dict[str, dict] = {}
        self.history: list[dict] = []
        self.current_source_ids: list[str] = []

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

    def save_sourced(self, category: str, content: str, statement_type: str,
                     source_refs: object) -> str:
        if category not in {"knowledge", "procedural"} or not isinstance(content, str) or not content:
            raise ValueError("invalid sourced memory")
        refs = self.resolve_refs(source_refs, statement_type)
        memory_id = (super().save_knowledge(content) if category == "knowledge"
                     else super().save_procedural(content))
        self.metadata[memory_id] = {"version": 1, "category": category,
                                    "statement_type": statement_type, "source_refs": refs}
        return memory_id

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
               source_refs: object, reason: str, evidence: list[dict]) -> str:
        old = self.get(memory_id)
        if old is None or not content or not reason or not evidence:
            raise ValueError("revision requires active entry, replacement and evidence")
        refs = self.resolve_refs(source_refs, statement_type)
        meta = self.metadata[memory_id]
        category = meta["category"]
        entries = self.knowledge if category == "knowledge" else self.procedural
        index = next(i for i, e in enumerate(entries) if e.id == memory_id)
        new_id = self._generate_id()
        while new_id == memory_id or new_id in self.metadata:
            new_id = self._generate_id()
        replacement = MemoryEntry(id=new_id, content=content)
        new_meta = {"version": meta["version"] + 1, "category": category,
                    "statement_type": statement_type, "source_refs": refs,
                    "supersedes": memory_id}
        # Validate everything before changing the active list. No I/O in this switch.
        self.history.append({"action": "revise", "id": memory_id,
                             "entry": old.to_dict(), "meta": meta,
                             "reason": reason, "evidence": evidence, "replaced_by": new_id})
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
        if set(memory.metadata) != {e.id for e in memory.knowledge + memory.procedural}:
            raise ValueError("active source metadata mismatch")
        for meta in memory.metadata.values():
            for ref in meta["source_refs"]:
                if not memory.source_ref_valid(ref):
                    raise ValueError("source identity or excerpt mismatch on load")
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
