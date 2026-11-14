"""Independent in-memory copy of GA TXT body processing (9eddf569 llmcore.py).

GA native Prompt uses json.dumps(... ensure_ascii=False, indent=2), Response
uses resp.raw without rewriting. We retain those exact expressions and log
section delimiters. Wall-clock/model suffixes are file metadata, not added to
model evidence. No GA imports, log reads, filesystem writes or model calls.
"""
import json


def prompt_body(message):
    return json.dumps(message, ensure_ascii=False, indent=2)


def response_body(response):
    # Adapter must provide GA's raw value, never reconstruct from public_blocks.
    if not isinstance(response, str):
        raise TypeError("actual response log body must be a string")
    return response


def section(label, content):
    return f"=== {label} ===\n{content}\n\n"


def format_log_trajectory(trajectory):
    parts = []
    for event in trajectory["events"]:
        payload = event["payload"]
        if event["kind"] == "input":
            parts.append(section("Prompt", payload["log_prompt"]))
        elif event["kind"] == "assistant":
            # Old archives cannot establish raw log parity; fail rather than
            # silently substitute a public projection for a complete response.
            parts.append(section("Response", response_body(payload["log_response"])))
    return "".join(parts)


def format_step_entry(entry, *, fallback):
    """Installed only on the read-context candidate; old candidates stay intact."""
    if "public_trajectory" in entry:
        return format_log_trajectory(entry["public_trajectory"])
    return fallback(entry)
