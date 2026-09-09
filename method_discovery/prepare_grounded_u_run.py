"""Prepare candidate U manifest or run minimal connectivity probes; never launch tasks."""
import argparse
import concurrent.futures
import json
import sys
import time
from pathlib import Path

from clean_monitor_prepare_real_task_gate import build_manifest, ROOT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    parser.add_argument("--run-suffix", default="phase1-grounded-u-20260908-r1")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "method_discovery/artifacts/phase1_20260908/grounded_u_fyne_r1_manifest.json")
    args = parser.parse_args()
    if args.probe:
        sys.path.insert(0, str(ROOT / "GenericAgent-main"))
        from llmcore import reload_mykeys
        from monitor_agent_core.provider import MonitorProviderClient
        configs = reload_mykeys()[0]

        def probe(name):
            started = time.monotonic()
            try:
                client = MonitorProviderClient(name, dict(configs[name], max_tokens=128, read_timeout=90))
                answer = client.complete([{"role": "user", "content": "Reply only OK."}], [])
                return {"config": name, "ok": bool(answer.content.strip()),
                        "seconds": round(time.monotonic()-started, 2), "usage": answer.usage}
            except Exception as exc:
                return {"config": name, "ok": False, "error_type": type(exc).__name__,
                        "seconds": round(time.monotonic()-started, 2)}
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            results = list(pool.map(probe, ["native_claude_cc_vibe_opus48", "native_oai_cc_vibe_gpt56_sol_high"]))
        print(json.dumps(results))
        return int(not all(row["ok"] for row in results))
    output = args.output
    if output.exists():
        raise FileExistsError("Refusing to overwrite an existing manifest")
    data = build_manifest("roadmapbench:fyn-2.2.0-roadmap", args.run_suffix, output)
    data["candidate"] = "grounded-context-u"
    data["runs"][0]["environment"].update(
        GA_LLM_CONFIG_NAME="native_claude_cc_vibe_opus48", GA_MONITOR_GROUNDED_CONTEXT="1")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(str(output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
