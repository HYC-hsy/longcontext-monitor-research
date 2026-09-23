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
        "state, not a fact source or verified truth. Keep only the current decision and scope, one "
        "focal uncertainty, current grounds with their supported scope and limits, and at most one "
        "decision-critical observation status. Requested, running or interrupted observations are not "
        "positive evidence. For the current decision, ask what boundary an observation actually measured "
        "and whether blocking behavior could still exist despite the same favorable result because the "
        "distinguishing path was bypassed. Keep such a result as partial support with its boundary limit; "
        "resolve only from completed, scope-matching, decision-discriminating evidence that covers the "
        "relevant behavioral boundary. Intervention is only recovery and local resolution is not global "
        "support. At whole-task scope, resolving one focal uncertainty returns to the same root anchor for "
        "re-evaluation; replace it if another currently recognizable completion-blocking alternative "
        "remains. Once grounds are adequate, clear the dependency, prune superseded grounds and relax. "
        "Update this file only when a new observation changes future control; no write is required on "
        "every wake. Claims and summaries remain qualified as such."
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
