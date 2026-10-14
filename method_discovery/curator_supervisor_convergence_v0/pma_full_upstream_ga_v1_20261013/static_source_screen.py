"""Unauthorized-by-default, fixed-public-trace U/S/R shadow entry.

The fake mode calls the pinned upstream PMA through PMAEpisode. It never runs GA,
an evaluator, or a provider transport. This is not a historical PMA restoration.
"""
import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
VENDOR = HERE / "vendor" / "pma_89e5c0d"
sys.path.insert(0, str(VENDOR / "src"))
sys.path.insert(0, str(VENDOR / "external" / "harbor" / "src"))
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
from harbor.llms.base import LLMResponse

from episode import PMAEpisode, construct_upstream


MANIFEST = HERE / "SOURCE_MEMORY_STATIC_SCREEN_DRAFT.json"
FIELDS = {
    "task_start": ("initial_user_content",),
    "before_actor_call": ("actor_attempt",),
    "actor_step": ("actor_attempt", "step_status", "response", "commands", "observation"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def projected_events(case: dict, run_id: str) -> list[dict]:
    source = HERE / case["event_file"]
    if sha256(source) != case["event_file_sha256"]:
        raise ValueError("fixed public event archive identity mismatch")
    public = HERE / case["public_event_file"]
    if sha256(public) != case["public_event_file_sha256"]:
        raise ValueError("fixed public Task event identity mismatch")
    events = []
    for line in source.read_text(encoding="utf-8").splitlines():
        original = json.loads(line)["event"]
        if original["sequence"] > case["inclusive_event_sequence"]:
            break
        kind = original["kind"]
        if kind not in FIELDS:
            raise ValueError("unexpected event before frozen cutoff")
        event = {key: original[key] for key in FIELDS[kind] if key in original}
        event.update(kind=kind, task_id=case["task"], run_id=run_id,
                     event_id=f"shadow-{original['sequence']}-{original['event_id']}",
                     sequence=original["sequence"])
        events.append(event)
    if not events or events[-1]["sequence"] != case["inclusive_event_sequence"]:
        raise ValueError("cutoff sequence missing")
    if [e["sequence"] for e in events] != list(range(1, len(events) + 1)):
        raise ValueError("event sequence not contiguous")
    return events


class FakePublicTransport:
    """Responses use only actual prompt/tool schema; unexpected sends fail closed."""

    def __init__(self, path: Path, *, expected: int):
        self.path = path
        self.expected = expected
        self.calls = 0
        self.saved_once = False

    async def __call__(self, *, prompt, system, tools=None):
        self.calls += 1
        if self.calls > self.expected:
            raise AssertionError("unscripted request; no real transport fallback")
        response = LLMResponse(content="<no_intervention/>")
        if tools is not None:
            response = LLMResponse(content="", tool_calls=[])
            names = {item["function"]["name"] for item in tools}
            if "memory_save_knowledge" in names and not self.saved_once:
                match = re.search(r"## Visible public source handles \(quote exact text above\)\n(\[.*\])", prompt)
                description = re.search(
                    r"\[Task Description\]\n(.+?)(?:\n\n\[Recent Trajectory|\n\n## Your Task)",
                    prompt, re.S)
                if match and description:
                    handles = json.loads(match.group(1))
                    task_source = next((h for h in handles if h["role"] == "task_instruction"), None)
                    quote = description.group(1)[:24]
                    if task_source and quote and description.group(1).count(quote) == 1:
                        function = SimpleNamespace(name="memory_save_knowledge", arguments={
                            "content": "Review the original public task scope",
                            "statement_type": "task_requirement",
                            "source_refs": [{"event_id": task_source["event_id"],
                                             "role": "task_instruction", "quote": quote}]})
                        response = LLMResponse(content="", tool_calls=[SimpleNamespace(function=function)])
                        self.saved_once = True
        elif self.saved_once:
            match = re.search(r"\[([A-Za-z0-9_-]+) v(\d+)\]", prompt)
            if match:
                response = LLMResponse(content=(
                    "<context_for_action>Consider the original public task scope.</context_for_action>"
                    f'<memory_refs>[{{"id":"{match.group(1)}","version":{match.group(2)}}}]</memory_refs>'))
        row = {"logical_call": self.calls, "system": system, "prompt": prompt,
               "tools": tools, "response_content": response.content,
               "response_tool_calls": [vars(call.function) for call in (response.tool_calls or [])]}
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return response


async def run_fake(manifest: dict, output: Path) -> list[dict]:
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for case in manifest["cases"]:
        for variant in manifest["conditions"]:
            run_id = f"shadow-{case['task']}-{variant.lower()}"
            slot = output / run_id
            slot.mkdir()
            events = projected_events(case, run_id)
            expected = (case["estimated_phase1_calls_per_condition"]
                        + case["estimated_phase2_calls_per_condition"])
            agent = construct_upstream(slot / "upstream", research_candidate=variant)
            fake = FakePublicTransport(slot / "requests.jsonl", expected=expected)
            agent._memory_llm.call = fake
            episode = PMAEpisode(agent, run_id=run_id, task_id=case["task"],
                                 archive=slot / "episode")
            for event in events:
                await episode.handle(event)
            if fake.calls != expected:
                raise AssertionError(f"logical call count {fake.calls} != {expected}")
            agent.save_memory(str(slot / "memory.json"))
            row = {"run_id": run_id, "task": case["task"], "variant": variant,
                   "events": len(events), "logical_phase_calls": fake.calls,
                   "provider_attempts": 0, "task_calls": 0, "native_evaluator_calls": 0,
                   "task_completed": False, "input_sent": False,
                   "event_sha256": case["event_file_sha256"],
                   "request_sha256": sha256(fake.path)}
            (slot / "result.json").write_text(json.dumps(row, indent=2), encoding="utf-8")
            results.append(row)
    (output / "summary.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("fake", "live"), default="fake")
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("execution_authorized") is not False:
        raise ValueError("this static draft must remain unauthorized")
    if args.mode != "fake":
        raise PermissionError("real static provider dispatch requires a later authorization and entry")
    rows = asyncio.run(run_fake(manifest, args.output))
    print(json.dumps({"slots": len(rows), "logical_phase_calls": sum(r["logical_phase_calls"] for r in rows),
                      "real_provider_attempts": 0}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
