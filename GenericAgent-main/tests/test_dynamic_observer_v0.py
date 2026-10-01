"""Offline contract/assembly checks; these do not test model adoption or correctness."""

import hashlib
import json
import os
from pathlib import Path
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
SEVEN_TOOLS = ["file_read", "file_write", "file_patch", "code_run", "wait", "intervene", "allow_complete"]


def root():
    return Path(__file__).resolve().parents[2]


def git(*args):
    return subprocess.check_output(["git", "-C", str(root()), *args], text=True).strip()


def provider(dcec):
    return MonitorProviderClient("anthropic", {
        "apikey": "virtual-test", "apibase": "https://offline.invalid",
        "model": "claude-test", "max_retries": 0, "monitor_dcec": dcec,
    })


def workspace(tmp_path):
    evidence = tmp_path / "evidence"
    evidence.mkdir(parents=True)
    (evidence / "original_task.txt").write_text("A neutral public task.\n", encoding="utf-8")
    return MonitorWorkspace(evidence, tmp_path / "private")


def test_exact_parent_and_no_unreviewed_production_diff():
    head = git("rev-parse", "HEAD")
    if head == PARENT:
        pytest.skip("candidate has not yet been committed")
    parents = git("rev-list", "--parents", "-n", "1", "HEAD").split()
    assert parents == [head, PARENT]
    changed = set(git("diff", "--name-only", PARENT, head).splitlines())
    assert {p for p in changed if p.startswith("GenericAgent-main/monitor_agent_core/")} == PRODUCTION
    assert not {p for p in changed if p.startswith("GenericAgent-main/monitor_agent_core/") and p not in PRODUCTION}
    assert not {p for p in changed if p.startswith("GenericAgent-main/") and "/tests/" not in p and p not in PRODUCTION}


def test_dcec_off_full_provider_ready_equality_to_frozen_parent(tmp_path):
    """Use the real assembler in fresh interpreters and fake only external transport."""
    parent = Path(os.environ["DYNAMIC_OBSERVER_PARENT_SOURCE"]).resolve()
    assert subprocess.check_output(["git", "-C", str(parent), "rev-parse", "HEAD"], text=True).strip() == PARENT
    ws = workspace(tmp_path)
    script = r"""
import json, pathlib, sys
from monitor_agent_core.agent import MonitorAgent
from monitor_agent_core.provider import MonitorProviderClient
from monitor_agent_core.workspace import MonitorWorkspace
source = pathlib.Path(sys.argv[3]).resolve()
import monitor_agent_core.agent as agent_module
import monitor_agent_core.provider as provider_module
import monitor_agent_core.workspace as workspace_module
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
        out = subprocess.check_output(
            [sys.executable, "-c", script, str(ws.evidence_root), str(ws.private_root), str(source)],
            env=env, cwd=str(source / "GenericAgent-main"), text=True,
        )
        payload = json.loads(out.strip().splitlines()[-1])
        # Generated review identity is the sole differing field in this fixed layout.
        payload["review_id"] = "<review-id>"
        return payload

    assert capture(parent) == capture(root())  # Complete nested payload and seven production tool schemas.


def test_dcec_on_ordinary_root_and_continuation_assembly(tmp_path, monkeypatch):
    for pending in (False, True):
        ws = workspace(tmp_path / str(pending))
        ws.write_text("monitor/working.md", "Current decision: a free-form local uncertainty.")
        client = provider(True)
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
        assert "minimal measurement relation" in request["system"]
        assert "world transitions, not new positive evidence" in request["system"]
        assert [t["function"]["name"] for t in request["tools"]] == SEVEN_TOOLS
        assert request["root_handoff"] == (
            {"generation": 1, "request_id": "completion-1", "cursor": 3} if pending else None)
        assert "<dcec_working_state>" in json.dumps(request)
        assert not (ws.private_root / "ground_store.json").exists()
    assert "Historical observation remains true" in DCEC_CONTINUATION_PROMPT
    assert "temporal/source anchor" in DCEC_CONTINUATION_PROMPT


def test_dynamic_observer_semantics_are_bounded_and_non_algorithmic(tmp_path):
    view, metadata = dcec_working_context(workspace(tmp_path))
    system = " ".join(DCEC_SYSTEM_PROMPT.lower().split())
    continuation = " ".join(DCEC_CONTINUATION_PROMPT.lower().split())
    guidance = " ".join(view.split("<dcec_working_state>", 1)[0].lower().split())
    required = (
        "minimal measurement relation", "discrimination basis", "world transitions, not new positive evidence",
        "change is not invalidation", "changed direct-file hash automatically reopens",
        "unchanged direct-file hash carries", "carry it", "reopen the action-changing alternative",
        "prune it", "withhold current positive support and requalify", "different snapshots",
        "adequate transported grounds need no ceremonial retest", "consequence horizon",
        "not merely the next tool call", "same-review transient observations need no bookkeeping entry",
        "intervention starts recovery, not resolution", "unfinished observations are not positive evidence",
        "immediately recondition the evidential reference", "preserve the reference and still-compatible states",
    )
    for phrase in required:
        assert phrase in system, phrase
    assert "historical observation remains true" in continuation
    assert "withhold and requalify" in guidance
    assert "not required headings or a fixed form" in guidance
    assert metadata["limit_characters"] == 4000
    forbidden = ("ground_valid", "ground_invalid", "basis_crossed", "needs_retest",
                 "obligation_id", "support_id", "confidence score", "requirement graph")
    assert all(term not in system + continuation + guidance for term in forbidden)


@pytest.mark.parametrize("case,supported,alternative,proxy_fields", [
    ("A Fyne MainMenu.Refresh", {"rerenders": True, "symbol": True, "build": True},
     {"rerenders": False, "symbol": True, "build": True}, ("symbol", "build")),
    ("B Kitex default Framed", {"default": "Framed", "test_expects_framed": True},
     {"default": "PurePayload", "test_expects_framed": True}, ("test_expects_framed",)),
    ("E Sphinx implicit context", {"implicit_context": True, "manual_helper": True},
     {"implicit_context": False, "manual_helper": True}, ("manual_helper",)),
])
def test_paper_case_proxy_does_not_distinguish_contrast(case, supported, alternative, proxy_fields):
    """Design vectors only: a favorable proxy shared by both states cannot resolve their contrast."""
    assert supported != alternative, case
    assert all(supported[field] == alternative[field] for field in proxy_fields), case
    assert "a weaker proxy favorable in both action-divergent states is partial" in " ".join(
        DCEC_SYSTEM_PROMPT.lower().split())


def test_paper_case_c_related_rewrite_and_d_unrelated_change():
    """C crosses option wiring; D's unrelated validation edit leaves Hyperlink basis untouched."""
    c_before = {"observed_option": "constructor resolves V1", "wiring": "routes V1"}
    c_after = {"observed_option": "constructor resolves V1", "wiring": "routes V2"}
    d_before = {"hyperlink_basis": "OnTapped invokes callback", "validation": "old"}
    d_after = {"hyperlink_basis": "OnTapped invokes callback", "validation": "new"}
    assert c_before["observed_option"] == c_after["observed_option"]
    assert c_before["wiring"] != c_after["wiring"]
    assert d_before["hyperlink_basis"] == d_after["hyperlink_basis"]
    assert d_before["validation"] != d_after["validation"]
    contract = " ".join(DCEC_SYSTEM_PROMPT.lower().split())
    assert "relevant transition crossed the basis" in contract
    assert "carry it when current evidence supports the basis still applying" in contract


def test_generic_f_same_file_irrelevant_edit_does_not_force_reopen():
    before = "def a(): return control_flow()\n# old comment\ndef b(): return 1\n"
    after = "def a(): return control_flow()\n# edited comment\ndef b(): return 2\n"
    assert hashlib.sha256(before.encode()).digest() != hashlib.sha256(after.encode()).digest()
    assert before.splitlines()[0] == after.splitlines()[0]  # Stated basis unchanged.
    contract = " ".join(DCEC_SYSTEM_PROMPT.lower().split())
    assert "changed direct-file hash automatically reopens" in contract
    assert "change is not invalidation" in contract


def test_generic_g_cross_file_dependency_edit_does_not_force_carry():
    direct_before = direct_after = "def observed(): return dispatch(request)\n"
    dependency_before = "def dispatch(request): return old_route(request)\n"
    dependency_after = "def dispatch(request): return new_route(request)\n"
    assert hashlib.sha256(direct_before.encode()).digest() == hashlib.sha256(direct_after.encode()).digest()
    assert hashlib.sha256(dependency_before.encode()).digest() != hashlib.sha256(dependency_after.encode()).digest()
    contract = " ".join(DCEC_SYSTEM_PROMPT.lower().split())
    assert "unchanged direct-file hash carries" in contract
    assert "dispatch, configuration, api or wiring" in contract
