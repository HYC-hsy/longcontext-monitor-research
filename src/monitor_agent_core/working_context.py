"""Bounded, model-owned working context; no semantic decisions or model calls."""

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
