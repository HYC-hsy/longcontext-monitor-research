"""One cold-start PMA cycle per arm/case, using the verified handoff source.

The Task and evaluator never run. Private full records stay outside Git.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time
from types import ModuleType, SimpleNamespace

import litellm

PMA_HOST = (Path(__file__).resolve().parents[1] / "curator_supervisor_convergence_v0"
            / "pma_full_upstream_ga_v1_20261013")
sys.path.insert(0, str(PMA_HOST))
from episode import construct_upstream  # noqa: E402

TXT_HASH = "263ef8fec8900dc11e98364902b13f0a765203681f1e5ca68368e402ef449fe7"
PROFILE_HASH = "cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1"
PMA_HASH = "e00d412034b8cfebb6b8121477453d2815e26ce2d78344c9f7991a37048e0b35"
OBSERVER_HASH = "43be3fd26948da674cbac4a49df92d5e44b4c78abf175a710e21c2d6fe671cdb"
ORDER = (("07", 235, "candidate"), ("07", 235, "reflection"),
         ("14", 105, "candidate"), ("14", 105, "reflection"),
         ("18", 6, "candidate"), ("18", 6, "reflection"))


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_new(path: Path, value: object) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def append(path: Path, value: object) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, default=str)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def capture(path: Path, value: object) -> None:
    try:
        append(path, value)
    except Exception as exc:
        raise StopTransport("required audit capture failed") from exc


def load_file(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def checked_inputs(handoff: Path, txt: Path, profile_path: Path):
    if digest(txt.read_bytes()) != TXT_HASH:
        raise ValueError("confirmed TXT identity changed")
    raw_profile = profile_path.read_bytes()
    if digest(raw_profile) != PROFILE_HASH:
        raise ValueError("private profile identity changed")
    profile = json.loads(raw_profile)["claude_monitor_opus48"]
    if any(profile.get(k) != v for k, v in {
        "provider": "anthropic", "api_mode": "messages", "model": "claude-opus-4-8",
        "thinking_type": "adaptive"}.items()):
        raise ValueError("private model route changed")
    prototype = handoff / "consequence_observer_v0"
    source = prototype / "vendor/pma_89e5c0d/src/memory_agent/memory"
    if digest((source / "memory_agent.py").read_bytes()) != PMA_HASH:
        raise ValueError("pinned PMA source changed")
    if digest((prototype / "observer.py").read_bytes()) != OBSERVER_HASH:
        raise ValueError("candidate source changed")
    bundle = handoff / "verified_three_case_bundle"
    manifest = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
    rows = {(r["arm"], r["step"]): r for r in manifest["cases"]}
    if set(rows) != {(arm, step) for arm, step, _ in ORDER}:
        raise ValueError("three-case identity changed")
    for row in rows.values():
        for key, hash_key in (("bank", "bank_sha256"), ("observation", "observation_sha256")):
            if digest((bundle / row[key]).read_bytes()) != row[hash_key]:
                raise ValueError("three-case input changed")
    for name in ("handoff_pma", "handoff_pma.memory"):
        package = ModuleType(name)
        package.__path__ = [str(source if name.endswith(".memory") else source.parent)]
        sys.modules[name] = package
    module = importlib.import_module("handoff_pma.memory.memory_agent")
    observer = load_file("consequence_handoff_observer", prototype / "observer.py")
    return profile, module, observer, bundle, rows


def case_state(module, observer, bundle: Path, row: dict, variant: str):
    snapshot = json.loads((bundle / row["bank"]).read_text(encoding="utf-8"))
    observation = (bundle / row["observation"]).read_text(encoding="utf-8")
    bank = module.UniversalMemory.from_dict(snapshot)
    selected = observer.classes(module)[variant]
    agent = selected(llm=None, memory=bank)
    original = module.MemoryAgent(llm=None, memory=module.UniversalMemory.from_dict(snapshot))
    rebuilt = original._build_phase1_prompt(observation, row["step"])
    if digest(rebuilt.encode("utf-8")) != row["expected_original_U_phase1_prompt_sha256"]:
        raise ValueError("original U Phase-1 prompt drifted")
    if agent._build_phase1_prompt(observation, row["step"]) != rebuilt:
        raise ValueError("arm changed the original PMA input assembly")
    return agent, bank, observation, snapshot


class StopTransport(BaseException):
    """Escape upstream's exception-to-silence handler after a failed request."""


async def run_unit(profile, module, observer, bundle, row, variant, directory, fake):
    directory.mkdir(exist_ok=False)
    agent, bank, observation, before = case_state(module, observer, bundle, row, variant)
    write_new(directory / "bank_before.json", before)
    host = None
    original_lower = litellm.acompletion
    lower_attempts = 0
    logical = 0
    failed = False

    async def lower(**kwargs):
        nonlocal lower_attempts, failed
        if failed or lower_attempts >= 2:
            raise StopTransport("provider attempt budget exhausted")
        lower_attempts += 1
        index = lower_attempts
        safe = {k: kwargs.get(k) for k in ("model", "max_tokens", "temperature",
                "thinking", "reasoning_effort", "timeout", "messages", "tools")}
        capture(directory / "provider_attempts.jsonl", {"attempt": index, "sent_epoch": time.time(),
                "request": safe})
        if fake:
            raise StopTransport("fake mode must not reach provider")
        try:
            response = await original_lower(**kwargs)
            capture(directory / "provider_attempts.jsonl", {"attempt": index,
                    "returned_epoch": time.time(), "usage": response.get("usage"),
                    "model": response.get("model"), "choices": response.get("choices")})
            return response
        except Exception as exc:
            failed = True
            capture(directory / "provider_attempts.jsonl", {"attempt": index,
                    "failed_epoch": time.time(), "error_type": type(exc).__name__,
                    "server_execution": "unknown"})
            raise StopTransport("provider failure; no retry") from exc

    async def transport(*, prompt, system, tools=None):
        nonlocal logical
        if logical >= 2 or failed:
            raise StopTransport("logical call budget exhausted")
        logical += 1
        index = logical
        phase = "phase1" if tools is not None else "phase2"
        if phase != ("phase1" if index == 1 else "phase2"):
            raise StopTransport("phase order changed")
        capture(directory / "requests.jsonl", {"call": index, "phase": phase,
                "epoch": time.time(), "prompt": prompt, "system": system, "tools": tools})
        if fake:
            response = (SimpleNamespace(content="", tool_calls=[SimpleNamespace(
                function=SimpleNamespace(name="memory_update_status",
                                         arguments={"content": "FAKE_STATUS"}))])
                if index == 1 else SimpleNamespace(content="<no_intervention/>", tool_calls=[]))
        else:
            response = await original_transport(prompt=prompt, system=system, tools=tools)
        capture(directory / "responses.jsonl", {"call": index, "phase": phase,
                "epoch": time.time(), "content": response.content,
                "tool_calls": [dict(name=c.function.name, arguments=c.function.arguments)
                               for c in response.tool_calls or []],
                "usage": getattr(response, "usage", None)})
        return response

    try:
        if not fake:
            host = construct_upstream(directory / "host_transport", memory_profile=profile,
                                      research_candidate="U")
            original_transport = host._memory_llm.call
            litellm.acompletion = lower
        agent.llm = SimpleNamespace(call=transport)
        cycle = await agent.process(observation, step_count=row["step"])
        if (logical != 2 or (not fake and lower_attempts != 2)
                or not cycle.raw_response_phase2 or any(not op.success for op in cycle.operations)):
            raise RuntimeError("two-phase cycle incomplete")
        raw2 = agent._strip_thinking(cycle.raw_response_phase2)
        if "<context_for_action>" not in raw2 and "<no_intervention" not in raw2:
            raise RuntimeError("Phase-2 response format incomplete")
        if fake and (bank.status != "FAKE_STATUS" or "FAKE_STATUS" not in cycle.user_prompt_phase2):
            raise RuntimeError("updated PMA bank did not reach Phase 2")
        write_new(directory / "bank_after.json", bank.to_dict())
        result = {"status": "completed", "arm": variant, "case": row["arm"],
                  "step": row["step"], "logical_calls": logical,
                  "provider_attempts": lower_attempts, "operations": [vars(x) for x in cycle.operations],
                  "reminder": cycle.context_for_action, "fake": fake,
                  "semantic_quality": "not_scored", "task_execution": "not_run"}
    except BaseException as exc:
        result = {"status": "stopped_failure", "arm": variant, "case": row["arm"],
                  "step": row["step"], "logical_calls": logical,
                  "provider_attempts": lower_attempts, "error_type": type(exc).__name__,
                  "error": str(exc), "server_execution": "unknown" if lower_attempts else "not_sent"}
    finally:
        litellm.acompletion = original_lower
    write_new(directory / "result.json", result)
    return result


async def run(args):
    handoff = args.handoff.resolve(strict=True)
    profile, module, observer, bundle, rows = checked_inputs(
        handoff, args.txt.resolve(strict=True), args.profile.resolve(strict=True))
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("single-use output already exists")
    for arm, step, variant in ORDER:
        case_state(module, observer, bundle, rows[arm, step], variant)
    output.mkdir(parents=True, exist_ok=False)
    write_new(output / "identity.json", {"txt_sha256": TXT_HASH, "profile_sha256": PROFILE_HASH,
              "source_sha256": PMA_HASH, "observer_sha256": OBSERVER_HASH,
              "mode": args.mode, "order": ORDER, "max_logical_calls": 12,
              "max_observable_provider_attempts": 12})
    results = []
    for index, (arm, step, variant) in enumerate(ORDER, 1):
        result = await run_unit(profile, module, observer, bundle, rows[arm, step], variant,
                                output / f"unit_{index:02d}_{arm}_{variant}", args.mode == "fake")
        results.append(result)
        append(output / "summary.jsonl", result)
        if result["status"] != "completed":
            break
    write_new(output / "summary.json", {"mode": args.mode, "units": results,
              "logical_calls": sum(x["logical_calls"] for x in results),
              "provider_attempts": sum(x["provider_attempts"] for x in results),
              "complete": len(results) == 6 and all(x["status"] == "completed" for x in results)})
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fake", "live"), required=True)
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--txt", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parsed = parser.parse_args()
    finished = asyncio.run(run(parsed))
    print(json.dumps({"units": len(finished), "status": finished[-1]["status"],
                      "logical_calls": sum(x["logical_calls"] for x in finished),
                      "provider_attempts": sum(x["provider_attempts"] for x in finished)}))
    if len(finished) != 6 or finished[-1]["status"] != "completed":
        raise SystemExit(1)
