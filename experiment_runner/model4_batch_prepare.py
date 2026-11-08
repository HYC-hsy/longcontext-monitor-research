"""Prepare private, per-slot configs for the frozen five-task/four-model run.

This writes no credentials to stdout or the repository. It never calls a model
or runs a Task. Every slot is subsequently launched through experiment_runner.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy


TASKS = ("kv-store-grpc", "reshard-c4-data", "rstan-to-pystan",
         "largest-eigenval", "filter-js-from-html")
MODELS = ("claude-opus-4-8", "claude-opus-5", "claude-fable-5", "gpt-6.1-sol")
METHOD = "pma-predictive-read-context"
CACHED = frozenset(TASKS) - {"reshard-c4-data"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(templates: Path, output: Path, repo: Path) -> dict:
    if output.exists():
        raise FileExistsError("batch output directory must be new")
    source = {}
    for task in TASKS:
        path = templates / (task + ".private.json")
        source[task] = json.loads(path.read_text(encoding="utf-8"))
        cfg = source[task]
        if (cfg["method"] != METHOD or cfg["slots"] != [
                {"method": METHOD, "occurrence": 1, "task": task}] or
                cfg["dataset"]["commit"] != "2fd12b88aafdd04a52c298e3940bcb189f9766d6" or
                cfg["runtime_policy"] != {"agent_timeout": "uncapped",
                    "task_turns": "uncapped", "verifier_timeout": "official"}):
            raise ValueError("template differs from frozen task/method/policy")
    profiles = source[TASKS[0]]["environment"]["profiles"]
    if any(item["environment"]["profiles"] != profiles for item in source.values()):
        raise ValueError("template model profile paths differ")
    task_profile = Path(profiles["task_profile_file"])
    pma_profile = Path(profiles["pma_profile_file"])
    task_settings = runpy.run_path(str(task_profile))["native_claude_cc_vibe_opus48"]
    pma_settings = json.loads(pma_profile.read_text(encoding="utf-8"))["claude_monitor_opus48"]
    if (task_settings["model"] != "claude-opus-4-8" or
            pma_settings["model"] != "claude-opus-4-8"):
        raise ValueError("frozen original model identity changed")
    names = []
    output.mkdir(parents=True)
    private_profiles = output / "private_profiles"
    private_configs = output / "private_configs"
    private_profiles.mkdir()
    private_configs.mkdir()
    for model in MODELS:
        if model == "gpt-6.1-sol":
            oai = runpy.run_path(str(task_profile))["native_oai_cc_vibe_gpt56_sol_high"]
            profile = {"provider": "openai", "api_mode": "responses", "model": model,
                       "apibase": oai["apibase"], "apikey": oai["apikey"],
                       "store": False, "reasoning_effort": "high", "max_tokens": 8192,
                       "model_context_window": 200000,
                       "read_timeout": pma_settings["read_timeout"],
                       "max_retries": pma_settings["max_retries"]}
        else:
            profile = dict(pma_settings, model=model)
        target = private_profiles / (model + ".json")
        target.write_text(json.dumps({"pma_model": profile}, ensure_ascii=False,
                                     indent=2) + "\n", encoding="utf-8")
    for task_index, task in enumerate(TASKS):
        for position in range(len(MODELS)):
            model = MODELS[(task_index + position) % len(MODELS)]
            config = copy.deepcopy(source[task])
            config["environment"]["paths"]["ga_source"] = str(repo / "GenericAgent-main")
            config["environment"]["paths"]["bench_root"] = str(repo / "long_context_bench")
            config["environment"]["profiles"]["pma_profile_file"] = str(
                private_profiles / (model + ".json"))
            if task in CACHED:
                bundle = Path("E:/ga20restoredata29") / ("eval-cache-" + task)
                config["evaluation_bootstrap_protocol"] = "prepared_dependency_bundle_v1"
                config["evaluation_cache"] = {
                    "bundle_path": str(bundle),
                    "manifest_sha256": file_hash(bundle / "manifest.json")}
            else:
                config.pop("evaluation_cache", None)
                config["evaluation_bootstrap_protocol"] = "original"
            slot = len(names) + 1
            label = f"{slot:02d}-{task}-{model}"
            config_path = private_configs / (label + ".json")
            config_path.write_text(json.dumps(config, ensure_ascii=False,
                                             indent=2) + "\n", encoding="utf-8")
            names.append({"slot": slot, "task": task, "model": model,
                          "config": str(config_path), "output": str(output / "runs" / label),
                          "evaluation_protocol": config["evaluation_bootstrap_protocol"],
                          "task_profile_sha256": file_hash(task_profile),
                          "pma_profile_sha256": file_hash(private_profiles / (model + ".json"))})
    plan = {"schema": "pma-simple-model4-plan-v1", "method": METHOD,
            "tasks": TASKS, "models": MODELS, "slots": names}
    (output / "batch_plan.json").write_text(json.dumps(plan, ensure_ascii=False,
                                              indent=2) + "\n", encoding="utf-8")
    return plan


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.templates, args.output, args.repo)
    print(f"prepared {len(result['slots'])} private configs; no model calls")
