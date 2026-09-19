"""Direct-investigation evidence access diagnostic.

This is deliberately separate from the three-way question/C protocol.  Both
conditions restore the same parent state and receive the same six-call budget;
the only experimental difference is access to a manifest-validated, read-only
index over the frozen task workspace.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, Callable

from monitor_agent_core.actions import MonitorAction, ToolOutcome
from monitor_agent_core.workspace import MonitorWorkspace

from decision_question_diagnostic import (
    CallBudget, DECISION_OUTCOMES, _clone_parent_workspace, _finish_tool,
    _monitor_tool, _read_tool, _run_parent, _tool,
)


PROTOCOL_ID = "direct-frozen-evidence-query-v1"
CONDITIONS = ("specified_files", "frozen_query")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().lower()


class FrozenEvidenceIndex:
    """Read-only, hash-checked task source index derived from one checkpoint."""

    EXCLUDED_PREFIXES = (
        "task/workspace/.git/",
        "task/workspace/.github/",
        "task/workspace/verifier/",
        "task/workspace/solution/",
        "task/workspace/evaluation/",
        "task/workspace/grader/",
    )
    EXCLUDED_NAMES = {".monitor_original_task_5752c24e74b644d8a41d894bdb1f576f.txt"}

    def __init__(self, checkpoint: dict[str, Any]):
        self.root = Path(checkpoint["root"])
        self.version = str(checkpoint["complete"]["manifest_sha256"])
        declared = checkpoint["manifest"]["files"]
        self.all_task_files = {
            relative: digest.lower() for relative, digest in declared.items()
            if relative.startswith("task/")
        }
        self.source_files = {
            relative: digest for relative, digest in self.all_task_files.items()
            if relative.startswith("task/workspace/") and self._source_allowed(relative)
        }
        if not self.source_files:
            raise ValueError("frozen query scope contains no source files")

    @classmethod
    def _source_allowed(cls, relative: str) -> bool:
        if relative.startswith(cls.EXCLUDED_PREFIXES):
            return False
        name = PurePosixPath(relative).name
        return (name not in cls.EXCLUDED_NAMES
                and not name.startswith(".monitor_original_task_"))

    @staticmethod
    def _normalize(virtual_path: str) -> str:
        normalized = str(virtual_path or "").replace("\\", "/").strip("/")
        parts = PurePosixPath(normalized).parts
        if not parts or parts[0] != "task" or any(part in {".", ".."} for part in parts):
            raise PermissionError("query path must remain under task/workspace/")
        if normalized != "task/workspace" and not normalized.startswith("task/workspace/"):
            raise PermissionError("query path is outside the frozen source scope")
        return normalized

    def descriptor(self) -> dict[str, Any]:
        return {
            "scope": "task/workspace/",
            "checkpoint_version": self.version,
            "indexed_files": len(self.source_files),
            "excluded_prefixes": list(self.EXCLUDED_PREFIXES),
            "excludes_parent_private_state": True,
            "excludes_research_and_evaluation_material": True,
        }

    def _validate_query_base(self, base: str) -> None:
        if base != "task/workspace" and not self._source_allowed(
                base.rstrip("/") + "/__query_scope__"):
            raise PermissionError("path is excluded from the frozen source query scope")

    def _verify(self, relative: str) -> Path:
        expected = self.source_files.get(relative)
        if expected is None:
            raise PermissionError("path is not in the frozen source query scope")
        path = self.root / relative
        if not path.is_file() or _sha(path) != expected:
            raise OSError("frozen evidence file is missing or changed")
        return path

    def read(self, workspace: MonitorWorkspace, virtual_path: str, args: dict[str, Any]) -> dict:
        normalized = self._normalize(virtual_path)
        relative = normalized
        self._verify(relative)
        result = workspace.read_text(
            normalized, args.get("start", 1), args.get("count", 200),
            tail=args.get("tail", False), offset=args.get("offset", 0),
            max_chars=args.get("max_chars", 20000),
        )
        result.update({
            "source": "frozen_checkpoint",
            "checkpoint_version": self.version,
            "file_version": self.source_files[relative],
        })
        result["note"] = (
            "Frozen checkpoint file. Any absence claim is limited to the explicitly queried "
            "path or search scope. next_read continues this same frozen version."
        )
        return result

    def list_files(self, args: dict[str, Any]) -> dict[str, Any]:
        base = self._normalize(args.get("path", "task/workspace"))
        self._validate_query_base(base)
        recursive = args.get("recursive", False)
        if type(recursive) is not bool:
            raise ValueError("recursive must be boolean")
        contains = str(args.get("name_contains", ""))
        max_results = args.get("max_results", 200)
        if type(max_results) is not int or not 1 <= max_results <= 500:
            raise ValueError("max_results must be between 1 and 500")
        prefix = base.rstrip("/") + "/"
        entries: set[tuple[str, str]] = set()
        for relative in self.source_files:
            if not relative.startswith(prefix):
                continue
            rest = relative[len(prefix):]
            if not recursive and "/" in rest:
                child = rest.split("/", 1)[0]
                entry = (prefix + child, "directory")
            else:
                entry = (relative, "file")
            if contains and contains not in PurePosixPath(entry[0]).name:
                continue
            entries.add(entry)
        ordered = sorted(entries)
        return {
            "status": "success",
            "scope": base + ("/**" if recursive else "/*"),
            "checkpoint_version": self.version,
            "total_matches": len(ordered),
            "entries": [{"path": path, "kind": kind,
                         "file_version": self.source_files.get(path)}
                        for path, kind in ordered[:max_results]],
            "truncated": len(ordered) > max_results,
        }

    def search_text(self, args: dict[str, Any]) -> dict[str, Any]:
        query = str(args.get("query", ""))
        if not query or len(query) > 500:
            raise ValueError("query must contain 1 to 500 characters")
        base = self._normalize(args.get("path", "task/workspace"))
        self._validate_query_base(base)
        pattern = str(args.get("file_pattern", "*"))
        if not pattern or len(pattern) > 200:
            raise ValueError("file_pattern must contain 1 to 200 characters")
        case_sensitive = args.get("case_sensitive", True)
        if type(case_sensitive) is not bool:
            raise ValueError("case_sensitive must be boolean")
        max_results = args.get("max_results", 50)
        if type(max_results) is not int or not 1 <= max_results <= 200:
            raise ValueError("max_results must be between 1 and 200")
        prefix = base.rstrip("/") + "/"
        candidates = [relative for relative in sorted(self.source_files)
                      if relative == base or relative.startswith(prefix)]
        candidates = [relative for relative in candidates
                      if fnmatch.fnmatch(PurePosixPath(relative).name, pattern)
                      or fnmatch.fnmatch(relative.removeprefix("task/workspace/"), pattern)]
        needle = query if case_sensitive else query.casefold()
        matches, searched, skipped = [], 0, 0
        for relative in candidates:
            path = self._verify(relative)
            raw = path.read_bytes()
            if b"\x00" in raw:
                skipped += 1
                continue
            text = raw.decode("utf-8", errors="replace")
            searched += 1
            for line_number, line in enumerate(text.splitlines(), 1):
                haystack = line if case_sensitive else line.casefold()
                if needle in haystack:
                    matches.append({
                        "path": relative,
                        "line": line_number,
                        "text": line[:1000],
                        "file_version": self.source_files[relative],
                    })
                    if len(matches) >= max_results:
                        return self._search_result(
                            base, pattern, query, candidates, searched, skipped, matches, True)
        return self._search_result(
            base, pattern, query, candidates, searched, skipped, matches, False)

    def _search_result(self, base, pattern, query, candidates, searched, skipped,
                       matches, truncated):
        return {
            "status": "success",
            "scope": base.rstrip("/") + "/**",
            "file_pattern": pattern,
            "query": query,
            "checkpoint_version": self.version,
            "candidate_files": len(candidates),
            "searched_text_files": searched,
            "binary_files_skipped": skipped,
            "matches": matches,
            "match_count_returned": len(matches),
            "truncated": truncated,
            "absence_boundary": (
                "No returned match means no match was found only among the reported candidate "
                "files in this frozen scope; it does not establish absence outside that scope."
            ),
        }

    def dispatch(self, workspace: MonitorWorkspace, name: str,
                 args: dict[str, Any]) -> ToolOutcome | None:
        try:
            if name == "file_read":
                path = str(args.get("path", "")).replace("\\", "/")
                if path.startswith("task/workspace/") and path not in {
                        "task/workspace", "task/workspace/"}:
                    normalized = self._normalize(path)
                    if normalized not in self.source_files:
                        if self._source_allowed(normalized):
                            return ToolOutcome({
                                "status": "not_found",
                                "checked_exact_path": normalized,
                                "scope": "task/workspace/",
                                "checkpoint_version": self.version,
                            })
                        raise PermissionError("path is excluded from the frozen source query scope")
                    return ToolOutcome(self.read(workspace, path, args))
                return None
            if name == "file_list":
                return ToolOutcome(self.list_files(args))
            if name == "text_search":
                return ToolOutcome(self.search_text(args))
        except PermissionError as exc:
            return ToolOutcome({
                "status": "denied", "error": str(exc),
                "checkpoint_version": self.version,
            })
        except (TypeError, ValueError, OSError) as exc:
            return ToolOutcome({
                "status": "error", "error": str(exc),
                "checkpoint_version": self.version,
            })
        return None


def file_list_tool() -> dict[str, Any]:
    return _tool(
        "file_list",
        "List files or immediate directories in the manifest-validated frozen task/workspace source scope.",
        {
            "path": {"type": "string", "default": "task/workspace"},
            "recursive": {"type": "boolean", "default": False},
            "name_contains": {"type": "string", "default": ""},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 500,
                            "default": 200},
        },
    )


def text_search_tool() -> dict[str, Any]:
    return _tool(
        "text_search",
        "Search literal text across a declared portion of the manifest-validated frozen source scope. A no-match result applies only to the reported scope.",
        {
            "query": {"type": "string", "minLength": 1, "maxLength": 500},
            "path": {"type": "string", "default": "task/workspace"},
            "file_pattern": {"type": "string", "default": "*"},
            "case_sensitive": {"type": "boolean", "default": True},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 200,
                            "default": 50},
        },
        ("query",),
    )


def run_direct_condition(*, condition: str, parent_client, seed_workspace: MonitorWorkspace,
                         branch_private_root: Path, index: FrozenEvidenceIndex,
                         acceptance_question: str, initial_paths: tuple[str, ...],
                         parent_history: list[dict[str, Any]], parent_system: str,
                         total_calls: int = 6, audit: Callable[..., None] | None = None
                         ) -> dict[str, Any]:
    if condition not in CONDITIONS:
        raise ValueError(f"unknown direct diagnostic condition: {condition}")
    workspace = _clone_parent_workspace(seed_workspace, Path(branch_private_root) / condition)
    parent_client.restore_history(parent_history)
    budget = CallBudget(total_calls)
    allowed = {str(path).replace("\\", "/") for path in initial_paths}
    query_enabled = condition == "frozen_query"
    scope_text = ""
    extra_dispatch = None
    extra_tools: list[dict[str, Any]] = []
    if query_enabled:
        descriptor = index.descriptor()
        scope_text = (
            "\n\nAdditional evidence interface: you may list and literal-search the frozen "
            f"source scope {descriptor['scope']} ({descriptor['indexed_files']} manifest-validated "
            "files), then read discovered files. No-match claims apply only to the returned scope."
        )
        extra_dispatch = lambda name, args: index.dispatch(workspace, name, args)
        extra_tools = [file_list_tool(), text_search_tool()]
    system = (parent_system.rstrip() + "\n\n" +
        "Offline direct-investigation diagnostic: the original evidence is frozen. You may "
        "maintain optional private notes under monitor/. Online controls and code execution are "
        "unavailable. End with finish_parent_decision. A private note or failed query is not "
        "evidence that the task is complete or defective." + scope_text)
    prompt = (
        acceptance_question + "\n\nInitially named evidence paths:\n" +
        "\n".join(f"- {path}" for path in sorted(allowed)) +
        f"\n\nProtocol budget: {total_calls} logical calls remain; this stage permits at most "
        f"{total_calls} calls. End with finish_parent_decision. Tool errors and private note "
        "operations do not refund a model call. Investigate as you judge appropriate."
    )
    action = _run_parent(
        parent_client, system, prompt,
        [_read_tool(), *extra_tools, _monitor_tool("file_write"),
         _monitor_tool("file_patch"), _finish_tool()],
        workspace, allowed, budget, total_calls, "finish_parent_decision",
        audit=audit, restore_private_maintenance=True, extra_dispatch=extra_dispatch,
        receipt_protocol=PROTOCOL_ID,
    )
    payload = action.payload if isinstance(action.payload, dict) else {}
    status = ("completed" if action.kind == "finish_parent_decision" else
              "budget_or_protocol_incomplete" if action.kind == "diagnostic_incomplete" else
              "error")
    return {
        "condition": condition,
        "protocol": PROTOCOL_ID,
        "status": status,
        "action": action.kind,
        "outcome": payload.get("outcome"),
        "conclusion": payload.get("conclusion"),
        "limitation": payload.get("reason") or payload.get("detail"),
        "calls": budget.used,
        "query_scope": index.descriptor() if query_enabled else None,
    }
