"""Separate, directly maintained gap entries over the upstream PMA bank."""

from copy import deepcopy
import shortuuid
from memory_agent.memory.universal_memory import MemoryEntry, UniversalMemory


class GapMemory(UniversalMemory):
    def __init__(self, max_status_length=2000):
        super().__init__(max_status_length=max_status_length)
        self._gap_entries = []

    @property
    def entries(self):
        return deepcopy(self._gap_entries)

    def save_gap(self, content):
        if not isinstance(content, str) or not content.strip():
            raise ValueError("gap content must be non-empty natural-language text")
        key = "gap_" + shortuuid.uuid()[:8]
        used = {entry.id for entry in self._gap_entries}
        while key in used:
            key = "gap_" + shortuuid.uuid()[:8]
        entry = MemoryEntry(id=key, content=content)
        self._gap_entries.append(entry)
        return key

    def delete_gap(self, key):
        for index, entry in enumerate(self._gap_entries):
            if entry.id == key:
                self._gap_entries.pop(index)
                return True
        return False

    def clear(self, keep_status=False):
        super().clear(keep_status=keep_status)
        self._gap_entries.clear()

    def to_dict(self):
        return {**super().to_dict(), "gaps": [entry.to_dict() for entry in self._gap_entries]}

    @classmethod
    def from_dict(cls, data):
        memory = super().from_dict(data)
        memory._gap_entries = [MemoryEntry.from_dict(row) for row in data.get("gaps", [])]
        ids = [entry.id for entry in memory._gap_entries]
        if len(ids) != len(set(ids)) or any(not key.startswith("gap_") for key in ids):
            raise ValueError("invalid saved gap identities")
        return memory

