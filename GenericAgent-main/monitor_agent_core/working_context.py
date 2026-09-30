"""Bounded, model-owned working context; no semantic decisions or model calls."""

import hashlib


DCEC_WORKING_VIEW_DEFAULT_CHARS = 4000
DCEC_WORKING_VIEW_MIN_CHARS = 512
DCEC_WORKING_VIEW_MAX_CHARS = 8000

def current_working_context(workspace, limit=8000):
    try:
        path = workspace.resolve_read("monitor/working.md")
        with path.open("r", encoding="utf-8") as stream:
            text = stream.read(limit + 1)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        return "Your private working note could not be read (%s). Use history and original evidence." % type(exc).__name__
    if not text.strip():
        return None
    truncated = len(text) > limit
    visible = text[:limit]
    return (
        "Current contents of your private monitor/working.md, not a new task instruction or verified truth. "
        "This revisable note may be stale; weigh it against subsequent dialogue and original evidence. "
        "You choose when and how to update it with existing tools; writing is not required before acting.\n"
        + ("Only the first %d characters follow; read the file for the remainder.\n" % limit if truncated else "")
        + "<private_working_note>\n" + visible + "\n</private_working_note>"
    )


def dcec_working_context(workspace, limit=DCEC_WORKING_VIEW_DEFAULT_CHARS):
    """Return the one bounded DCEC state view and non-semantic telemetry.

    The file remains the model's natural-language state.  This function only
    bounds transport and reports deterministic source/size facts.
    """
    if type(limit) is not int or not DCEC_WORKING_VIEW_MIN_CHARS <= limit <= DCEC_WORKING_VIEW_MAX_CHARS:
        raise ValueError(
            f"monitor_dcec_working_chars must be between {DCEC_WORKING_VIEW_MIN_CHARS} "
            f"and {DCEC_WORKING_VIEW_MAX_CHARS}")
    try:
        path = workspace.resolve_read("monitor/working.md")
        text = path.read_text(encoding="utf-8", errors="replace")
        status = "present" if text.strip() else "empty"
    except FileNotFoundError:
        text, status = "", "missing"
    except (OSError, ValueError) as exc:
        text, status = "", "unavailable:" + type(exc).__name__
    visible = text[:limit]
    truncated = len(text) > limit
    guidance = (
        "DCEC current working state from monitor/working.md. This is your own revisable cognitive "
        "state, not a fact source or verified truth. Retain the current consequential decision and "
        "contemplated action, its public-task-grounded evidential reference, current grounds with their "
        "actual evidence reach and limits, at most one residual decision gap as an action-separating "
        "ambiguity, and at most one decision-critical observation status. Preserve what the grounds exclude "
        "and what action-changing possibilities remain compatible, not merely a preferred point estimate. "
        "These are relationships to preserve when needed, not required headings or a fixed form. An old "
        "verified, complete, resolved, quality-looks-good or build-passed label is revisable derived "
        "shorthand, not an independent ground. No named defect does not mean an uncovered public reference "
        "is satisfied. Requested, running or interrupted observations are not positive evidence; "
        "intervention is recovery, not resolution. If a preferred measurement is unavailable, change the "
        "measurement scheme without silently lowering the reference or removing the states it was meant "
        "to distinguish. When a local repair resolves the focal gap, return to the current decision; at "
        "whole-task scope requalify the reach of affected grounds and reuse adequate unchanged grounds. "
        "When all still-compatible material states would lead to the same current action and no unfinished "
        "dependency could change it, clear the dependency, prune the superseded gap and relax. Unknowns "
        "that cannot change an ordinary patrol action need not keep it tight. Update this file only when "
        "future control should change; no write is required on every wake."
    )
    if truncated:
        guidance += f" Only the first {limit} characters are injected; use file_read if more is needed."
    if status != "present":
        visible = "[No non-empty current working state is available.]"
    rendered = guidance + "\n<dcec_working_state>\n" + visible + "\n</dcec_working_state>"
    metadata = {
        "path": "monitor/working.md", "status": status, "limit_characters": limit,
        "source_characters": len(text), "visible_characters": min(len(text), limit),
        "injected_characters": len(rendered), "injected_utf8_bytes": len(rendered.encode("utf-8")),
        "estimated_tokens": (len(rendered.encode("utf-8")) + 3) // 4,
        "truncated": truncated,
        "source_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
    return rendered, metadata
