"""S2/R2 line-addressed public leaves on the inherited active PMA bank."""
from __future__ import annotations

import hashlib
import json

from source_memory import SourceMemory
from source_protocol_v2 import SourceLines


class SourceSelectionError(ValueError):
    """Typed source rejection; only fixed, bounded fields may reach the model."""

    def __init__(self, code: str, *, argument_path: str = "source_refs",
                 source_handle: str | None = None, total_lines: int | None = None,
                 required_role: str | None = None, actual_roles: tuple[str, ...] = ()):
        super().__init__(code)
        self.code = code
        self.argument_path = argument_path
        self.source_handle = source_handle
        self.total_lines = total_lines
        self.required_role = required_role
        self.actual_roles = actual_roles


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
        visible = {key: self.sources[key] for key in self.current_source_ids}
        for source_id in self.current_source_ids:
            source = self.sources[source_id]
            if "handle" not in source:
                raise ValueError("unversioned source in v2 bank")
            lines = self._line_spans(source["text"])
            rows.append({"source_handle": source["handle"], "role": source["role"],
                         "field_path": source["field_path"], "order": source["order"],
                         "total_lines": len(lines), "line_numbers": "1-based for this source_handle only",
                         "numbered_lines": [f"{n}: {line[2]}" for n, line in enumerate(lines, 1)]})
        by_handle = {source["handle"]: source for source in visible.values()}
        by_path = {(source["event_id"].removesuffix(":" + source["field_path"]),
                    source["field_path"]): source
                   for source in visible.values()}
        for row in rows:
            path = row["field_path"]
            if not path.endswith(("/stdout", "/stderr", "/msg", "/output")):
                continue
            child = by_handle[row["source_handle"]]
            event = child["event_id"].removesuffix(":" + path)
            parent = by_path.get((event, path.rsplit("/", 1)[0]))
            if parent is None or parent["role"] != "tool_observation":
                continue
            if (child["raw_sha256"], child["order"]) != (parent["raw_sha256"], parent["order"]):
                continue
            try:
                envelope = json.loads(parent["text"])
            except (ValueError, TypeError):
                continue
            if (isinstance(envelope, dict) and "status" in envelope
                    and envelope.get(path.rsplit("/", 1)[1]) == child["text"]):
                row["decoded_from"] = parent["handle"]
                row["coordinate_note"] = (f"{parent['handle']} is a separate "
                    f"{len(self._line_spans(parent['text']))}-line JSON wrapper; cite "
                    f"{row['source_handle']} for this decoded field's lines")
        return rows

    def resolve_refs(self, refs: object, statement_type: str) -> list[dict]:
        if statement_type not in self.TYPES or not isinstance(refs, list) or not refs:
            raise ValueError("statement type and source selections required")
        resolved = []
        visible = {self.sources[key].get("handle"): self.sources[key]
                   for key in self.current_source_ids}
        paths = getattr(self, "_diagnostic_ref_paths", {})
        base_path = paths.get(id(refs), "source_refs")
        self._last_resolve_path = base_path
        for index, item in enumerate(refs):
            selection = SourceLines.model_validate(item)
            source = visible.get(selection.source_handle)
            if source is None:
                if any(row.get("handle") == selection.source_handle for row in self.sources.values()):
                    raise SourceSelectionError("window_invisible", argument_path=f"{base_path}[{index}]")
                raise SourceSelectionError("unknown_source", argument_path=f"{base_path}[{index}]")
            spans = self._line_spans(source["text"])
            if selection.end_line < selection.start_line or selection.end_line > len(spans):
                raise SourceSelectionError("invalid_range", argument_path=f"{base_path}[{index}]",
                                           source_handle=selection.source_handle, total_lines=len(spans))
            start = spans[selection.start_line - 1][0]
            end = spans[selection.end_line - 1][1]
            excerpt = source["text"][start:end]
            if not excerpt:
                raise SourceSelectionError("invalid_range", argument_path=f"{base_path}[{index}]",
                                           source_handle=selection.source_handle, total_lines=len(spans))
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

    def _check_roles(self, refs: list[dict], statement_type: str) -> None:
        required = {"task_requirement": "task_instruction", "tool_observation": "tool_observation",
                    "agent_report": "agent_report"}.get(statement_type)
        roles = {ref["role"] for ref in refs}
        if required and required not in roles:
            raise SourceSelectionError("role_mismatch",
                argument_path=getattr(self, "_last_resolve_path", "source_refs"),
                required_role=required, actual_roles=tuple(sorted(roles)))
        super()._check_roles(refs, statement_type)

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
