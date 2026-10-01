"""Offline assembly and contract vectors; not evidence of model adoption."""

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from monitor_agent_core.agent import DCEC_CONTINUATION_PROMPT, DCEC_SYSTEM_PROMPT, MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.working_context import dcec_working_context
from monitor_agent_core.workspace import MonitorWorkspace


PARENT = "c6f6cc8fac555b638303237b64881552e38d846b"
PRODUCTION = {
    "GenericAgent-main/monitor_agent_core/agent.py",
    "GenericAgent-main/monitor_agent_core/working_context.py",
}
TOOLS = ["file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]


def root():
    return Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", "-C", str(root()), *args], text=True).strip()


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "original_task.txt").write_text("A neutral public task.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "private")


def normalized(text):
    return " ".join(text.lower().split())


def test_sibling_topology_and_production_scope():
    head = git("rev-parse", "HEAD")
    if head == PARENT:
        pytest.skip("candidate not committed yet")
    assert git("rev-list", "--parents", "-n", "1", "HEAD").split() == [head, PARENT]
    changed = set(git("diff", "--name-only", PARENT, head).splitlines())
    assert {p for p in changed if p.startswith("GenericAgent-main/monitor_agent_core/")} == PRODUCTION
    assert not {p for p in changed if p.startswith("GenericAgent-main/") and
                "/tests/" not in p and p not in PRODUCTION}


def test_dcec_off_full_provider_ready_request_equals_parent(tmp_path):
    """Fresh interpreters import actual assemblers; only external transport is fake."""
    parent = Path(os.environ["DYNAMIC_OBSERVER_PARENT_SOURCE"]).resolve()
    assert subprocess.check_output(["git", "-C", str(parent), "rev-parse", "HEAD"],
                                   text=True).strip() == PARENT
    ws = workspace(tmp_path)
    script = r"""
import json, pathlib, sys
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
import monitor_agent_core.agent as agent_module
import monitor_agent_core.provider as provider_module
import monitor_agent_core.workspace as workspace_module
source = pathlib.Path(sys.argv[3]).resolve()
for module in (agent_module, provider_module, workspace_module):
    assert pathlib.Path(module.__file__).resolve().is_relative_to(source / 'GenericAgent-main')
client = MonitorProviderClient('anthropic', {
    'apikey': 'virtual-test', 'apibase': 'https://offline.invalid',
    'model': 'claude-test', 'max_retries': 0, 'monitor_dcec': False})
monitor = MonitorAgent(client, MonitorWorkspace(sys.argv[1], sys.argv[2]))
def fake(tools):
    print(json.dumps(client.assembled_request_snapshot(tools), sort_keys=True))
    return ([{'type': 'tool_use', 'id': 'wait-1', 'name': 'wait',
              'input': {'after_turns': 1}}], {})
client._request_once = fake
assert monitor.review('Ordinary synthetic wake.').kind == 'wait'
assert client.complete_calls == 1
"""

    def capture(source):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(source / "GenericAgent-main")
        output = subprocess.check_output(
            [sys.executable, "-c", script, str(ws.evidence_root), str(ws.private_root), str(source)],
            env=env, cwd=str(source / "GenericAgent-main"), text=True,
        )
        payload = json.loads(output.strip().splitlines()[-1])
        payload["review_id"] = "<generated-review-id>"  # Sole non-deterministic field in fixed layout.
        return payload

    parent_payload, candidate_payload = capture(parent), capture(root())
    assert parent_payload == candidate_payload  # Full nested messages, control fields and production schemas.
    assert [t["function"]["name"] for t in candidate_payload["tools"]] == TOOLS


def test_dcec_on_native_review_surface_and_bounded_state(tmp_path, monkeypatch):
    for pending in (False, True):
        ws = workspace(tmp_path / str(pending))
        ws.write_text("monitor/working.md", "Free-form current ground; no schema.")
        client = MonitorProviderClient("anthropic", {
            "apikey": "virtual-test", "apibase": "https://offline.invalid", "model": "claude-test",
            "max_retries": 0, "monitor_dcec": True,
        })
        monitor = MonitorAgent(client, ws)
        if pending:
            monitor.completion_state = lambda: {"generation": 1, "request_id": "completion-1", "cursor": 3}
        snapshots = []

        def fake(tools):
            snapshots.append(client.assembled_request_snapshot(tools))
            name = "allow_complete" if pending else "wait"
            return ([{"type": "tool_use", "id": "control", "name": name,
                      "input": {} if pending else {"after_turns": 1}}], {})

        monkeypatch.setattr(client, "_request_once", fake)
        monitor.review("Synthetic wake", completion_pending=pending)
        assert client.complete_calls == len(snapshots) == 1
        request = snapshots[0]
        assert "decision-critical measurement" in request["system"]
        assert [t["function"]["name"] for t in request["tools"]] == TOOLS
        assert request["root_handoff"] == (
            {"generation": 1, "request_id": "completion-1", "cursor": 3} if pending else None)
        assert "<dcec_working_state>" in json.dumps(request)
        assert not (ws.private_root / "ground_store.json").exists()


def test_compressed_contract_preserves_observer_and_ader_invariants(tmp_path):
    view, metadata = dcec_working_context(workspace(tmp_path))
    system = normalized(DCEC_SYSTEM_PROMPT)
    continuation = normalized(DCEC_CONTINUATION_PROMPT)
    guidance = normalized(view.split("<dcec_working_state>", 1)[0])
    required_system = (
        "evidential reference", "action-relevant information state", "consequence horizon",
        "decision-critical measurement", "navigation, file finding and cheap reconnaissance need no such precondition",
        "favorable result substantially unchanged", "discrimination basis", "one focal residual gap",
        "no recognized defect is not evidence", "public reference", "change the scheme, not the contrast",
        "world transitions, not positive evidence", "carry an old ground", "reopen the alternative",
        "without denying the historical observation", "prune it when irrelevant", "withhold current positive support",
        "change is not invalidation", "changed direct-file hash does not automatically reopen",
        "unchanged direct-file hash does not automatically carry", "unrelated changes permit carry",
        "not favorable labels summed across snapshots", "without ceremonial retest", "mid-review",
        "unfinished observation is not positive evidence", "intervention starts recovery, not resolution",
        "local evidence resolves only local scope", "prune superseded grounds and relax",
    )
    for phrase in required_system:
        assert phrase in system, phrase
    assert "same-review transient observations need no bookkeeping entry" in system
    assert "no gap" in continuation and "not chronology, a ledger or a fixed form" in continuation
    assert "transient observations merely for bookkeeping" in guidance
    assert "no fixed headings or schema" in guidance
    assert metadata["limit_characters"] == 4000
    combined = system + continuation + guidance
    for forbidden in ("ground_valid", "ground_invalid", "basis_crossed", "needs_retest",
                      "obligation_id", "support_id", "confidence score", "requirement graph"):
        assert forbidden not in combined, forbidden
    assert not re.search(r"(?im)^\s*(contrast|measurement|basis|reach|anchor):", "\n".join(
        (DCEC_SYSTEM_PROMPT, DCEC_CONTINUATION_PROMPT, view)))


@pytest.mark.parametrize("case,good,bad,proxy", [
    ("A Fyne rerender", {"rerenders": True, "symbol": True, "build": True},
     {"rerenders": False, "symbol": True, "build": True}, ("symbol", "build")),
    ("B Kitex default", {"default": "Framed", "test_expects": True},
     {"default": "PurePayload", "test_expects": True}, ("test_expects",)),
    ("E Sphinx implicit context", {"implicit": True, "helper": True},
     {"implicit": False, "helper": True}, ("helper",)),
])
def test_paper_proxy_vectors_are_not_discriminating(case, good, bad, proxy):
    assert good != bad, case
    assert all(good[key] == bad[key] for key in proxy), case
    assert "favorable result substantially unchanged" in normalized(DCEC_SYSTEM_PROMPT)


def test_paper_transport_vectors_c_and_d():
    c_old, c_new = {"observed": "option V1", "wiring": "route V1"}, {"observed": "option V1", "wiring": "route V2"}
    d_old, d_new = {"basis": "callback flow", "validation": "old"}, {"basis": "callback flow", "validation": "new"}
    assert c_old["observed"] == c_new["observed"] and c_old["wiring"] != c_new["wiring"]
    assert d_old["basis"] == d_new["basis"] and d_old["validation"] != d_new["validation"]
    contract = normalized(DCEC_SYSTEM_PROMPT)
    assert "transition crossed it" in contract and "unrelated changes permit carry" in contract


def test_generic_f_same_file_irrelevant_edit_changes_hash_not_basis():
    old = "def a(): return control_flow()\n# old\ndef b(): return 1\n"
    new = "def a(): return control_flow()\n# edited\ndef b(): return 2\n"
    assert hashlib.sha256(old.encode()).digest() != hashlib.sha256(new.encode()).digest()
    assert old.splitlines()[0] == new.splitlines()[0]
    assert "changed direct-file hash does not automatically reopen" in normalized(DCEC_SYSTEM_PROMPT)


def test_generic_g_external_dependency_changes_without_direct_hash_change():
    direct_old = direct_new = "def observed(): return dispatch(request)\n"
    external_old = "def dispatch(request): return old_route(request)\n"
    external_new = "def dispatch(request): return new_route(request)\n"
    assert hashlib.sha256(direct_old.encode()).digest() == hashlib.sha256(direct_new.encode()).digest()
    assert hashlib.sha256(external_old.encode()).digest() != hashlib.sha256(external_new.encode()).digest()
    assert "unchanged direct-file hash does not automatically carry" in normalized(DCEC_SYSTEM_PROMPT)
