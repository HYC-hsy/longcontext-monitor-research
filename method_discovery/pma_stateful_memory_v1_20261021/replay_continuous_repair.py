"""Offline public-artifact replay. Never opens a provider or sends a request."""

import argparse
import hashlib
import json
from pathlib import Path

from .audit import AuditCodec, _replace_refs
from .budget import TokenProxy
from .model_output import decode_model_object
from .prompts import continuous_repair, repair
from .proposal import _local_id_map
from .source import canonical, digest


INPUT_SHA256 = "3212e3e6afdb9fba046de39ee7f4a8fe9af2a8901277996f2952471b41395541"
DEFAULT_EVENTS = Path(__file__).parent / "evidence" / \
    "live_sqlite_audit_repair_20261022" / "auxiliary_provider_events.public.jsonl"


def public_text(blocks):
    return "".join(block["text"] for block in blocks if "text" in block)


def public_messages(row):
    content = row["payload"]["content"]
    return [{"role": "system", "content": public_text(content["system"])}] + [
        {"role": item["role"], "content": public_text(item["content"])}
        for item in content["messages"]]


def replay(path):
    raw_file = Path(path).read_bytes()
    if hashlib.sha256(raw_file).hexdigest() != INPUT_SHA256:
        raise ValueError("expected the pinned public diagnostic artifact")
    rows = [json.loads(line) for line in raw_file.splitlines()]
    expected = ((60, "provider_request_ready", "stateful-maintenance"),
                (63, "provider_response_content", "stateful-maintenance"),
                (65, "provider_request_ready", "stateful-audit"),
                (68, "provider_response_content", "stateful-audit"))
    for index, event_type, branch in expected:
        if (rows[index]["event_type"], rows[index]["branch_id"]) != (event_type, branch):
            raise ValueError("unexpected public exchange identity")
    literal = public_messages(rows[60])
    body = json.loads(literal[1]["content"])
    original = [literal[0], {"role": "user", "content": canonical(body).decode()}]
    view = json.loads(public_messages(rows[65])[1]["content"])
    maint_raw = public_text(rows[63]["payload"]["parsed_visible_blocks"])
    audit_raw = public_text(rows[68]["payload"]["parsed_visible_blocks"])
    proposal = decode_model_object(maint_raw)
    assessment = decode_model_object(audit_raw)
    before_objects, after_objects = {}, {}
    for item in view["shared_objects"]:
        after_objects[item["object_ref"]] = item["body"]
        before_objects[item["object_ref"].replace("candidate:", "before:")] = item["body"]
    for item in view["changed_objects"]:
        before_objects[item["before_ref"]] = item["before_body"]
        after_objects[item["after_ref"]] = item["after_body"]
    for item in view["added_objects"]:
        after_objects[item["after_ref"]] = item["body"]
    before = _replace_refs(view["before_layout"], before_objects)
    candidate = _replace_refs(view["candidate_layout"], after_objects)
    AuditCodec().verify(view, before, candidate)
    if before != body["before_view"]:
        raise ValueError("public before views do not agree")
    mapping = _local_id_map(proposal, view["binding"]["cycle_id"])
    old = repair(original_messages=original, base=before,
        rejected={"candidate": candidate, "proposal": proposal,
                  "issues": assessment["issues"]},
        raw_response=audit_raw, error="blocking_issues", mode="replacement_proposal")
    new = continuous_repair(original_messages=original, maintenance_raw=maint_raw,
        error="blocking_issues", mode="replacement_proposal",
        local_id_map=mapping, issues=assessment["issues"])
    proxy = TokenProxy()
    measurements = {name: proxy.measure(messages) for name, messages in (
        ("literal_public_maintenance", literal), ("maintenance", original),
        ("old_repair", old), ("continuous_repair", new))}
    components = []
    previous = proxy.measure([])["proxy_tokens"]
    for index, message in enumerate(new):
        current = proxy.measure(new[:index + 1])["proxy_tokens"]
        components.append({"role": message["role"],
                           "incremental_proxy_tokens": current - previous})
        previous = current
    old_tokens = measurements["old_repair"]["proxy_tokens"]
    new_tokens = measurements["continuous_repair"]["proxy_tokens"]
    return {
        "scope": "offline reconstruction of public text; no real calls",
        "input_sha256": INPUT_SHA256,
        "measurements": measurements,
        "message_hashes": {"old": digest(old), "new": digest(new)},
        "incremental_components": components,
        "saved_proxy_tokens": old_tokens - new_tokens,
        "continuous_fits_32768": new_tokens <= 32768,
        "continuous_headroom": 32768 - new_tokens,
        "historical_maintenance_reported": 29543,
        "public_maintenance_delta": measurements["maintenance"]["proxy_tokens"] - 29543,
        "candidate_matches_recorded_private_hash":
            digest(candidate) == view["binding"]["candidate_view_hash"],
        "limitations": [
            "Public request JSON was reserialized; canonicalization is explicit.",
            "Public reconstruction differs from private original; no byte identity claim.",
            "Codec roundtrip checks public objects, not the original private candidate hash.",
            "Proxy tokens are not native model usage or proof of semantic improvement.",
            "Only this frozen failure scene is measured; no guarantee for every cycle."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(replay(args.events), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(result, encoding="utf-8")
    else:
        print(result, end="")


if __name__ == "__main__":
    main()
