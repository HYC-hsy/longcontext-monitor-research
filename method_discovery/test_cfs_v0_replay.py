"""Frozen historical CFS rendering vectors; no model or verifier."""

from method_discovery.cfs_v0_replay import DEST, rows


def test_fyne_source_paths_and_command_outcomes():
    records = rows(DEST / "fyne_eis.jsonl")
    assert len(records) == 9
    assert any("task/workspace/app_test.go" in row["rendered_surface"] and
               "task/workspace/test/testapp.go" in row["rendered_surface"] for row in records)
    assert any("go test ./..." in outcome["command"]
               for row in records for outcome in row["code_run_outcomes"])
    assert all("test adequate" not in row["rendered_surface"].lower()
               and "requirement covered" not in row["rendered_surface"].lower()
               for row in records)


def test_kitex_echo_event_118_is_only_code_run():
    records = rows(DEST / "kitex_eis.jsonl")
    observed = [row for row in records if "task/public_events.jsonl#118" in row["event_locators"]]
    assert len(observed) == 1 and observed[0]["from_cursor"] == 115
    calls = [row for row in observed[0]["code_run_outcomes"]
             if row["event_locator"] == "task/public_events.jsonl#118"]
    assert len(calls) == 1
    assert calls[0]["result_present"] and "go test ./..." in calls[0]["command"]
    assert "FINAL DELIVERY REPORT" in calls[0]["command"]
    assert "validation execution" not in observed[0]["rendered_surface"].lower()
