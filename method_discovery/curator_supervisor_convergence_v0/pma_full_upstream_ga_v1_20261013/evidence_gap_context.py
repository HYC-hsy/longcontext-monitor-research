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


def prepare_context(wrapper):
    """Snapshot the same task + recent steps as the unmodified raw formatter."""
    raw = wrapper._get_memory_agent_context()
    agent = wrapper._memory_agent
    blocks = []
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
            identity = entry["_evidence_identity"]
            add(identity, "agent_report", entry.get("analysis"), "response")
            for index, command in enumerate((entry.get("commands") or [])[:5]):
                add(identity, "tool_command", command, f"commands/{index}")
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
                # One raw tool-content body. Do not also emit decoded stdout copies.
                # The accepted event + exact field path locates the original
                # tool_use_id; no command/result pairing is guessed from order.
                add(identity, "tool_observation", result["content"],
                    f"observation/tool_results/{index}/content",
                    tool_call_id=result["tool_use_id"])
        agent.prepare_visible_context(raw, blocks)
    except (ValueError, TypeError, KeyError, AttributeError) as exc:
        # Invalid evidence does not turn a valid actor event into a Task failure.
        agent.prepare_visible_context(raw, [{"source_projection_error": type(exc).__name__}])
