"""Offline CFS rendering from frozen EIS public events and WTV path facts.

No model, task process, workspace mutation, or native verifier is started.
Historical WTV samples supply path facts; this is not a reconstructed live CFS run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from monitor_agent_core.cfs_v0 import render_surface


ROOT = Path(__file__).resolve().parent / "runs"
SOURCE = ROOT / "eis_v0_20261004" / "records"
DEST = ROOT / "cfs_v0_20261004" / "offline_replay"
RUNS = {
    "fyne_eis": "02_82b860b44c5e4bb8a81b9d01ead5703c",
    "kitex_eis": "03_3ab0193ad553424ba1a53b87fdec61e8",
}


def rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def replay_one(label, directory):
    events_path = directory / "monitor/task_evidence/public_events.jsonl"
    transitions_path = directory / "monitor/audit/workspace_transitions.jsonl"
    events = rows(events_path)
    transitions = rows(transitions_path)
    by_sequence = {row["archive_sequence"]: row for row in events}
    output = []
    for index, transition in enumerate(transitions, 1):
        before = transition["from_cursor"] if transition["from_cursor"] is not None else 0
        after = transition["to_cursor"]
        interval = [by_sequence[key] for key in sorted(by_sequence) if before < key <= after]
        latest = by_sequence.get(after)
        locator = f"offline_replay/{label}.jsonl#{index}"
        changed = {kind: transition[kind] for kind in ("added", "modified", "deleted")}
        text, outcomes = render_surface(
            baseline=before, from_cursor=before, to_cursor=after, events=interval,
            changed=changed, sample_complete=transition["sample_complete"],
            sample_errors=transition["errors"], current_event=latest, root_handoff=None,
            control=None, used_turns=transition.get("task_turn"), max_turns=300,
            remaining_seconds=None, manifest_locator=locator)
        output.append({"sample_sequence": transition["sample_sequence"],
                       "from_cursor": before, "to_cursor": after,
                       "event_locators": [f"task/public_events.jsonl#{row['archive_sequence']}"
                                          for row in interval],
                       "changed_paths": changed, "code_run_outcomes": outcomes,
                       "rendered_surface": text})
    destination = DEST / f"{label}.jsonl"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in output),
                           encoding="utf-8")
    return {"source_public_events_sha256": hashlib.sha256(events_path.read_bytes()).hexdigest(),
            "source_wtv_sha256": hashlib.sha256(transitions_path.read_bytes()).hexdigest(),
            "replay_sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
            "samples": len(output), "command_outcomes": sum(len(row["code_run_outcomes"]) for row in output),
            "changed_paths": sum(sum(len(paths) for paths in row["changed_paths"].values())
                                 for row in output)}


def main():
    # This is a deterministic derived artifact; re-rendering is safe before freeze.
    DEST.mkdir(parents=True, exist_ok=True)
    summary = {label: replay_one(label, SOURCE / subdir) for label, subdir in RUNS.items()}
    fyne = rows(DEST / "fyne_eis.jsonl")
    assert any("task/workspace/app_test.go" in row["rendered_surface"] and
               "task/workspace/test/testapp.go" in row["rendered_surface"] for row in fyne)
    kitex = rows(DEST / "kitex_eis.jsonl")
    event118 = [row for row in kitex if "task/public_events.jsonl#118" in row["event_locators"]]
    assert len(event118) == 1
    echo = [row for row in event118[0]["code_run_outcomes"]
            if row["result_event_locator"] == "task/public_events.jsonl#118"]
    assert len(echo) == 1 and "go test ./..." in echo[0]["command"]
    assert echo[0]["call_event_locator"] == "task/public_events.jsonl#117"
    assert echo[0]["result_present"]
    for record in fyne + kitex:
        identities = [row["tool_use_id"] for row in record["code_run_outcomes"]]
        assert len(identities) == len(set(identities))
    assert "validation execution" not in event118[0]["rendered_surface"].lower()
    assert "test adequate" not in event118[0]["rendered_surface"].lower()
    summary["kitex_echo_event_118"] = {
        "interval": [event118[0]["from_cursor"], event118[0]["to_cursor"]],
        "paired_code_run": True, "unique_code_run_identity": echo[0]["tool_use_id"],
        "call_event_locator": echo[0]["call_event_locator"],
        "result_event_locator": echo[0]["result_event_locator"],
        "command_contains_printed_go_test": True,
        "runtime_test_classification": "not present",
        "full_command_locator": "task/public_events.jsonl#118"}
    (DEST / "SUMMARY.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n",
                                          encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
