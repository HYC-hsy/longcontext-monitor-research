"""Recheck private six-unit records; emit a content-free public audit summary."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ORDER = (("07", "candidate"), ("07", "reflection"),
         ("14", "candidate"), ("14", "reflection"),
         ("18", "candidate"), ("18", "reflection"))


def read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def usage_number(value: object, field: str) -> int:
    return int(str(value).split(field + "=", 1)[1].split(",", 1)[0])


def audit(root: Path, bundle: Path) -> dict:
    cases = {(r["arm"], r["step"]): r for r in json.loads(
        (bundle / "bundle.json").read_text(encoding="utf-8"))["cases"]}
    units = []
    exact = []
    for index, (case, arm) in enumerate(ORDER, 1):
        folder = root / f"unit_{index:02d}_{case}_{arm}"
        assert folder.is_dir()
        result = json.loads((folder / "result.json").read_text(encoding="utf-8"))
        before = json.loads((folder / "bank_before.json").read_text(encoding="utf-8"))
        after = json.loads((folder / "bank_after.json").read_text(encoding="utf-8"))
        requests = read_lines(folder / "requests.jsonl")
        responses = read_lines(folder / "responses.jsonl")
        attempts = read_lines(folder / "provider_attempts.jsonl")
        assert len(requests) == len(responses) == 2 and len(attempts) == 4
        assert (result["case"], result["arm"], result["status"],
                result["logical_calls"], result["provider_attempts"]) == (
                case, arm, "completed", 2, 2)
        assert [r["phase"] for r in requests] == ["phase1", "phase2"]
        assert requests[0]["tools"] and requests[1]["tools"] is None
        archived = json.loads((bundle / cases[case, result["step"]]["bank"]).read_text(
            encoding="utf-8"))
        assert before["status"] == archived["status"]
        for kind in ("knowledge", "procedural"):
            assert [(x["id"], x["content"]) for x in before[kind]] == [
                (x["id"], x["content"]) for x in archived[kind]]
        assert sha(requests[0]["prompt"]) == cases[case, result["step"]][
            "expected_original_U_phase1_prompt_sha256"]
        assert after["status"] in requests[1]["prompt"]
        assert all(op["success"] for op in result["operations"])
        assert all("returned_epoch" in attempts[i] and "sent_epoch" in attempts[i - 1]
                   for i in (1, 3))
        for call in range(2):
            request = attempts[call * 2]["request"]
            assert request["messages"][0]["content"][0]["text"] == requests[call]["system"]
            assert request["messages"][1]["content"][0]["text"] == requests[call]["prompt"]
            assert request["model"] == "anthropic/claude-opus-4-8"
            assert request["max_tokens"] == 8192
            assert request["thinking"] == {"type": "adaptive"}
            assert "api_key" not in request and "apikey" not in request
        usage = [attempts[i]["usage"] for i in (1, 3)]
        prompt_tokens = sum(usage_number(u, "prompt_tokens") for u in usage)
        output_tokens = sum(usage_number(u, "completion_tokens") for u in usage)
        seconds = sum(attempts[i]["returned_epoch"] - attempts[i - 1]["sent_epoch"]
                      for i in (1, 3))
        units.append({"case": case, "arm": arm, "step": result["step"],
                      "logical_calls": 2, "observable_provider_attempts": 2,
                      "prompt_tokens": prompt_tokens, "completion_tokens": output_tokens,
                      "provider_elapsed_seconds": round(seconds, 3),
                      "operation_count": len(result["operations"]),
                      "reminder_present": result["reminder"] is not None,
                      "phase1_prompt_sha256": sha(requests[0]["prompt"]),
                      "phase2_prompt_sha256": sha(requests[1]["prompt"])})
        exact.append(requests)
    for i in (0, 2, 4):
        assert exact[i][0]["prompt"] == exact[i + 1][0]["prompt"]
        assert exact[i][0]["tools"] == exact[i + 1][0]["tools"]
        assert exact[i][0]["system"] != exact[i + 1][0]["system"]
    assert len(list(root.glob("unit_*"))) == 6
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert summary["complete"] and summary["logical_calls"] == 12
    assert summary["provider_attempts"] == 12
    return {"status": "verified_records", "study": "historical static-input single-cycle screen",
            "task_runs": 0, "evaluator_runs": 0, "units": units,
            "totals": {"logical_calls": 12, "observable_provider_attempts": 12,
                       "prompt_tokens": sum(u["prompt_tokens"] for u in units),
                       "completion_tokens": sum(u["completion_tokens"] for u in units),
                       "provider_elapsed_seconds": round(sum(u["provider_elapsed_seconds"]
                                                             for u in units), 3)},
            "cost_usd": None, "cost_note": "No verified billing rate or invoice in this archive.",
            "deeper_network_attempts": "not independently observed",
            "semantic_efficacy": "not established"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--private-run", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.private_run.resolve(strict=True), args.bundle.resolve(strict=True))
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, sort_keys=True, indent=2)
        stream.write("\n")
    print(json.dumps(result["totals"]))
