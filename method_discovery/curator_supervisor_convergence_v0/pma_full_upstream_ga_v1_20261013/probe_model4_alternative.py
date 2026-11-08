"""One real P1/P2 transport probe using a frozen, previously visible task_start.

This does not start a Task or verifier. It never writes the private profile or
provider-private reasoning into the probe directory.
"""

import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import traceback
import uuid

from episode import PMAEpisode, construct_upstream
from pma_model_profile import READ_CONTEXT


async def probe(args):
    root = args.output.resolve()
    root.mkdir(parents=True, exist_ok=False)
    profile_bytes = args.profile.read_bytes()
    profile = json.loads(profile_bytes)["pma_model"]
    if profile["provider"] != "openai" or profile["api_mode"] != "responses":
        raise ValueError("probe requires the existing Responses profile")
    profile["model"] = args.model
    source_bytes = args.task_start.read_bytes()
    event = json.loads(source_bytes)
    if event.get("kind") != "task_start" or event.get("task_id") != "kv-store-grpc":
        raise ValueError("probe input is not the frozen KV task_start")
    run_id = "model-probe-" + uuid.uuid4().hex
    event.update(run_id=run_id, event_id=run_id + "-start", sequence=1)
    agent = construct_upstream(root / "upstream", memory_profile=profile,
                               research_candidate=READ_CONTEXT)
    episode = PMAEpisode(agent, run_id=run_id, task_id="kv-store-grpc",
                         archive=root / "archive")
    summary = {"run_id": run_id, "model": args.model,
               "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
               "profile_sha256": hashlib.sha256(profile_bytes).hexdigest(),
               "task_started": False, "native_evaluation": False}
    try:
        start = await episode.handle(event)
        summary["task_start_status"] = start.get("status")
        end = await episode.handle({"kind": "task_end", "run_id": run_id,
            "task_id": "kv-store-grpc", "event_id": run_id + "-end",
            "sequence": 2, "terminal": {"result": "PROBE_ONLY"}})
        summary["task_end_status"] = end.get("status")
        summary["status"] = "completed" if end.get("status") == "saved" else "failed"
    except Exception as exc:
        summary["status"] = "failed"
        summary["error_type"] = type(exc).__name__
        summary["cause_type"] = type(exc.__cause__).__name__ if exc.__cause__ else None
        summary["error_message"] = str(exc)
        (root / "private_traceback.txt").write_text(traceback.format_exc(), encoding="utf-8")
    llm = agent._memory_llm
    summary["response_item_types"] = (llm.last_visible_response or {}).get("output_item_types")
    if llm.last_effective_request is not None:
        (root / "visible_request.json").write_text(json.dumps(
            llm.last_effective_request, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False,
                                      indent=2), encoding="utf-8")
    print(json.dumps({k: summary.get(k) for k in
        ("model", "status", "error_type", "cause_type", "error_message",
         "response_item_types", "task_end_status")}, ensure_ascii=False))
    return 0 if summary["status"] == "completed" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--task-start", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", choices=("gpt-6-sol", "gpt-6-astra"), required=True)
    args = parser.parse_args()
    return asyncio.run(probe(args))


if __name__ == "__main__":
    raise SystemExit(main())
