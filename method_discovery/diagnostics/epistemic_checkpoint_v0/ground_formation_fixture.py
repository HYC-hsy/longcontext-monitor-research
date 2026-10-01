"""Research-only, one-review ground-formation seeds; no transition or replay.

The task workspaces contain ordinary small software examples.  Only the
Supervisor can write its working note.  Capturing that note is mechanical and
does not certify its meaning or adequacy.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import time
from pathlib import Path

from .checkpoint import capture_checkpoint, verify_checkpoint, _tree_manifest


TASK_ROUTER = (
    "Maintain the request dispatcher. The public `handle` function should use "
    "the configured route and return the selected handler's response. The "
    "workspace includes a small demonstration that can be run locally.\n"
)
TASK_REFRESH = (
    "Maintain the view component. Calling `refresh` should update the visible "
    "rendered text to reflect the current title. The workspace includes a "
    "small demonstration that can be run locally.\n"
)
ROUTER_FILES = {
    "dispatcher.py": (
        "from wiring import resolve\n\n"
        "def handle(path):\n"
        "    handler = resolve(path)\n"
        "    return handler()\n"
    ),
    "wiring.py": (
        "def home():\n    return 'home page'\n\n"
        "def missing():\n    return 'not found'\n\n"
        "ROUTES = {'/': home}\n\n"
        "def resolve(path):\n    return ROUTES.get(path, missing)\n"
    ),
    "demo.py": "from dispatcher import handle\nprint(handle('/'))\nprint(handle('/missing'))\n",
}
REFRESH_FILES = {
    "view.py": (
        "class View:\n"
        "    def __init__(self, title):\n"
        "        self.title = title\n"
        "        self.rendered = ''\n\n"
        "    def refresh(self):\n"
        "        pass\n"
    ),
    "demo.py": (
        "from view import View\n"
        "view = View('first')\n"
        "view.refresh()\n"
        "print(repr(view.rendered))\n"
        "view.title = 'second'\n"
        "view.refresh()\n"
        "print(repr(view.rendered))\n"
    ),
}
EXTRA_FILE = "def valid_name(value):\n    return bool(value and value.strip())\n"
RESEARCH_MARKERS = (
    "case a", "case b", "case c", "related-transition", "unrelated-transition",
    "transport", "carry", "reopen", "stale", "ground", "checkpoint",
    "expected transition", "future patch", "hidden verifier",
)
FIELD_HEADINGS = ("Contrast:", "Measurement:", "Basis:", "Reach:", "Anchor:", "Transport:")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def create_workspace(kind: str, destination: Path) -> str:
    """Create an ordinary, immutable-for-this-run public task workspace."""
    if kind not in {"a", "b", "c"}:
        raise ValueError("unknown seed kind")
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=False)
    files = dict(REFRESH_FILES if kind == "c" else ROUTER_FILES)
    if kind == "b":
        files["validation.py"] = EXTRA_FILE
    for name, content in files.items():
        (destination / name).write_bytes(content.encode("utf-8"))
    task = TASK_REFRESH if kind == "c" else TASK_ROUTER
    assert not any(marker in task.lower() for marker in RESEARCH_MARKERS)
    assert not any(marker in text.lower() for text in files.values()
                   for marker in RESEARCH_MARKERS)
    return task


def eligible_boundary(*, review_finished: bool, provider_idle: bool,
                      tools_idle: bool, workspace_idle: bool,
                      observed_task_tool: bool, working_bytes: bytes) -> bool:
    """Conservative mechanical trigger, deliberately not a ground classifier."""
    return all((review_finished, provider_idle, tools_idle, workspace_idle,
                observed_task_tool, bool(working_bytes.strip())))


def capture_seed(*, checkpoint_root: Path, checkpoint_id: str,
                 workspace_root: Path, working_path: Path, history_prefix: list,
                 identities: dict, boundary: dict, boundary_probe,
                 review_finished: bool, observed_task_tool: bool) -> Path:
    before = boundary_probe()
    if not eligible_boundary(
        review_finished=review_finished,
        provider_idle=before.get("supervisor_idle") is True
        and before.get("inflight_requests") == 0,
        tools_idle=before.get("inflight_tools") == 0,
        workspace_idle=before.get("task_writes_paused") is True,
        observed_task_tool=observed_task_tool,
        working_bytes=Path(working_path).read_bytes(),
    ):
        raise ValueError("review is not an eligible idle capture boundary")
    captured = capture_checkpoint(
        checkpoint_root=checkpoint_root, checkpoint_id=checkpoint_id,
        workspace_root=workspace_root, working_path=working_path,
        history_prefix=history_prefix, identities=identities,
        boundary=boundary, boundary_probe=boundary_probe,
    )
    verify_checkpoint(captured, expected_identities=identities)
    return captured


def audit_model_input(dialogue_path: Path, forbidden: tuple[str, ...]) -> dict:
    """Scan archived provider-facing text for research metadata, not task terms."""
    checked = 0
    hits = []
    for number, raw in enumerate(Path(dialogue_path).read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(raw)
        if row.get("event") not in {"review_context", "model_input"}:
            continue
        checked += 1
        serialized = json.dumps(row, ensure_ascii=False).lower()
        for marker in forbidden:
            if marker.lower() in serialized:
                hits.append({"line": number, "marker": marker})
    return {"checked": checked, "hits": hits, "contaminated": bool(hits)}


def summarize_audit(dialogue_path: Path, working_path: Path) -> dict:
    rows = [json.loads(line) for line in Path(dialogue_path).read_text(encoding="utf-8").splitlines()]
    tools = [row for row in rows if row.get("event") == "tool_call"]
    names = sorted({row.get("name", "") for row in tools})
    working = Path(working_path).read_text(encoding="utf-8") if Path(working_path).is_file() else ""
    return {
        "supervisor_requests": sum(row.get("event") == "model_input" for row in rows),
        "tool_calls_by_type": {name: sum(row.get("name") == name for row in tools) for name in names},
        "working_mutations": sum(row.get("event") == "tool_call"
                                 and row.get("name") in {"file_write", "file_patch"}
                                 and "monitor/working.md" in str(row.get("arguments", ""))
                                 for row in rows),
        "working_final_chars": len(working),
        "field_headings": {heading: bool(re.search(rf"(?m)^\s*{re.escape(heading)}", working))
                           for heading in FIELD_HEADINGS},
        "observed_task_tool": any(row.get("name") in {"file_read", "code_run"}
                                  for row in tools),
    }


def archive_input(root: Path, task: str, workspace: Path, config: dict) -> dict:
    """Freeze public input and redacted effective config before any model call."""
    root.mkdir(parents=True, exist_ok=False)
    (root / "original_task.txt").write_bytes(task.encode("utf-8"))
    shutil.copytree(workspace, root / "initial_workspace")
    (root / "effective_config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"task_sha256": sha256_bytes(task.encode("utf-8")),
            "workspace_manifest_sha256": sha256_bytes(json.dumps(_tree_manifest(workspace),
                sort_keys=True, separators=(",", ":")).encode("utf-8"))}
