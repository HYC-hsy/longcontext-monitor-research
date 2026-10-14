"""S2/R2 line-addressed public leaves on the inherited active PMA bank."""
from __future__ import annotations

import hashlib

from source_memory import SourceMemory
from source_protocol_v2 import SourceLines


class SourceMemoryV2(SourceMemory):
    @staticmethod
    def _line_spans(text: str) -> list[tuple[int, int, str]]:
        """One-based displayed lines map to Python text offsets, not raw-byte offsets."""
        rows = []
        offset = 0
        for part in text.splitlines(keepends=True):
            visible = part.rstrip("\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")
            rows.append((offset, offset + len(visible), visible))
            offset += len(part)
        return rows

    def register_leaf(self, event_id: str, role: str, text: str, order: int,
                      field_path: str, raw_sha256: str) -> str | None:
        if not isinstance(text, str) or not text:
            return None
        if not field_path or not isinstance(raw_sha256, str) or len(raw_sha256) != 64:
            raise ValueError("source record identity missing")
        source_id = event_id + ":" + field_path
        handle = "s" + hashlib.sha256(source_id.encode("utf-8")).hexdigest()[:12]
        if any(row.get("handle") == handle and key != source_id
               for key, row in self.sources.items()):
            raise ValueError("source handle collision")
        if source_id in self.sources:
            row = self.sources[source_id]
            if (row.get("handle"), row.get("raw_sha256"), row.get("field_path")) != (
                    handle, raw_sha256, field_path):
                raise ValueError("source leaf changed")
            if source_id not in self.current_source_ids:
                self.current_source_ids.append(source_id)
            return handle
        super().register_source(source_id, role, text, order)
        self.sources[source_id].update(handle=handle, field_path=field_path,
                                       raw_sha256=raw_sha256)
        return handle

    def visible_lines(self) -> list[dict]:
        rows = []
        for source_id in self.current_source_ids:
            source = self.sources[source_id]
            if "handle" not in source:
                raise ValueError("unversioned source in v2 bank")
            lines = self._line_spans(source["text"])
            rows.append({"source_handle": source["handle"], "role": source["role"],
                         "field_path": source["field_path"], "order": source["order"],
                         "numbered_lines": [f"{n}: {line[2]}" for n, line in enumerate(lines, 1)]})
        return rows

    def resolve_refs(self, refs: object, statement_type: str) -> list[dict]:
        if statement_type not in self.TYPES or not isinstance(refs, list) or not refs:
            raise ValueError("statement type and source selections required")
        resolved = []
        visible = {self.sources[key].get("handle"): self.sources[key]
                   for key in self.current_source_ids}
        for item in refs:
            selection = SourceLines.model_validate(item)
            source = visible.get(selection.source_handle)
            if source is None:
                if any(row.get("handle") == selection.source_handle for row in self.sources.values()):
                    raise ValueError("window-invisible source handle")
                raise ValueError("unknown source handle")
            spans = self._line_spans(source["text"])
            if selection.end_line < selection.start_line or selection.end_line > len(spans):
                raise ValueError("source line range outside visible leaf")
            start = spans[selection.start_line - 1][0]
            end = spans[selection.end_line - 1][1]
            excerpt = source["text"][start:end]
            if not excerpt:
                raise ValueError("empty source line selection")
            resolved.append({"event_id": source["event_id"], "role": source["role"],
                             "order": source["order"], "start": start, "end": end,
                             "event_sha256": source["sha256"],
                             "snippet_sha256": hashlib.sha256(excerpt.encode()).hexdigest(),
                             "source_handle": selection.source_handle,
                             "start_line": selection.start_line, "end_line": selection.end_line,
                             "raw_sha256": source["raw_sha256"],
                             "field_path": source["field_path"]})
        self._check_roles(resolved, statement_type)
        return resolved

    def source_ref_valid(self, ref: dict) -> bool:
        if not super().source_ref_valid(ref):
            return False
        source = self.sources[ref["event_id"]]
        start_line, end_line = ref.get("start_line"), ref.get("end_line")
        spans = self._line_spans(source["text"])
        if (type(start_line) is not int or type(end_line) is not int or
                not 1 <= start_line <= end_line <= len(spans)):
            return False
        start = spans[start_line - 1][0]
        end = spans[end_line - 1][1]
        return (source.get("handle") == ref.get("source_handle") and
                source.get("raw_sha256") == ref.get("raw_sha256") and
                source.get("field_path") == ref.get("field_path") and
                ref["start"] == start and ref["end"] == end)
