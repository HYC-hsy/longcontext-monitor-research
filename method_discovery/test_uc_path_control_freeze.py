"""Zero-model checks for the frozen four-slot path-control deployment inputs."""

import json
from pathlib import Path

import pytest

from method_discovery.uc_path_control_entry import (
    MANIFEST, PLAN, load_authorized_slot,
)
from method_discovery.uc_r5_execution_bridge import file_sha


EXPECTED = (
    ("fyn-2.2.0-roadmap", "BASE", "cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080"),
    ("fyn-2.2.0-roadmap", "PATH", "cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080"),
    ("ktx-0.13.0-roadmap", "PATH", "c5fac1db423182fadeb24dac34259f61a22b993ee974a8a9e3a24d690952b61d"),
    ("ktx-0.13.0-roadmap", "BASE", "c5fac1db423182fadeb24dac34259f61a22b993ee974a8a9e3a24d690952b61d"),
)


def test_four_slots_and_authorization_are_exact_and_fresh():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert plan["execution_authorized"] is False
    assert manifest["secrets_included"] is False
    assert len(plan["slots"]) == len(manifest["runs"]) == 4
    assert plan["run_order"] == [s["run_id"] for s in plan["slots"]]
    assert len(set(plan["run_order"])) == 4
    for row, expected, run in zip(plan["slots"], EXPECTED, manifest["runs"]):
        task_id, condition, input_sha = expected
        assert row["runner"]["task_id"] == task_id
        assert row["condition"] == condition
        assert row["task_identity"]["actual_task_input_sha256"] == input_sha
        assert row["task_identity"]["monitor_original_task_sha256"] == input_sha
        assert row["status"] == "not_started"
        assert not Path(row["live_root"]).exists()
        assert run["run_id"] == row["run_id"]
        env = run["environment"]
        assert env["GA_MAX_TURNS"] == "180"
        assert env["GA_MONITOR_DCEC_WORKING_CHARS"] == "4000"
        assert env["GA_BASELINE_CONDITION"] == "original"
        assert env["GA_HOST_ROOT"] == row["deployment"]["ga_host_root"]
        auth = PLAN.parent / f"AUTH_{row['run_id']}.json"
        assert load_authorized_slot(row["run_id"], auth)[0] == row
    assert file_sha(PLAN) == json.loads((PLAN.parent / f"AUTH_{plan['run_order'][0]}.json").read_text())["plan_sha256"]


def test_same_code_and_only_profile_switch_differs():
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    deployments = {row["condition"]: row["deployment"] for row in plan["slots"]}
    assert deployments["BASE"]["ga_source_tree_hash_runner_scope"] == deployments["PATH"]["ga_source_tree_hash_runner_scope"]
    profiles = {name: json.loads(Path(value["monitor_profile_path"]).read_text(encoding="utf-8"))
                for name, value in deployments.items()}
    base = profiles["BASE"]["claude_monitor_opus48"]
    path = profiles["PATH"]["claude_monitor_opus48"]
    assert base["monitor_path_control_v0"] is False
    assert path["monitor_path_control_v0"] is True
    assert {k: v for k, v in base.items() if k != "monitor_path_control_v0"} == {
        k: v for k, v in path.items() if k != "monitor_path_control_v0"}
    assert base["monitor_dcec"] is True
    assert base.get("monitor_research_view", "off") == base.get("monitor_research_intent", "off") == "off"
    for value in deployments.values():
        assert file_sha(Path(value["monitor_profile_path"])) == value["monitor_profile_sha256"]


def test_unauthorized_or_mismatched_auth_fails(tmp_path):
    plan = json.loads(PLAN.read_text(encoding="utf-8"))
    run_id = plan["run_order"][0]
    source = json.loads((PLAN.parent / f"AUTH_{run_id}.json").read_text(encoding="utf-8"))
    source["execution_authorized"] = False
    changed = tmp_path / "authorization.json"
    changed.write_text(json.dumps(source), encoding="utf-8")
    with pytest.raises(RuntimeError):
        load_authorized_slot(run_id, changed)
