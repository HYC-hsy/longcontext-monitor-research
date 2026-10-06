"""Post-termination mechanical raw archive and measurement trace locator index."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import tarfile

from method_discovery import uc_path_control_archive as raw
from method_discovery.curator_supervisor_convergence_v0.fyne_gate_candidate_r2 import archive_result as prior


RUN_ID = "curator-supervisor-fyne-measurement-v01-r1-infra-replacement"
ROOT = Path(__file__).resolve().parent
CAMPAIGN = Path(r"E:\LongContext\long_context_bench\output\curator_supervisor_fyne_measurement_v01")
DESTINATION = ROOT / "archive" / "r1"
STAGING = Path(r"E:\cs_fyne_archive_stage")
EXTRACTION = Path(r"E:\curator_fyne_measurement_v01_private_20261006\final_workspace_extract_replacement")


def recover_long_path_copies() -> None:
    """Recover source files beyond Windows MAX_PATH; preserve original bytes."""
    manifest_path = DESTINATION / "RAW_FILE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in manifest["copied"]:
        if record.get("status") not in ("missing", "absent"):
            continue
        source = Path(record["source"])
        if not source.is_absolute():
            continue
        extended_source = Path("\\\\?\\" + str(source))
        if not extended_source.is_file():
            continue
        target = DESTINATION / record["archive"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(extended_source, target)
        if raw.digest(extended_source) != raw.digest(target):
            raise RuntimeError(f"Long-path copy hash mismatch: {record['archive']}")
        record.update(status="copied", bytes=target.stat().st_size,
                      sha256=raw.digest(target))
        record.pop("reason", None)
    raw.write(manifest_path, manifest)


def rows(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def tool_arguments(event: dict) -> dict:
    value = event.get("arguments")
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {"raw_arguments": value}
        except json.JSONDecodeError:
            return {"raw_arguments": value}
    return {}


def event_locator(line_number: int) -> str:
    return f"monitor/audit/dialogue.jsonl#{line_number}"


def measurement_index() -> None:
    dialogue = rows(DESTINATION / "monitor/audit/dialogue.jsonl")
    progress = rows(DESTINATION / "monitor/audit/progress.jsonl")
    reviews = rows(DESTINATION / "monitor/audit/reviews.jsonl")
    public = rows(DESTINATION / "monitor/task_evidence/public_events.jsonl")
    starts = [row for row in progress if row.get("event") == "review_started"]
    if len(starts) != len(reviews):
        raise RuntimeError("Cannot pair review starts with completed reviews")
    indexed = {}
    for line, event in enumerate(dialogue, 1):
        indexed.setdefault(event.get("review_id"), []).append((line, event))
    result = []
    for ordinal, (start, review) in enumerate(zip(starts, reviews), 1):
        review_id = start["review_id"]
        events = indexed.get(review_id, [])
        surfaces = [(line, event) for line, event in events
                    if event.get("event") == "supervisory_situation_surface"]
        manifests = []
        for line, event in surfaces:
            locator = event.get("manifest_locator")
            if not isinstance(locator, str):
                continue
            path = DESTINATION / locator
            if path.is_file():
                manifests.append((line, locator, json.loads(path.read_text(encoding="utf-8"))))
        turns = [turn for _, _, manifest in manifests
                 for turn in manifest.get("task_turns", []) if isinstance(turn, int)]
        latest = manifests[-1][2] if manifests else {}
        latest_locator = latest.get("current_event_locator")
        latest_public = None
        if isinstance(latest_locator, str) and "#" in latest_locator:
            try:
                event_number = int(latest_locator.rsplit("#", 1)[1])
            except ValueError:
                event_number = 0
            if 1 <= event_number <= len(public):
                task_event = public[event_number - 1]
                text = str(task_event.get("text") or "")
                latest_public = {
                    "locator": latest_locator,
                    "task_turn": task_event.get("task_turn"),
                    "text_sha256": sha(text.encode("utf-8")),
                    "text_characters": len(text),
                    "exact_public_synopsis": task_event.get("synopsis"),
                    "claimed_evidence_extraction": "not_attempted_no_semantic_parser",
                }
        calls = []
        for line, event in events:
            if event.get("event") != "tool_call":
                continue
            name = event.get("name")
            if name in ("file_read", "code_run", "intervene"):
                calls.append({"locator": event_locator(line), "name": name,
                              "arguments": tool_arguments(event), "model_turn": event.get("turn")})
        situation_outcomes = [outcome for _, _, manifest in manifests
                              for outcome in manifest.get("code_run_outcomes", [])]
        entry = {
            "review_ordinal": ordinal,
            "review_id": review_id,
            "frame": review.get("frame"),
            "completion_pending": start.get("completion_pending"),
            "task_turn_interval": [min(turns), max(turns)] if turns else None,
            "public_cursor_interval": [manifests[0][2].get("from_cursor"),
                                       latest.get("shown_through_cursor")] if manifests else None,
            "situation_manifest_locators": [locator for _, locator, _ in manifests],
            "most_recent_public_task_statement": latest_public,
            "supervisor_file_reads": [call for call in calls if call["name"] == "file_read"],
            "supervisor_code_runs": [call for call in calls if call["name"] == "code_run"],
            "supervisor_interventions": [call for call in calls if call["name"] == "intervene"],
            "task_book_mutations": [dict(event, locator=event_locator(line)) for line, event in events
                                    if event.get("event") == "curator_task_book_mutated"],
            "echo_visible_submission_ids": [event.get("submission_id") for _, event in events
                                            if event.get("event") == "curator_echo_surface_injected"],
            "echo_consumed_submission_ids": [event.get("submission_id") for _, event in events
                                             if event.get("event") == "curator_echo_consumed"],
            "terminal_action": review.get("action"),
        }
        if review.get("frame") == "root" or start.get("completion_pending"):
            entry["completion_mechanics"] = {
                "root_handoff_events": [dict(event, locator=event_locator(line)) for line, event in events
                                        if event.get("event") == "root_frame_input"],
                "root_handoff_from_situation": [manifest.get("root_handoff")
                                                 for _, _, manifest in manifests
                                                 if manifest.get("root_handoff")],
                "task_code_run_outcomes_surfaced_by_situation": situation_outcomes,
                "all_supervisor_file_reads_before_terminal": entry["supervisor_file_reads"],
                "all_supervisor_code_runs_before_terminal": entry["supervisor_code_runs"],
                "measurement_read_selection": "none; all reads are indexed without semantic classification",
            }
        result.append(entry)
    raw.write(DESTINATION / "MEASUREMENT_TRACE_INDEX.json", {
        "schema": "mechanical-measurement-trace-index/1",
        "run_id": RUN_ID,
        "semantic_scoring": None,
        "source_paths": ["monitor/audit/dialogue.jsonl", "monitor/audit/progress.jsonl",
                         "monitor/audit/reviews.jsonl", "monitor/audit/cfs_deltas/",
                         "monitor/task_evidence/public_events.jsonl"],
        "review_count": len(result),
        "reviews": result,
    })


def final_workspace_diff() -> None:
    capture = CAMPAIGN / "bridge" / RUN_ID / "evidence/pre_verification_app.tar"
    if not capture.is_file():
        raise RuntimeError("Terminal pre-verifier workspace capture absent")
    if EXTRACTION.exists():
        raise RuntimeError("Final workspace extraction target already exists")
    with tarfile.open(capture) as archive:
        for member in archive.getmembers():
            path = PurePosixPath(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise RuntimeError("Unsafe terminal workspace archive member")
    EXTRACTION.mkdir(parents=True, exist_ok=False)
    subprocess.run(["tar", "-xf", str(capture), "-C", str(EXTRACTION)], check=True)
    destination = DESTINATION / "task_final"
    destination.mkdir(parents=True, exist_ok=False)
    patch = destination / "tracked_changes.patch"
    subprocess.run(["git", "-C", str(EXTRACTION), "diff", "--binary",
                    f"--output={patch}"], check=True)
    listed = subprocess.check_output(
        ["git", "-C", str(EXTRACTION), "ls-files", "--others", "--exclude-standard"],
        text=True, encoding="utf-8").splitlines()
    files = [patch]
    for name in listed:
        relative = PurePosixPath(name)
        if relative.is_absolute() or ".." in relative.parts:
            raise RuntimeError("Unsafe untracked task path")
        source = EXTRACTION.joinpath(*relative.parts)
        target = destination / "untracked" / Path(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        files.append(target)
    raw.write(destination / "MANIFEST.json", {
        "source_capture": str(capture),
        "source_capture_sha256": raw.digest(capture),
        "files": [{"path": path.relative_to(destination).as_posix(),
                   "bytes": path.stat().st_size, "sha256": raw.digest(path)}
                  for path in files],
    })


def main() -> None:
    if STAGING.exists() or DESTINATION.exists():
        raise RuntimeError("Archive staging or destination already exists")
    prior.RUN_ID = RUN_ID
    prior.ROOT = ROOT
    prior.CAMPAIGN = CAMPAIGN
    prior.DESTINATION = STAGING / RUN_ID
    prior.main()
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(prior.DESTINATION), str(DESTINATION))
    summary_path = DESTINATION / "MECHANICAL_SUMMARY.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    summary["archive_path"] = str(DESTINATION)
    raw.write(summary_path, summary)
    recover_long_path_copies()
    measurement_index()
    final_workspace_diff()
    print(json.dumps({"archive": str(DESTINATION),
                      "measurement_index": str(DESTINATION / "MEASUREMENT_TRACE_INDEX.json")},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
