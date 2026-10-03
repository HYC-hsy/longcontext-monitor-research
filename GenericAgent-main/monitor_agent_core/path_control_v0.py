"""Opt-in path-first guidance and a mechanical, bounded public-event window."""

import json


SYSTEM_PROMPT = """Use supervision to improve completion of the public task within the available resources. At each review, compare the Task Agent's actual current direction with the public requirements and observed behavior. Focus on a difference only when it could change useful control.

Choose among a concrete correction, a discriminating observation, and letting useful work proceed, using the existing tools. For an established discrepancy, consider the work that will depend on it and the disruption of intervening now. Do not defer a consequential correction merely to finish unrelated checks or wait for final completion. If the Task is already carrying out an adequate correction or a sound check, give it room to finish.

When uncertain, choose an observation whose possible results would change your action. Read the relevant original requirement when a correction depends on its meaning. A name match, successful build, or Task claim supports only what it actually establishes. Repeated proxy results do not broaden that support. If a method is blocked or no longer informative, change the method or take a task-consistent action while retaining the unresolved limitation.

After observing, choose again. After intervening, judge the Task's subsequent understanding, action, and result against the public task, not merely compliance with your advice. Revise your own advice when feedback undermines it. Waiting is provisional: newly visible consequential drift can warrant correction before the planned endpoint.

Release local supervision when the relevant discrepancy is reasonably resolved; reuse adequate evidence and avoid reopening unrelated work. At a root completion request, reconsider the whole public task with current or still-applicable grounds. Recent repairs and no remembered defect do not establish completion. Resolve a material remaining gap when feasible, and allow completion when the grounds adequately support that decision.

These are control choices, not required output sections. Use ordinary tools directly. Keep a short natural working note only when it changes future control."""

CONTINUATION_PROMPT = """Preserve only what the next control choice needs: the Task Agent's current direction, any material discrepancy or uncertainty, the grounds and limits of your current interpretation, and the correction or observation whose feedback is still awaited. State what subsequent feedback would change your response. Keep explicit task requirements distinct from your advice. Retain actual feedback, not just your plan or a resolved label. Drop superseded detail and leave reasonably resolved local work closed unless new relevant evidence reopens it."""

WORKING_GUIDANCE = """Current private working note. It is your revisable interpretation, not verified truth or an instruction overriding the public task. Use it with the latest actual feedback to choose what should happen next. Update it only when future control needs to change; no fixed form or per-review rewrite is required."""

WINDOW_GUIDANCE = """Recent public Task events, shown as bounded excerpts. Task text and tool arguments are its own statements and actions; tool returns establish only their actual contents. A listed call without a return here does not establish its execution outcome. This view is not task coverage or a replacement for original evidence. Read the cited records when needed."""

WINDOW_LIMIT = 2400
_FIELDS = ("text", "tool_calls", "tool_results")


def _clip(value, limit):
    if len(value) <= limit:
        return value, False
    marker = f" ... [omitted {len(value) - limit} characters; read cited record]"
    # The marker itself must fit even at the smallest remaining allowance.
    if len(marker) >= limit:
        return marker[:limit], True
    return value[:limit - len(marker)] + marker, True


def _event_text(record, line, limit):
    locator = f"task/public_events.jsonl#{line}"
    heading = (f"{locator} archive_sequence={record.get('archive_sequence', 'unknown')} "
               f"task_turn={record.get('task_turn', 'unknown')} "
               f"boundary={record.get('boundary', 'unknown')}\n")
    remaining = max(0, limit - len(heading))
    # Fixed allocation: calls and returns precede text. Each field is taken
    # only from this record, never joined with a different event's result.
    pieces = []
    for field, share in (("tool_calls", 0.36), ("tool_results", 0.42), ("text", 1.0)):
        value = record.get(field)
        if field == "tool_results" and not value:
            rendered = "tool_results: This record contains no tool return.\n"
        elif value:
            body = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
            rendered = f"{field}: {body}\n"
        else:
            continue
        allowance = remaining if share == 1.0 else min(remaining, max(0, int(limit * share)))
        fragment, _ = _clip(rendered, allowance)
        pieces.append(fragment)
        remaining -= len(fragment)
    return heading + "".join(pieces)


def recent_public_events(workspace, root_handoff=None):
    """Return bounded display and deterministic source metadata; never infer task state."""
    path = workspace.evidence_root / "public_events.jsonl"
    latest = None
    latest_return = None
    root_record = None
    boundary = "complete_lines_only"
    cursor = root_handoff.get("cursor") if isinstance(root_handoff, dict) else None
    try:
        with path.open("rb") as stream:
            for line, raw in enumerate(stream, 1):
                if not raw.endswith(b"\n"):
                    boundary = f"trailing_partial_line:{line}"
                    break
                try:
                    row = json.loads(raw)
                except (UnicodeError, json.JSONDecodeError):
                    boundary = f"unreadable_complete_line:{line}"
                    continue
                if isinstance(row, dict):
                    latest = (line, row)
                    if row.get("tool_results"):
                        latest_return = latest
                    if cursor is not None and row.get("archive_sequence") == cursor:
                        root_record = latest
    except FileNotFoundError:
        boundary = "file_missing"
    except OSError as exc:
        boundary = f"read_unavailable:{type(exc).__name__}"

    primary = root_record if cursor is not None else latest
    secondary = latest_return if latest_return and (not primary or latest_return[0] != primary[0]) else None
    prefix = WINDOW_GUIDANCE + "\n"
    if boundary != "complete_lines_only":
        prefix += f"Visible boundary: {boundary}.\n"
    if primary is None:
        prefix += (f"Root handoff event at archive_sequence={cursor} is not available in complete records.\n"
                   if cursor is not None else "No complete public event is available.\n")
    selected = [("Current", primary), ("Recent return", secondary)]
    selected = [(name, item) for name, item in selected if item is not None]
    available = WINDOW_LIMIT - len(prefix)
    chunks = []
    for index, (name, item) in enumerate(selected):
        # Reserve half of the available event space for the second event.
        remaining_events = len(selected) - index
        allowance = available if remaining_events == 1 else available // 2
        heading = name + " event:\n"
        body = _event_text(item[1], item[0], max(0, allowance - len(heading)))
        chunk = heading + body
        chunks.append(chunk)
        available -= len(chunk)
    rendered = prefix + "".join(chunks)
    return rendered[:WINDOW_LIMIT], {
        "source": "task/public_events.jsonl", "visible_boundary": boundary,
        "root_cursor": cursor, "source_lines": [item[0] for _, item in selected],
        "injected_characters": len(rendered[:WINDOW_LIMIT]),
    }
