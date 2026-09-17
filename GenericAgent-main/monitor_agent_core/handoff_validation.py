"""Optional same-session draft verification before a capacity handoff is committed."""

from __future__ import annotations

import hashlib
import json
import time
import uuid

from .provider import is_reasoning_echo


VERIFY_PROMPT = """Review the proposed memory handoff against the original task below, your existing
working note, and the dialogue still present above. The draft is not yet committed. Return only the
complete replacement note for your future self, retaining useful inferences as inferences rather than
silently promoting them into task requirements. Repair lost requirements, unsupported completion claims,
or stale reasoning when the available evidence warrants it. Preserve useful new understanding and
uncertainty; do not merely copy the old note or erase conclusions just because they require inference.
This is a memory handoff, not another task review or a request for new work from the Task Agent.
No fixed fields, identifiers, pass/fail declaration, or explanation outside the replacement note is needed.
Some earlier tool outputs may have been archived: do not infer their missing contents from excerpts.
If available material cannot settle something, preserve the uncertainty and its location for later inquiry.
"""


class ContinuationContractError(ValueError):
    """Stable, content-free reason suitable for diagnostic telemetry."""
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def note_text(blocks):
    if any(block.get("type") == "tool_use" for block in blocks):
        raise ContinuationContractError('unexpected_tool', "Continuation unexpectedly requested a tool")
    text = "\n".join(block.get("text", "") for block in blocks
                     if block.get("type") == "text").strip()
    if not text:
        raise ContinuationContractError('empty_note', "Empty continuation; keeping original history")
    if is_reasoning_echo(text, blocks):
        raise ContinuationContractError('reasoning_echo', "Continuation duplicates reasoning summary; keeping original history")
    return text


def validate_handoff(monitor, draft, previous):
    """One verification request, same client/model/history; no semantic engine or actions.

    Archive the draft and comparison inputs before paying. The caller commits only
    the returned note. Exceptions leave its prior working note/history untouched.
    """
    client = monitor.client
    task = monitor.workspace.resolve_read("task/original_task.txt").read_text(encoding="utf-8")
    transaction = uuid.uuid4().hex
    root = "audit/handoff_validation/" + transaction
    original_size = len(client.history)
    started = time.time()
    comparison = VERIFY_PROMPT + "\nOriginal task:\n" + task + "\nPrevious working note:\n" + previous
    context = getattr(client, "continuation_context", None)
    if context:
        comparison += ("\nPlanned retirement: the first " + str(context["retired_messages"])
                       + " history messages. Full pre-handoff history is archived at "
                       + context["archive"] + ". Remaining recent dialogue is retained verbatim.")
    monitor._atomic_private_text(root + "/draft.md", draft)
    monitor._atomic_private_text(root + "/comparison.txt", comparison)
    monitor._atomic_private_text(root + "/context.json", json.dumps({
        "review_id": monitor.review_id, "history": client.history_measure(),
        "retirement": context, "task_sha256": hashlib.sha256(task.encode("utf-8")).hexdigest(),
        "started_at": started,
    }, ensure_ascii=False))
    monitor._progress("handoff_validation_started", transaction=transaction)
    try:
        client.history.extend([
            {"role": "assistant", "content": [{"type": "text", "text": draft}]},
            {"role": "user", "content": [{"type": "text", "text": comparison}]},
        ])
        blocks, usage = client._request([])
        client.usage_records.append(dict(usage, purpose="handoff_validation", transaction=transaction))
        monitor._atomic_private_text(root + "/response.json", json.dumps(blocks, ensure_ascii=False))
        result = note_text(blocks)
        monitor._atomic_private_text(root + "/validated.md", result)
        monitor._progress("handoff_validation_finished", transaction=transaction,
                          changed=result != draft, duration_seconds=time.time() - started)
        return result
    except Exception as exc:
        monitor._progress("handoff_validation_failed", transaction=transaction,
                          error_type=type(exc).__name__, duration_seconds=time.time() - started)
        raise
    finally:
        del client.history[original_size:]
