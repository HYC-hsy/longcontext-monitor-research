"""Public-only source projection for the optional evidence gap variant.

Reuse PMAEpisode's accepted event identity and the upstream task/window boundary.
Never read provider reasoning or hidden evaluator data. This replaces only the
Phase 1 trajectory presentation; the original observation remains the P2 query.
"""
import hashlib
import json

CANDIDATE = "pma_gap_evidence_v1"


def event_identity(event):
    """A digest of an accepted public envelope is not a raw HTTP digest."""
    keys = ("event_id", "sequence", "kind", "initial_user_content", "response",
            "commands", "observation", "step_status", "actor_attempt")
    public = {key: event[key] for key in keys if key in event}
    digest = hashlib.sha256(json.dumps(public, sort_keys=True,
        ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
    return {"source_id": event["event_id"], "order": event["sequence"],
            "record_digest": digest, "record_digest_kind": "accepted_public_envelope"}


def _json_members(text, start=0):
    """Locate values in the original wrapper with the standard JSON decoder.

    Decoded strings never become decoder inputs: escapes are interpreted at
    their declared JSON field boundary only, not recursively unescaped.
    """
    decoder = json.JSONDecoder()
    cursor = start
    while text[cursor].isspace():
        cursor += 1
    if text[cursor] != "{":
        raise ValueError("expected JSON object")
    cursor += 1
    members = {}
    while True:
        while text[cursor].isspace():
            cursor += 1
        if text[cursor] == "}":
            return members
        key, cursor = decoder.raw_decode(text, cursor)
        if not isinstance(key, str) or key in members:
            raise ValueError("ambiguous JSON member")
        while text[cursor].isspace():
            cursor += 1
        if text[cursor] != ":":
            raise ValueError("expected JSON colon")
        cursor += 1
        while text[cursor].isspace():
            cursor += 1
        begin = cursor
        value, cursor = decoder.raw_decode(text, cursor)
        members[key] = (value, begin, cursor)
        while text[cursor].isspace():
            cursor += 1
        if text[cursor] == "}":
            return members
        if text[cursor] != ",":
            raise ValueError("expected JSON comma")
        cursor += 1


def _project_tool_text(add, identity, role, text, path, tool_call_id=None):
    """Adapt episode.py:360-374's known GA text fields without changing it.

    The raw parent remains registered. Only its non-body literal spans and the
    decoded children are displayed, so metadata is preserved without two bodies.
    Commands follow agent_loop.py:393-394,615-616 and ga.py:298-300.
    """
    metadata = {} if tool_call_id is None else {"tool_call_id": tool_call_id}
    children = []
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            members = _json_members(text)
            if role == "tool_observation" and "status" in payload:
                # Exact whitelist and one-level JSON decoding from episode.py.
                fields = ("stdout", "stderr", "msg", "output")
                container, prefix = members, ""
            elif role == "tool_command" and isinstance(payload.get("args"), dict):
                fields = {"code_run": ("code", "script"),
                          "file_write": ("content",),
                          "file_patch": ("old_content", "new_content")}.get(payload.get("tool_name"), ())
                container = _json_members(text, members["args"][1])
                prefix = "args/"
                if isinstance(payload.get("id"), str) and payload["id"]:
                    metadata["tool_call_id"] = payload["id"]
            else:
                fields, container, prefix = (), {}, ""
            for field in fields:
                value, begin, end = container.get(field, (None, 0, 0))
                if isinstance(value, str) and value:
                    children.append((prefix + field, value, begin, end))
    except (ValueError, TypeError, IndexError):
        # Malformed/unknown wrappers stay literal; never repair or unescape them.
        children = []
    if not children:
        add(identity, role, text, path, **metadata)
        return
    spans, cursor = [], 0
    for _, _, begin, end in sorted(children, key=lambda row: row[2]):
        if cursor < begin:
            spans.append((cursor, begin))
        cursor = end
    if cursor < len(text):
        spans.append((cursor, len(text)))
    add(identity, role, text, path, render_spans=spans, **metadata)
    for field, value, _, _ in children:
        add(identity, role, value, path + "/" + field,
            parent_field_path=path, **metadata)


def prepare_context(wrapper):
    """Snapshot the same task + recent steps as the unmodified raw formatter."""
    raw = wrapper._get_memory_agent_context()
    agent = wrapper._memory_agent
    blocks = []
    if getattr(agent, 'review_strategy', None) == 'claim-split-same-evidence-v4':
        # Same bounded task window as the source catalog; no event bodies retained.
        agent._accepted_execution_inventory = {}
    try:
        def add(identity, role, text, path, **metadata):
            if text:
                if not isinstance(text, str):
                    raise ValueError("public source text must be a string")
                blocks.append({**identity, "role": role, "text": text,
                               "field_path": path, **metadata})

        add(wrapper._evidence_task_identity, "task_instruction",
            wrapper._task_description, "initial_user_content")
        size = wrapper._sliding_window_size
        if type(size) is not int or size < 1:
            raise ValueError("invalid evidence window")
        for entry in wrapper._accumulated_observations[1:][-size:]:
            if getattr(agent, 'review_strategy', None) == 'claim-split-same-evidence-v4':
                item = entry.get('_execution_inventory')
                if item is not None:
                    agent._accepted_execution_inventory[item['event_id']] = item
            identity = entry["_evidence_identity"]
            add(identity, "agent_report", entry.get("analysis"), "response")
            for index, command in enumerate((entry.get("commands") or [])[:5]):
                _project_tool_text(add, identity, "tool_command", command, f"commands/{index}")
            observation = entry.get("observation", "")
            if not observation:
                continue
            envelope = json.loads(observation)
            if (not isinstance(envelope, dict) or
                    set(envelope) != {"content", "tool_results"} or
                    not isinstance(envelope["content"], str) or
                    not isinstance(envelope["tool_results"], list)):
                raise ValueError("unknown public observation envelope")
            # The outer actor content often repeats the already visible response.
            if envelope["content"] != entry.get("analysis"):
                add(identity, "agent_report", envelope["content"], "observation/content")
            for index, result in enumerate(envelope["tool_results"]):
                if (not isinstance(result, dict) or
                        set(result) != {"tool_use_id", "content"} or
                        not isinstance(result["tool_use_id"], str) or
                        not isinstance(result["content"], str)):
                    raise ValueError("unknown public tool result")
                _project_tool_text(add, identity, "tool_observation", result["content"],
                    f"observation/tool_results/{index}/content",
                    tool_call_id=result["tool_use_id"])
        agent.prepare_visible_context(raw, blocks)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        # Invalid evidence does not turn a valid actor event into a Task failure.
        agent.prepare_visible_context(raw, [{"source_projection_error": type(exc).__name__}])
