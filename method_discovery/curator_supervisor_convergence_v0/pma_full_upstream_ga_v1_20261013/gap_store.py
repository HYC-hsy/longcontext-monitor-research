"""Small upstream bank extension; only official gaps enter serialization."""

from copy import deepcopy
import shortuuid
from memory_agent.memory.universal_memory import MemoryEntry, UniversalMemory


class GapMemory(UniversalMemory):
    def __init__(self, max_status_length=2000):
        super().__init__(max_status_length=max_status_length)
        self._entries = []
        self.candidate = None
        self.changes = []

    @property
    def entries(self):
        return deepcopy(self._entries)

    def begin(self):
        if self.candidate is not None:
            raise RuntimeError("gap transaction already active")
        self.candidate = self.entries
        self.changes = []

    def stage_save(self, content):
        if self.candidate is None:
            raise RuntimeError("no active gap transaction")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("gap content must be non-empty natural-language text")
        key = "gap_" + shortuuid.uuid()[:8]
        used = {entry.id for entry in self.candidate + self._entries}
        while key in used:
            key = "gap_" + shortuuid.uuid()[:8]
        entry = MemoryEntry(id=key, content=content)
        self.candidate.append(entry)
        self.changes.append({"action": "save_gap", "entry": entry.to_dict()})
        return key

    def stage_delete(self, key):
        if self.candidate is None:
            raise RuntimeError("no active gap transaction")
        for index, entry in enumerate(self.candidate):
            if entry.id == key:
                self.candidate.pop(index)
                self.changes.append({"action": "delete_gap", "entry": entry.to_dict()})
                return True
        return False

    def commit(self):
        if self.candidate is None:
            raise RuntimeError("no active gap transaction")
        committed = deepcopy(self.candidate)
        # One reference swap, with no await or ordinary-memory rollback.
        self._entries = committed
        self.candidate = None

    def discard(self):
        self.candidate = None

    def clear(self, keep_status=False):
        super().clear(keep_status=keep_status)
        self._entries.clear()
        self.candidate = None
        self.changes = []

    def to_dict(self):
        return {**super().to_dict(), "gaps": [entry.to_dict() for entry in self._entries]}

    @classmethod
    def from_dict(cls, data):
        memory = super().from_dict(data)
        memory._entries = [MemoryEntry.from_dict(row) for row in data.get("gaps", [])]
        ids = [entry.id for entry in memory._entries]
        if len(ids) != len(set(ids)) or any(not key.startswith("gap_") for key in ids):
            raise ValueError("invalid saved gap identities")
        return memory

