"""GA13 archived observation plus explicitly authored state/answers: offline only."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from .budget import TokenProxy
from .audit import AuditCodec, validate_audit_result
from .source import ContractError, SourceCatalog
from copy import deepcopy
from .engine import CycleEngine
from .source import canonical, digest
from .store import MemoryStore
from .test_contracts import empty_snapshot, leaf


ROOT = (Path(__file__).resolve().parents[1] /
        "pos_pma_shared_view_v1_20261020/raw_live_sqlite_contract_v2")
ARCHIVE = ROOT / "pos/events.host.jsonl.part001.jsonl"
TASK_REQUEST = ROOT / "spool/requests/916c033166ee4b82a4280972c60cab25.json"
CALL = "toolu_exwuJ8l8ii6K0TOkaI8jn6"


def archived_input():
    prompt = json.loads(TASK_REQUEST.read_text(encoding="utf-8"))["prompt"]
    task = prompt.split("[Task Description]\n", 1)[1].split("\n\n", 1)[0]
    assert "gcov instrumentation" in task and "PATH" in task
    action = result = None
    for number, line in enumerate(ARCHIVE.read_text(encoding="utf-8").splitlines(), 1):
        if CALL not in line:
            continue
        row = json.loads(line)
        payload = row.get("payload", {})
        if row["kind"] == "tool_started" and payload.get("id") == CALL:
            action = (number, payload)
        if row["kind"] == "tool_outcome" and payload.get("tool_use_id") == CALL:
            result = (number, payload)
    assert action[0] == 52 and result[0] == 53
    assert result[1]["result"]["exit_code"] == 127
    return task, action[1], result[1]["result"]["stdout"]


def source_witness(payload, mode):
    """Bind only to source bytes actually displayed in this audit request."""
    source = next(item for item in payload['source_catalog'] if
        item['source_id'] == 'ga13-stdout' and item['purpose'] == 'audit' and
        'sqlite3: command not found' in item['text'])
    witness = {'kind': 'source', 'ref': {'evidence_id': source['evidence_id'],
                                       'quote': 'sqlite3: command not found'}}
    if mode == 'bad_quote':
        witness['ref']['quote'] = 'sqlite3: command succeeded'
    elif mode == 'invisible_id':
        witness['ref']['evidence_id'] = 'not-visible-in-this-request'
    return witness


class GA13Provider:
    def __init__(self, mode):
        self.mode = mode
        self.calls = []
        self.proxy = TokenProxy()

    def __call__(self, role, messages, call_id, max_output):
        payload = json.loads(messages[1]["content"])
        self.calls.append({"role": role, "messages": messages,
            "call_id": call_id, "request_sha256": digest(messages),
            "size": {key: self.proxy.measure(messages)[key] for key in
                ("characters", "utf8_bytes", "proxy_tokens")}})
        if role in {"maintenance", "candidate_repair"}:
            text = ("sqlite3 command not found in this invocation" if
                self.mode == "good" or role == "candidate_repair" else
                "SQLite is available in PATH")
            original = payload["binding"] if role == "maintenance" else json.loads(
                messages[1]["content"])["binding"]
            source = next(item for item in payload["source_catalog"] if item[
                "source_id"] == "ga13-stdout" and item["purpose"] == "maintenance"
                and "sqlite3: command not found" in item["text"])
            answer = {"protocol": "maintenance-proposal/1",
                "request_id": original["request_id"],
                "active_task_version": original["active_task_version"],
                "base_state_version": original["base_state_version"],
                "world_patch": {"entity_upserts": [], "state_upserts": [{
                    "record_id": "@ga13", "revision": 1, "entity_id": "e",
                    "scope": {"task_id": "task", "entity_ids": ["e"],
                              "conditions": []},
                    "use_status": "active", "updated_at_step": 13,
                    "supersedes": [], "kind": "knowledge", "claim": {
                        "text": text, "assertion_origin": "tool_observation",
                        "time_role": "present_fact", "support_refs": [{
                            "evidence_id": source["evidence_id"],
                            "quote": "sqlite3: command not found"}],
                        "challenge_refs": []}}], "relation_upserts": [],
                    "record_transitions": []}, "specification_upserts": [],
                "gap_upserts": [], "gap_resolutions": [], "gap_reopens": [],
                "focus": {"op": "keep"}}
            raw = canonical(answer).decode("utf-8")
        elif role in {"audit", "audit_correction"}:
            issue = []
            if (self.mode in {"bad_quote", "invisible_id"} or
                    self.mode == "bad_repaired" and sum(row["role"] == "audit" for
                    row in self.calls) == 1):
                body = next(item["body"] for item in payload["added_objects"] if
                            item["body"].get("kind") == "knowledge")
                target = {"snapshot": "candidate", "target": {"kind": "state",
                    "id": body["record_id"], "revision": 1},
                    "field_path": "claim.text"}
                issue = [{"issue_id": "ga13-dev-issue", "kind": "observation_conflict",
                    "target": target, "related_targets": [],
                    "explanation": "developer fake review: displayed command-not-found receipt conflicts with PATH availability claim",
                    "witnesses": [{"kind": "field", "field": target,
                        "exact_value": body["claim"]["text"]},
                        source_witness(payload, self.mode)],
                    "repair_constraint": "limit claim to observed command result"}]
            raw = canonical({"protocol": "audit-result/1", "binding": payload[
                "binding"], "coverage": payload["required_coverage"],
                "outcome": "issues" if issue else "clean", "issues": issue,
                "closure_assessments": [], "unusable_reason": None}).decode("utf-8")
        elif role == "selection":
            raw = canonical({"decision": "silent", "state_version": payload[
                "binding"]["state_version"], "task_version": payload[
                "binding"]["task_version"], "phase2_view_id": payload[
                "binding"]["phase2_view_id"]}).decode("utf-8")
        else:
            raise AssertionError("unexpected fake role: " + role)
        self.calls[-1]["raw_response_utf8_sha256"] = hashlib.sha256(raw.encode(
            "utf-8")).hexdigest()
        self.calls[-1]["response_bytes"] = len(raw.encode("utf-8"))
        self.calls[-1]["raw_response"] = raw
        return raw


class GA13V4DevelopmentTests(unittest.TestCase):
    def test_real_observation_developer_states_and_semantic_blind_spot(self):
        task, action, stdout = archived_input()
        self.assertIn("sqlite3: command not found", stdout)
        summaries = []
        for mode in ("good", "bad_repaired", "false_clean", "bad_quote", "invisible_id"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as root:
                store = MemoryStore(Path(root) / "ga13.sqlite3")
                try:
                    user = leaf(task)
                    base = empty_snapshot()
                    user_ref = {"source_id": "u0", "start": 0,
                        "end": len(task), "quote": task}
                    base["B"]["G"]["original_user_sources"] = [user_ref]
                    store.initialize(base, user)
                    before = json.loads(json.dumps(base))
                    before["state_version"] = 1
                    before["B"]["G"]["specifications"] = [{
                        "requirement_id": "r-path", "revision": 1,
                        "task_version": 1,
                        "interpretation": "SQLite available in PATH with gcov build",
                        "source_refs": [user_ref], "status": "active",
                        "retirement": None}]
                    before["B"]["W"]["entities"] = [{"entity_id": "e",
                        "entity_type": "environment", "display_name": "workspace"}]
                    before["B"]["W"]["states"] = [{"record_id": "s-path",
                        "revision": 1, "entity_id": "e", "scope": {"task_id":
                            "task", "entity_ids": ["e"], "conditions": []},
                        "use_status": "active", "updated_at_step": 0,
                        "supersedes": [], "kind": "knowledge", "claim": {
                            "text": "PATH availability is a task requirement",
                            "assertion_origin": "user_requirement",
                            "time_role": "present_fact", "support_refs": [user_ref],
                            "challenge_refs": []}}]
                    before["B"]["DeltaA"] = [{"gap_id": "g-path", "revision": 1,
                        "task_version": 1, "gap_kind": "achievement",
                        "target": "SQLite built with gcov and available in PATH",
                        "reason": "not yet established", "goal_refs": [{
                            "type": "requirement", "requirement_id": "r-path",
                            "revision": 1, "task_version": 1}], "record_refs": [{
                                "type": "state", "record_id": "s-path",
                                "revision": 1}], "status": "open", "closure": None}]
                    store.compare_and_swap(update_id="developer-before",
                        cycle_id="developer-before", base=base, candidate=before,
                        archive_delta=[])
                    action_text = json.dumps(action["arguments"], ensure_ascii=False,
                                             sort_keys=True, separators=(",", ":"))
                    sources = []
                    for source_id, kind, field_path, text in (
                            ("ga13-action", "executed_action", "payload.arguments",
                             action_text), ("ga13-stdout", "tool_result",
                                            "payload.result.stdout", stdout)):
                        source = leaf(text, source_id=source_id, source_kind=kind)
                        source.update(event_id=CALL, event_seq=1, ga_turn=13,
                                      field_path=field_path)
                        sources.append(source)
                    store.append_event({"event_id": "ga13-development-batch",
                        "event_seq": 1, "kind": "action_batch",
                        "occurred_at_step": 13,
                        "source_ids": [item["source_id"] for item in sources],
                        "payload": {"actions": [{"tool_use_id": CALL}]}}, sources)
                    provider = GA13Provider(mode)
                    result = CycleEngine(store, provider, task_text=task).run(
                        "ga13-" + mode)
                    if mode in {"bad_quote", "invisible_id"}:
                        self.assertEqual(result['status'], 'update_unusable')
                        self.assertEqual(result['error_code'], 'quote_mismatch' if
                            mode == 'bad_quote' else 'invisible_reference')
                        self.assertEqual(store.snapshot(), before)
                        self.assertEqual([item['role'] for item in provider.calls],
                                         ['maintenance', 'audit', 'audit_correction'])
                        summaries.append({'mode': mode, 'result': result,
                                          'calls': provider.calls})
                        continue
                    self.assertEqual(result["status"], "committed_selection_silent")
                    if mode == 'bad_repaired':
                        audited = next(item for item in provider.calls if item['role'] == 'audit')
                        payload = json.loads(audited['messages'][1]['content'])
                        answer = json.loads(audited['raw_response'])
                        catalog = audit_catalog(store.sources(), payload)
                        self.assertEqual(validate_audit_result(answer, view=payload,
                            catalog=catalog)['outcome'], 'issues')
                        witness = answer['issues'][0]['witnesses'][1]['ref']
                        resolved = catalog.resolve(witness, purpose='audit')
                        self.assertEqual(resolved['source_id'], 'ga13-stdout')
                        self.assertEqual(stdout[resolved['start']:resolved['end']],
                                         'sqlite3: command not found')
                    states = store.snapshot()["B"]["W"]["states"]
                    observed = next(item for item in states if item["record_id"] !=
                                    "s-path")
                    expected = ("SQLite is available in PATH" if mode ==
                        "false_clean" else "sqlite3 command not found in this invocation")
                    self.assertEqual(observed["claim"]["text"], expected)
                    self.assertEqual(store.snapshot()["B"]["DeltaA"][0]["status"],
                                     "open")
                    self.assertNotIn("reward", provider.calls[0]["messages"][1][
                        "content"])
                    self.assertNotIn("ga13-dev-issue", provider.calls[0][
                        "messages"][1]["content"])
                    summaries.append({"mode": mode, "status": result["status"],
                        "fake_roles": [item["role"] for item in provider.calls],
                        "calls": provider.calls,
                        "requests": [{key: item[key] for key in
                            ("role", "request_sha256", "size", "response_bytes",
                             "raw_response_utf8_sha256")} for item in
                            provider.calls]})
                finally:
                    store.close()
        print(json.dumps({"fixture": "ga13_development_v4",
            "archive_sha256": hashlib.sha256(ARCHIVE.read_bytes()).hexdigest(),
            "task_request_sha256": hashlib.sha256(TASK_REQUEST.read_bytes()).hexdigest(),
            "source_call_id": CALL, "source_lines": [52, 53],
            "before_and_answers": "developer_authored_not_archived_model_state",
            "claim": "PATH claim repair wiring; every gap stays open",
            "scenarios": summaries}, sort_keys=True))


def audit_catalog(ledger, payload):
    catalog = SourceCatalog(ledger, payload['binding']['source_window_id'])
    for item in payload['source_catalog']:
        span = catalog.add(item['source_id'], item['start'], item['end'],
            item['purpose'], exact_stored_ref=item['exact_stored_ref'])
        if span.evidence_id != item['evidence_id']:
            raise AssertionError('audit source catalog identity mismatch')
    return catalog


class GA13WitnessV4Tests(unittest.TestCase):
    def test_archived_receipt_witness_parses_and_bad_witness_invalidates_whole_issue(self):
        # Tokenizer-independent parser control; full engine payload is checked above.
        task, action, stdout = archived_input()
        source = leaf(stdout, source_id='ga13-stdout', source_kind='tool_result')
        catalog = SourceCatalog({'ga13-stdout': source}, 'v4-source-control')
        span = catalog.add('ga13-stdout', 0, len(stdout), 'audit')
        before = empty_snapshot()
        candidate = deepcopy(before)
        candidate['state_version'] = 1
        candidate['B']['W']['entities'] = [{'entity_id': 'e', 'entity_type': 'tool',
                                           'display_name': 'sqlite3'}]
        view = AuditCodec().encode(before, candidate,
            binding={'source_window_id': 'v4-source-control'}, observations={},
            sources=[{'source_id': 'ga13-stdout', 'purpose': 'audit',
                      'evidence_id': span.evidence_id, 'text': stdout}],
            operation_index=[], resolve_manifest=[])
        target = {'snapshot': 'candidate', 'target': {'kind': 'entity', 'id': 'e'},
                  'field_path': 'display_name'}
        issue = {'issue_id': 'v4-control', 'kind': 'observation_conflict',
            'target': target, 'related_targets': [], 'explanation': 'developer control',
            'repair_constraint': 'retain receipt', 'witnesses': [
                {'kind': 'field', 'field': target, 'exact_value': 'sqlite3'},
                source_witness(view, 'bad_repaired')]}
        answer = {'protocol': 'audit-result/1', 'binding': view['binding'],
            'coverage': view['required_coverage'], 'outcome': 'issues', 'issues': [issue],
            'closure_assessments': [], 'unusable_reason': None}
        self.assertEqual(validate_audit_result(answer, view=view,
                                              catalog=catalog)['outcome'], 'issues')
        resolved = catalog.resolve(issue['witnesses'][1]['ref'], purpose='audit')
        self.assertEqual(resolved['source_id'], 'ga13-stdout')
        self.assertEqual(stdout[resolved['start']:resolved['end']], 'sqlite3: command not found')
        for mode, error in (('bad_quote', 'quote_mismatch'), ('invisible_id', 'invisible_reference')):
            bad = deepcopy(answer)
            bad['issues'][0]['witnesses'][1] = source_witness(view, mode)
            with self.subTest(mode=mode), self.assertRaisesRegex(ContractError, error):
                validate_audit_result(bad, view=view, catalog=catalog)
