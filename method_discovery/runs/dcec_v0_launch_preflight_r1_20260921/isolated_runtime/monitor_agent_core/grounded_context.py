"""Optional, one-hop restoration of private notes and their actual sources."""

import hashlib
import json
import os
import re
import tempfile
import time
import uuid
from urllib.parse import unquote


LINK = re.compile(r"\[([^\]\n]*)\]\((<[^>\n]+>|[^)\n]+)\)")
LOCATION = re.compile(r"(.+?)(?:#L([0-9]+)(?:-L?([0-9]+))?)?$")


def _atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".pending-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_with_sources(workspace, path, start=1, count=200):
    """No semantic matching, recursive expansion, or decision gating."""
    workspace.resolve_private(path)
    note = workspace.read_text(path, start, count)
    links = list(dict.fromkeys(
        (label, target.strip().strip("<>"))
        for label, target in LINK.findall(note["content"])
    ))
    key = hashlib.sha256(path.encode("utf-8")).hexdigest()
    latest = workspace.resolve_private(f"monitor/audit/source_reads/{key}/latest.json")
    previous, warnings = {}, []
    if latest.exists():
        try:
            previous = json.loads(latest.read_text(encoding="utf-8"))["observations"]
        except (OSError, ValueError, KeyError, TypeError):
            warnings.append("Previous read receipt unavailable; no change comparison is claimed.")
    if not isinstance(previous, dict):
        previous = {}
    observations, sources = dict(previous), []
    for label, target in links[:8]:
        item = {"label": label, "target": target}
        try:
            match = LOCATION.fullmatch(unquote(target))
            if not match:
                raise ValueError("Use a task/ or monitor/ path, optionally #L10-L30.")
            source_path, first, last = match.groups()
            if not source_path.startswith(("task/", "monitor/")):
                raise ValueError("Only virtual local paths are expanded; use existing tools for other sources.")
            first = int(first or 1)
            requested = int(last) - first + 1 if last else (1 if match[2] else 200)
            if first < 1 or requested < 1:
                raise ValueError("Line range must be positive and ordered.")
            current = workspace.read_text(source_path, first, min(requested, 1000))
            excerpt_hash = hashlib.sha256(current["content"].encode("utf-8")).hexdigest()
            old = previous.get(target)
            item.update(status="read", source=current,
                        excerpt_changed=None if not old else old["excerpt_sha256"] != excerpt_hash,
                        file_changed=None if not old else old["sha256"] != current["sha256"],
                        previous_read=old.get("archive") if old else None,
                        range_truncated=requested > 1000,
                        file_has_more=first + current["lines"] - 1 < current["total_lines"])
            if not current["lines"]:
                item["warning"] = "Requested lines no longer exist; locate the source again."
            observations[target] = {"sha256": current["sha256"], "excerpt_sha256": excerpt_hash}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            item.update(status="error", error=str(exc))
        sources.append(item)
    result = {
        "note": note, "sources": sources,
        "unexpanded_links": [{"label": label, "target": target} for label, target in links[8:]],
        "note_has_more": note["start"] + note["lines"] - 1 < note["total_lines"],
        "notice": "These are separate live reads, not a simultaneous snapshot. Links do not prove an "
                  "interpretation. Changes are textual, not semantic verdicts; line locations may shift. "
                  "Unchanged or first-read sources do not validate the note. Use ordinary tools as needed.",
    }
    archive = f"monitor/audit/source_reads/{key}/{uuid.uuid4().hex}.json"
    result["archive"] = archive
    result["warnings"] = warnings
    try:
        _atomic_json(workspace.resolve_private(archive), {"time": time.time(), "result": result})
        for item in sources:
            if item["status"] == "read":
                observations[item["target"]]["archive"] = archive
        _atomic_json(latest, {"observations": observations})
    except OSError as exc:
        warnings.append(f"Read succeeded but archival/checkpoint write failed: {exc}")
    return result
