"""Frozen historical CFS rendering vectors; no model or verifier."""

import json

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
             if row["result_event_locator"] == "task/public_events.jsonl#118"]
    assert len(calls) == 1
    assert calls[0]["result_present"] and "go test ./..." in calls[0]["command"]
    assert calls[0]["call_event_locator"] == "task/public_events.jsonl#117"
    assert "FINAL DELIVERY REPORT" in calls[0]["command"]
    assert "validation execution" not in observed[0]["rendered_surface"].lower()


def test_each_replay_interval_contains_unique_code_run_identities():
    for name in ("fyne_eis", "kitex_eis"):
        for record in rows(DEST / f"{name}.jsonl"):
            outcomes = record["code_run_outcomes"]
            identities = [row["tool_use_id"] for row in outcomes]
            assert len(identities) == len(set(identities))
            assert all(row["result_event_locator"] is not None or
                       row["status"] == "no_return_in_interval" for row in outcomes)


def test_real_fyne_and_kitex_pairs_split_at_observed_cursor():
    split = json.loads((DEST / "SPLIT_BOUNDARY_REPLAY.json").read_text(encoding="utf-8"))
    for label, call_cursor, result_cursor in (("kitex_117_118", 117, 118),
                                               ("fyne_53_54", 53, 54)):
        first, second = split[label]["surfaces"]
        assert first["to_cursor"] == call_cursor
        assert second["from_cursor"] == call_cursor
        assert second["to_cursor"] == result_cursor
        assert len(first["code_run_outcomes"]) == len(second["code_run_outcomes"]) == 1
        call = first["code_run_outcomes"][0]
        result = second["code_run_outcomes"][0]
        assert call["tool_use_id"] == result["tool_use_id"]
        assert call["status"] == "no_return_in_interval" and not call["result_present"]
        assert f"task/public_events.jsonl#{result_cursor}" not in first["rendered_surface"]
        assert result["call_event_locator"] == f"task/public_events.jsonl#{call_cursor}"
        assert result["result_event_locator"] == f"task/public_events.jsonl#{result_cursor}"
        assert result["command"] == call["command"]
        assert result["status"] == "success" and result["result_present"]
        assert call["call_conflicts"] == result["call_conflicts"] == []
        assert "1 unique tool identities" in second["rendered_surface"]
        assert "validation execution" not in second["rendered_surface"].lower()
    assert "go test ./..." in split["kitex_117_118"]["surfaces"][1]["code_run_outcomes"][0]["command"]
