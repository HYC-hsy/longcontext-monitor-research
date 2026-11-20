#!/usr/bin/env python3
"""Prepare or submit an isolated one-response Task intervention replay."""
import argparse
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from http.client import HTTPException
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

CASES = Path(__file__).with_name("cases.json")
ARMS = ("none", "generic", "paired")
GENERIC = "Before acting, cross-check your next step against the task requirements and the observations available here."
PRIVATE_BLOCK = {"type": "[PRIVATE_BLOCK_EXCLUDED]"}
PLACEHOLDER = re.compile(r"\[(?:REDACTED[A-Z_]*|PRIVATE_BLOCK_EXCLUDED|EXCLUDED_PRIVATE_FIELD)\]")


def dump(value):
    # Same canonical digest as research_runtime.payload_summary.
    return json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")


def sha(data):
    return hashlib.sha256(data).hexdigest()


def archive_events(path, spec):
    with path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != spec["archive_sha256"]:
            raise ValueError("Unexpected public archive checksum")
    cases = spec["cases"]
    found = {}
    with ZipFile(path) as archive:
        for run in dict.fromkeys(case["run"] for case in cases):
            targets = {c["event"]: c for c in cases if c["run"] == run}
            with archive.open(f"runs/{run}/task_agent/research_events.jsonl") as stream:
                round_no = 0
                for line in stream:
                    row = json.loads(line)
                    if row.get("event_type") != "provider_request_ready":
                        continue
                    round_no += 1
                    case = targets.get(row.get("event_id"))
                    if case:
                        if round_no != case["request"] or case["id"] in found:
                            raise ValueError("Unexpected request position or duplicate event")
                        if row["run_id"] != run.split("_", 1)[1]:
                            raise ValueError("Run identity mismatch")
                        found[case["id"]] = row["payload"]
    if set(found) != {c["id"] for c in cases}:
        raise ValueError("Missing pinned archive events")
    return found


def passage(body, item):
    value = body
    for key in item["field"]:
        value = value[key]
    if "json_key" in item:
        value = json.loads(value)[item["json_key"]]
    literal = item["literal"]
    if not isinstance(value, str) or value.count(literal) != 1:
        raise ValueError(f"Source excerpt is absent or ambiguous at {item['field']}")
    return value[value.index(literal):value.index(literal) + len(literal)]


def intervention(body, case, arm, *, evidence_body=None):
    if arm not in ARMS:
        raise ValueError("Unknown arm")
    out = deepcopy(body)
    if arm == "none":
        return out
    last = out["messages"][-1]
    if last["role"] != "user" or last["content"][-1]["type"] != "text":
        raise ValueError("Cannot use the pinned final user text insertion point")
    suffix = "\n\n[Reminder]\n" + GENERIC
    if arm == "paired":
        suffix += "\n\nRelevant passages already in this conversation:"
        for item in case["evidence"]:
            suffix += "\n\n" + item["label"] + ":\n" + passage(evidence_body if evidence_body is not None else body, item)
    last["content"][-1]["text"] += suffix
    return out


def full_body(payload, raw_dir, case):
    body = json.loads((raw_dir / (case["id"] + ".json")).read_bytes())
    if sha(dump(body)) != payload["sha256"]:
        raise ValueError("Private request differs from pinned original provider-request digest")
    return body


def public_normalized(body):
    out = deepcopy(body)
    # Explicit alternative protocol, not a reconstruction of private thinking.
    if out.get("thinking") != "[EXCLUDED_PRIVATE_FIELD]":
        raise ValueError("Unexpected public projection")
    for key in ("thinking", "context_management", "metadata"):
        out.pop(key, None)
    for msg in out["messages"]:
        msg["content"] = [b for b in msg["content"] if b != PRIVATE_BLOCK]
        if not msg["content"]:
            raise ValueError("Normalizing a private-only message would break context")
    return out


def schedule(cases, repeats):
    for rep in range(repeats):
        for index, case in enumerate(cases):
            order = (rep + index) % len(ARMS)
            for arm in ARMS[order:] + ARMS[:order]:
                yield case, rep + 1, arm


def put(path, content):
    with path.open("xb") as stream:
        stream.write(content)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, hdrs, newurl):
        return None


def transport(path, endpoint_hashes):
    cfg = json.loads(path.read_bytes())
    url = cfg["endpoint"]
    u = urlsplit(url)
    if (u.scheme != "https" or not u.hostname or u.username or u.password
            or u.query or u.fragment or not u.path.endswith("/messages")):
        raise ValueError("Use the original HTTPS Messages endpoint without credentials or query")
    if {sha(url.encode("utf-8"))} != endpoint_hashes:
        raise ValueError("The endpoint does not match the archived endpoint fingerprint")
    headers = cfg["headers"]
    allowed = {"anthropic-version", "anthropic-beta", "accept", "user-agent", "x-app",
               "anthropic-dangerous-direct-browser-access"}
    if (not set(headers) <= allowed or headers.get("anthropic-version") != "2023-06-01"
            or not all(isinstance(v, str) and "\r" not in v and "\n" not in v for v in headers.values())):
        raise ValueError("Supply original anthropic-version and (if used) anthropic-beta headers")
    auth_name = cfg.get("auth_header", "x-api-key")
    if auth_name not in {"x-api-key", "Authorization"}:
        raise ValueError("Unsupported authentication header")
    secret = os.environ.get("TASK_REPLAY_API_KEY")
    if not secret:
        raise ValueError("Set TASK_REPLAY_API_KEY locally")
    return url + "?beta=true", {**headers, "Content-Type": "application/json",
                 auth_name: ("Bearer " if auth_name == "Authorization" else "") + secret}


def visible_sse(data):
    blocks, stopped, provider_error = {}, False, False
    for line in data.splitlines():
        if not line.startswith(b"data:"):
            continue
        event = json.loads(line[5:].strip())
        kind = event.get("type")
        if kind == "error":
            provider_error = True
        elif kind == "message_stop":
            stopped = True
        elif kind == "content_block_start":
            b = event.get("content_block", {})
            if b.get("type") in {"text", "tool_use"}:
                blocks[event["index"]] = deepcopy(b)
        elif kind == "content_block_delta" and event["index"] in blocks:
            b = blocks[event["index"]]
            delta = event["delta"]
            if b["type"] == "text" and delta["type"] == "text_delta":
                b["text"] += delta["text"]
            elif b["type"] == "tool_use" and delta["type"] == "input_json_delta":
                b["_partial"] = b.get("_partial", "") + delta["partial_json"]
    if provider_error or not stopped:
        return ("provider_error" if provider_error else "incomplete_stream"), []
    for b in blocks.values():
        if "_partial" in b:
            b["input"] = json.loads(b.pop("_partial"))
    return "complete", [blocks[k] for k in sorted(blocks)]


def submit(wire, connection):
    url, headers = connection
    req = Request(url, wire, headers=headers, method="POST")
    try:
        with build_opener(NoRedirect()).open(req, timeout=180) as response:
            code, data = response.status, response.read(16 * 1024 * 1024 + 1)
    except HTTPError as error:
        return {"status": "http_error", "http": error.code}, error.read(1024 * 1024)
    except (URLError, OSError, HTTPException) as error:
        # Exception messages can include the private endpoint; no retries.
        return {"status": "transport_error", "error_class": type(error).__name__}, b""
    try:
        status, blocks = visible_sse(data) if len(data) <= 16 * 1024 * 1024 else ("response_too_large", [])
    except (ValueError, KeyError, TypeError):
        status, blocks = "invalid_response", []
    return {"status": status, "http": code, "visible_blocks": blocks}, data


def run(args):
    spec = json.loads(CASES.read_bytes())
    cases = spec["cases"]
    archived = archive_events(args.archive, spec)
    if args.raw_dir and args.public_normalized:
        raise ValueError("Choose exactly one request source mode")
    mode = "exact_original" if args.raw_dir else (
        "public_normalized" if args.public_normalized else "public_archive_preview")
    if args.execute and mode == "public_archive_preview":
        raise ValueError("Redacted archive payloads cannot be sent; select a supported mode")
    connection = None
    bodies = {}
    for case in cases:
        payload = archived[case["id"]]
        body = payload["content"]
        for item in case["evidence"]:
            passage(body, item)
        if args.raw_dir:
            body = full_body(payload, args.raw_dir, case)
        elif args.public_normalized:
            body = public_normalized(body)
        if args.execute and (PLACEHOLDER.search(dump(body).decode()) or body.get("stream") is not True):
            raise ValueError("Request has unresolved placeholders or is not the captured streaming protocol")
        bodies[case["id"]] = body
    if args.execute:
        connection = transport(args.transport, {a["provider_url_sha256"] for a in archived.values()})
    slots = []
    wires = []
    for i, (case, rep, arm) in enumerate(schedule(cases, args.repeats), 1):
        slot = f"{i:03d}"
        body = bodies[case["id"]]
        evidence_body = archived[case["id"]]["content"] if args.public_normalized else body
        wire = dump(intervention(body, case, arm, evidence_body=evidence_body))
        slots.append({"slot": slot, "case": case["id"], "rep": rep, "arm": arm,
                      "source_event": case["event"],
                      "source_provider_hash": archived[case["id"]]["sha256"],
                      "base_sha256": sha(dump(body)), "request_sha256": sha(wire)})
        wires.append(wire)
    # Fresh output only. No previous slots overwritten and no resume/retry.
    args.out.mkdir(mode=0o700, parents=False, exist_ok=False)
    put(args.out / "plan.json", dump({"mode": mode, "execute": args.execute,
                                             "archive_sha256": spec["archive_sha256"],
                                             "case_spec_sha256": sha(CASES.read_bytes()),
                                             "transport_config_sha256": sha(args.transport.read_bytes()) if args.transport else None,
                                             "slots": slots}))
    for row, wire in zip(slots, wires):
        put(args.out / (row["slot"] + ".request.json"), wire)
    if connection:
        for row, wire in zip(slots, wires):
            slot = row["slot"]
            started = time.monotonic()
            put(args.out / (slot + ".started"), b"Request attempt started\n")
            result, data = submit(wire, connection)
            put(args.out / (slot + ".response.bin"), data)
            put(args.out / (slot + ".result.json"), dump({**result, "slot": slot,
                                                         "elapsed_s": round(time.monotonic() - started, 3),
                                                         "response_sha256": sha(data)}))
    return len(slots), mode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--raw-dir", type=Path)
    parser.add_argument("--public-normalized", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--transport", type=Path, help="Local transport JSON (no secrets)")
    args = parser.parse_args()
    if args.execute != bool(args.transport):
        parser.error("--execute and --transport must be supplied together")
    os.umask(0o077)
    try:
        n, mode = run(args)
    except (ValueError, OSError, KeyError, TypeError, IndexError, BadZipFile) as error:
        parser.exit(2, f"Stopped: {error}\n")
    print(f"{n} slots; mode={mode}; {'executed' if args.execute else 'prepared only; zero model calls'}")


if __name__ == "__main__":
    main()
