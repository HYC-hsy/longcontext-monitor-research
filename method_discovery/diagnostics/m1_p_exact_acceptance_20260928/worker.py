"""One-process, no-network, exact frozen-M1 engineering trace.

Never import the current checkout's monitor_agent_core.  The parent runner
starts one fresh interpreter per condition and supplies --source explicitly.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import re
import socket
import subprocess
import sys
import tempfile

EXPECTED = "746a695adac4325d6440941d384d543d1364fef9"
MODULES = ("agent", "working_context", "loop", "provider", "workspace", "process_runner")
TASK = "Synthetic engineering fixture: inspect task/original_task.txt, maintain a scoped working note, and assess only the current completion proposal."
INITIAL = "Decision: assess the current task scope. Focal uncertainty: whether direct evidence supports completion.\n"
REVISED = "Decision: assess the current task scope. Grounds: original task was read; local evidence remains qualified.\n"
CONTINUED = "Decision: assess the current task scope. Grounds: original task read; local evidence remains qualified after maintenance.\n"

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def git(source: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()

def source_identity(source: Path) -> dict:
    source = source.resolve(strict=True)
    if git(source, "rev-parse", "HEAD") != EXPECTED:
        raise RuntimeError("source commit is not frozen M1")
    if git(source, "status", "--porcelain", "--untracked-files=no"):
        raise RuntimeError("frozen tracked source is modified")
    package = source / "GenericAgent-main" / "monitor_agent_core"
    if not package.is_dir():
        raise RuntimeError("frozen monitor_agent_core is absent")
    identity = {}
    for name in MODULES:
        relative = f"GenericAgent-main/monitor_agent_core/{name}.py"
        path = source / relative
        raw = path.read_bytes()
        blob = subprocess.check_output(["git", "-C", str(source), "show", f"HEAD:{relative}"])
        identity[name] = {"path": str(path.resolve()), "working_sha256": sha(raw),
                          "git_blob_sha256": sha(blob), "bytes_equal": raw == blob,
                          "lf_normalized_equal": raw.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n'),
                          "git_blob_id": git(source, "rev-parse", f"HEAD:{relative}")}
    return {"commit": EXPECTED, "source": str(source), "tracked_clean": True,
            "modules": identity}

def block(name: str, ident: str, **kwargs) -> list[dict]:
    return [{"type": "tool_use", "id": ident, "name": name, "input": kwargs}]

def scripted_responses():
    return [
        block("file_read", "read-task", path="task/original_task.txt"),
        block("file_write", "write-state", path="monitor/working.md", content=REVISED, mode="replace"),
        block("wait", "wait-first", after_turns=1, mode="follow"),
        block("wait", "wait-pending", after_turns=1, mode="follow"),
        block("intervene", "correct-old", message="Reconsider the old completion premise."),
        block("allow_complete", "approve-old"),
        block("wait", "wait-after-correction", after_turns=1, mode="follow"),
        block("allow_complete", "approve-new"),
    ]

def install_network_deny():
    counters = {"socket_connect_attempts": 0, "requests_attempts": 0}
    def denied_connect(*_args, **_kwargs):
        counters["socket_connect_attempts"] += 1
        raise AssertionError("offline test attempted an external socket")
    socket.socket.connect = denied_connect
    socket.socket.connect_ex = denied_connect
    socket.create_connection = denied_connect
    import requests
    def denied_request(*_args, **_kwargs):
        counters["requests_attempts"] += 1
        raise AssertionError("offline test attempted HTTP transport")
    requests.sessions.Session.request = denied_request
    return counters

def run(source: Path, mode: str, policy: Path | None) -> dict:
    if mode not in {"native", "off", "p", "fallback"}:
        raise ValueError(mode)
    identity = source_identity(source)
    source_module_root = (source / "GenericAgent-main").resolve()
    if any(name == "monitor_agent_core" or name.startswith("monitor_agent_core.") for name in sys.modules):
        raise RuntimeError("monitor_agent_core imported before frozen source selection")
    sys.path.insert(0, str(source_module_root))
    imported = {}
    for name in MODULES:
        module = importlib.import_module("monitor_agent_core." + name)
        actual = Path(module.__file__).resolve(strict=True)
        expected = (source_module_root / "monitor_agent_core" / (name + ".py")).resolve(strict=True)
        if actual != expected:
            raise RuntimeError(f"mixed import for {name}: {actual}")
        imported[name] = str(actual)
    for key, module in list(sys.modules.items()):
        if key == "monitor_agent_core" or key.startswith("monitor_agent_core."):
            path = getattr(module, "__file__", None)
            if path and not Path(path).resolve().is_relative_to(source_module_root):
                raise RuntimeError(f"mixed local dependency: {key}: {path}")
            if path:
                actual = Path(path).resolve()
                relative = actual.relative_to(source.resolve()).as_posix()
                blob = subprocess.check_output(["git", "-C", str(source), "show", f"HEAD:{relative}"])
                raw = actual.read_bytes()
                if raw.replace(b'\r\n', b'\n') != blob.replace(b'\r\n', b'\n'):
                    raise RuntimeError(f"loaded dependency differs from frozen blob: {key}")
                identity.setdefault('loaded_dependencies', {})[key] = {
                    'path': str(actual), 'working_sha256': sha(raw), 'git_blob_sha256': sha(blob),
                    'lf_normalized_equal': True}
    from monitor_agent_core.agent import MonitorAgent, MONITOR_TOOLS, MONITOR_SYSTEM_PROMPT, DCEC_SYSTEM_PROMPT, DCEC_CONTINUATION_PROMPT
    from monitor_agent_core.provider import MonitorProviderClient
    from monitor_agent_core.workspace import MonitorWorkspace

    archive_config = Path(__file__).resolve().parents[2] / "runs/dcec_v1_fyne_longrun_20260921/r1/monitor/resolved_model_config.json"
    archived = json.loads(archive_config.read_text(encoding="utf-8"))["roles"]["supervisor"]
    config = {key: archived[key] for key in ("model", "provider", "api_mode", "thinking_type",
              "reasoning_effort", "temperature", "max_tokens", "context_win", "timeout",
              "read_timeout", "max_retries", "transport_route", "stream", "endpoint_host")}
    config.update(profile=archived["profile"], apikey="offline-virtual-key",
                  apibase="https://offline.invalid", monitor_dcec=(mode != "off"),
                  monitor_semantic_continuity=True, monitor_dcec_working_chars=4000)
    if archived["profile"] != "claude_monitor_opus48":
        raise RuntimeError("unexpected supervisor profile")
    if policy is not None:
        frozen_policy = subprocess.check_output(['git', '-C', str(Path(__file__).resolve().parents[3]),
            'show', 'c6e2b35820e472b48c93ee80b36d44d7a96582e5:method_discovery/diagnostics/rp_candidate_prototypes_20260927/P_POLICY.txt'])
        if policy.read_bytes().replace(b'\r\n', b'\n') != frozen_policy.replace(b'\r\n', b'\n'):
            raise RuntimeError('P policy is not the frozen c6e2 body')
        body = policy.read_text(encoding="utf-8").strip()
        policy_hash = sha(policy.read_bytes())
    else:
        body, policy_hash = None, None
    if mode == "p" and not body:
        raise RuntimeError("P requires explicit neutral policy")
    if mode != "p" and policy is not None:
        raise RuntimeError("candidate-off cannot receive a policy")
    network = install_network_deny()
    with tempfile.TemporaryDirectory(prefix="exact-m1-offline-") as tmp:
        base = Path(tmp)
        task, private = base / "task", base / "monitor"
        (task / "workspace").mkdir(parents=True)
        private.mkdir()
        (task / "original_task.txt").write_text(TASK, encoding="utf-8")
        initial_event = {'kind': 'public_event', 'line': 1, 'text': 'Initial assessment.'}
        (task / "public_events.jsonl").write_text(json.dumps(initial_event) + '\n', encoding="utf-8")
        (private / "working.md").write_text(INITIAL, encoding="utf-8")
        workspace = MonitorWorkspace(task, private)
        client = MonitorProviderClient(archived["profile"], config)
        agent = MonitorAgent(client, workspace, max_review_turns=20)
        expected_provider_tools = client._anthropic_request(MONITOR_TOOLS)[2]['tools']
        if not agent.dcec_enabled or not agent.semantic_continuity:
            raise AssertionError("native DCEC-v1 was not enabled")
        expected_names = {"file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"}
        actual_names = {item.get("function", {}).get("name") for item in MONITOR_TOOLS}
        if len(MONITOR_TOOLS) != 7 or actual_names != expected_names:
            raise AssertionError("frozen M1 production tool schema changed")
        if getattr(client.prepare_active_context, "__self__", None) is not agent:
            raise AssertionError("native active-view hook was not installed")
        if getattr(client.prepare_continuation, "__self__", None) is not agent:
            raise AssertionError("native continuation hook was not installed")
        native_system = MONITOR_SYSTEM_PROMPT + "\n\n" + DCEC_SYSTEM_PROMPT
        if agent.system_prompt != native_system:
            raise AssertionError("native full M1 system differs from frozen source")
        if mode in {'p', 'fallback'}:
            # Explicit opt-in entry; native mode never calls this adapter.
            sys.path.insert(0, str(Path(__file__).resolve().parent))
            from experimental_adapter import apply_strategy
            apply_strategy(agent, body if mode == 'p' else None)
        events, controls, requests_log, responses_log = [initial_event], [], [], []
        pending = {"value": None}
        agent.completion_state = lambda: pending["value"]
        agent.intervention_callback = lambda message: events.append({"kind": "intervention", "message": message}) or {"status": "submitted"}
        scripted = scripted_responses()
        class FakeStreamResponse:
            status_code = 200
            def __init__(self, blocks):
                self.blocks = blocks
            def __enter__(self):
                return self
            def __exit__(self, *_args):
                self.close()
            def close(self):
                pass
            def iter_lines(self):
                events = [{'type': 'message_start', 'message': {'id': 'scripted-message', 'usage': {'input_tokens': 1}}}]
                for index, block_value in enumerate(self.blocks):
                    events.append({'type': 'content_block_start', 'index': index, 'content_block': block_value})
                    delta = ({'type': 'text_delta', 'text': block_value['text']} if block_value['type'] == 'text'
                             else {'type': 'input_json_delta', 'partial_json': json.dumps(block_value['input'])})
                    events.extend([{'type': 'content_block_delta', 'index': index, 'delta': delta},
                                   {'type': 'content_block_stop', 'index': index}])
                events.extend([{'type': 'message_delta', 'delta': {'stop_reason': 'end_turn'}, 'usage': {'output_tokens': 1}},
                               {'type': 'message_stop'}])
                for event in events:
                    yield ('data: ' + json.dumps(event)).encode('utf-8')
                    yield b''
        def fake_post(url, **kwargs):
            if not url.startswith('https://offline.invalid/'):
                network['requests_attempts'] += 1
                raise AssertionError('unexpected external target at fake transport')
            headers, payload = kwargs['headers'], kwargs['json']
            purpose = client.request_purpose if hasattr(client, "request_purpose") else "review"
            # Deep-copy at actual send boundary, before future history mutation.
            copied = json.loads(json.dumps(payload, ensure_ascii=False))
            requests_log.append({"purpose": purpose, "url": url,
                                 "headers": dict(headers), "payload": copied,
                                 "transport_options": {key: kwargs.get(key) for key in ('stream', 'timeout', 'proxies', 'verify')},
                                 "payload_sha256": sha(json.dumps(copied, ensure_ascii=False, sort_keys=True,
                                                                   separators=(",", ":")).encode("utf-8"))})
            if purpose in ("continuation", "format_repair"):
                response = [{"type": "text", "text": CONTINUED}]
            else:
                if not scripted:
                    raise AssertionError("fake response script exhausted")
                response = scripted.pop(0)
            responses_log.append({"purpose": purpose, "blocks": response, "usage": "synthetic-test-data"})
            return FakeStreamResponse(response)
        # Real _request_once, route/header assembly and stream parser remain
        # intact; only the outgoing requests.post transport is scripted.
        import requests
        requests.post = fake_post
        first = agent.review("Public event 1: initial assessment.", completion_pending=False)
        controls.append({"review": 1, "kind": first.kind, "payload": first.payload})
        if first.kind != "wait":
            raise AssertionError("first review did not wait")
        first_state = (private / "working.md").read_text(encoding="utf-8")
        # Invoke the native maintenance function with its real no-tool request.
        # This is a controlled compaction seam, not a new Agent/model stage.
        # Enter the existing compaction/continuation control path, using a
        # deterministic test seam rather than changing the history threshold.
        client._compact_with_continuation(client.history_measure())
        compaction_transforms = json.loads(json.dumps(client.history_transforms))
        continuation_note = (private / 'working.md').read_text(encoding='utf-8')
        if continuation_note != CONTINUED.strip():
            raise AssertionError(f"continuation did not preserve scripted note: {continuation_note!r}")
        events.append({"kind": "public_event", "line": 2, "text": "Task Agent proposes completion (old)."})
        with (task / "public_events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(events[-1]) + "\n")
        pending["value"] = {"generation": 1, "request_id": "proposal-old", "cursor": 2}
        second = agent.review("Public event 2: old completion proposal.", completion_pending=True)
        controls.append({"review": 2, "kind": second.kind, "payload": second.payload})
        if second.kind != "wait":
            raise AssertionError("intervention review did not return to wait")
        events.append({"kind": "public_event", "line": 3, "text": "Task Agent proposes completion again (new)."})
        with (task / "public_events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(events[-1]) + "\n")
        pending["value"] = {"generation": 2, "request_id": "proposal-new", "cursor": 3}
        third = agent.review("Public event 3: new completion proposal.", completion_pending=True)
        controls.append({"review": 3, "kind": third.kind, "payload": third.payload})
        if third.kind != "allow_complete" or third.payload.get("request_id") != "proposal-new":
            raise AssertionError("new proposal identity was not approved")
        dialogue = private / "audit" / "dialogue.jsonl"
        dialogue_rows = [json.loads(line) for line in dialogue.read_text(encoding="utf-8").splitlines()]
        progress = private / "audit" / "progress.jsonl"
        progress_rows = [json.loads(line) for line in progress.read_text(encoding="utf-8").splitlines()]
        tool_calls = [row for row in dialogue_rows if row.get("event") == "tool_call"]
        tool_results = [row for row in dialogue_rows if row.get("event") == "tool_result"]
        artifacts = {}
        for file in sorted(private.rglob('*')):
            if file.is_file():
                raw = file.read_bytes()
                artifacts[file.relative_to(private).as_posix()] = {
                    'sha256': sha(raw), 'utf8_text': raw.decode('utf-8')}
        read_results = [row for row in tool_results if row.get("tool_id") == "read-task"]
        if not read_results or read_results[0]["data"].get("content") != TASK:
            raise AssertionError("file_read did not return the frozen original task")
        request_text = json.dumps(requests_log, ensure_ascii=False)
        current_blocks = [block.get('text', '') for msg in requests_log[2]['payload']['messages']
                          for block in msg.get('content', []) if block.get('type') == 'text']
        if not any('<dcec_working_state>' in text and REVISED.strip() in text for text in current_blocks):
            raise AssertionError("DCEC active view did not expose updated working state")
        if '"tool_use_id": "read-task"' not in request_text:
            raise AssertionError("tool receipt was not consumed by a later request")
        old_approval_attempt = [row for row in tool_calls if row.get("tool_id") == "approve-old"]
        old_approval_result = [row for row in tool_results if row.get("tool_id") == "approve-old"]
        if not old_approval_attempt or not old_approval_result:
            raise AssertionError("old completion approval was not exercised")
        if "no longer current" not in json.dumps(old_approval_result, ensure_ascii=False):
            raise AssertionError("old completion proposal was not rejected by native identity guard")
        return {"mode": mode, "source_identity": identity, "imported_modules": imported,
                "runtime": {"python": sys.version, "os": platform.platform(), "shell": os.environ.get("COMSPEC") or os.environ.get("SHELL"),
                            "requests_version": __import__("requests").__version__},
                "effective_config": {**{key: value for key, value in config.items() if key != "apikey"},
                                     "review_max_turns": 20, "dcec_working_chars": 4000,
                                     "archived_config_sha256": sha(archive_config.read_bytes())},
                "virtual_credential": True, "policy_sha256": policy_hash,
                "native_system_sha256": sha(native_system.encode()),
                "native_system": native_system,
                "dcec_continuation_prompt_sha256": sha(DCEC_CONTINUATION_PROMPT.encode()),
                "tools_sha256": sha(json.dumps(MONITOR_TOOLS, ensure_ascii=False, sort_keys=True).encode()),
                "provider_tools": expected_provider_tools,
                "requests": requests_log, "scripted_responses": responses_log,
                "events": events, "controls": controls, "tool_calls": tool_calls,
                "public_events_bytes": (task / 'public_events.jsonl').read_text(encoding='utf-8'),
                "tool_results": tool_results, "progress": progress_rows,
                "old_completion_rejected": True,
                "first_working_state": first_state,
                "final_working_state": (private / "working.md").read_text(encoding="utf-8"),
                "continuation_note": continuation_note,
                "history_transforms": compaction_transforms,
                "private_artifacts": artifacts,
                "mechanical_mapping": {
                    'temp_root': str(base),
                    'history_archives': [item['archive'] for item in compaction_transforms if item.get('archive')]},
                "working_branch_commit": git(Path(__file__).resolve().parents[3], 'rev-parse', 'HEAD'),
                "captured_provider_ready_requests": len(requests_log),
                "scripted_fake_responses": len(responses_log),
                "patches": [],
                "network": network, "remaining_fake_responses": len(scripted)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--mode", choices=("native", "off", "p", "fallback"), default="native")
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.source, args.mode, args.policy)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
