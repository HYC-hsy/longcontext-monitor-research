"""Re-certify the amended asynchronous Docker tool port without changing stage-1 evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import tempfile

from .adapter import HERE, materialize, save_json, sha
from .docker_tool import DockerToolPort, IMAGE


def run(output_name: str = "ISOLATION_CERTIFICATION_V2.json") -> dict:
    if output_name not in {"ISOLATION_CERTIFICATION_V2.json", "ISOLATION_CERTIFICATION_V3.json"}:
        raise ValueError("Certification output name is not allowed")
    image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                           text=True, capture_output=True, check=True).stdout.strip()
    server = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}} {{.OSType}}"],
                            text=True, capture_output=True, check=True).stdout.strip()
    if image != IMAGE or not server.endswith(" linux"):
        raise RuntimeError("Frozen image/Linux daemon unavailable")
    probe = (HERE / "probe_isolation.py").read_text(encoding="utf-8")
    cases = {}
    with tempfile.TemporaryDirectory(prefix="static-diagnostic-v2-cert-") as temporary:
        for scene in ("C01", "C02"):
            fixture = Path(temporary) / scene
            manifest = materialize(scene, fixture)
            port = DockerToolPort(fixture)
            before = sha((port.app / "menu.go").read_bytes())
            receipt = port.execute("code_run", {"type": "python", "code": probe,
                                                "timeout": 60, "wait_seconds": 5})
            for _ in range(20):
                if receipt["status"] != "running":
                    break
                receipt = port.execute("code_run", {"session_id": receipt["session_id"],
                                                    "wait_seconds": 5})
            output = port.private / receipt["output_path"].removeprefix("monitor/")
            findings = json.loads(output.read_text(encoding="utf-8"))
            port.close()
            if (receipt["status"] != "success" or not all(findings.values()) or
                    sha((port.app / "menu.go").read_bytes()) != before):
                raise RuntimeError("Isolation probe failed: " + scene)
            cases[scene] = {"probe_results": findings, "all_probe_checks_passed": True,
                            "probe_output_sha256": sha(output.read_bytes()),
                            "workspace_tree_sha256": manifest["workspace_tree_sha256"],
                            "visible_file_count": len(manifest["visible_files"]),
                            "historical_completed_outputs": len(port.historical)}
    result = {"status": "certified_for_amended_async_docker_tool_port_only",
              "image": IMAGE, "docker_server": server, "cases": cases,
              "tool_port_source_sha256": sha((HERE / "docker_tool.py").read_bytes()),
              "probe_source_sha256": sha((HERE / "probe_isolation.py").read_bytes()),
              "mount_policy": "app/evidence read-only; per-attempt private writable; /tests masked; no network; read-only root; no host credentials passed",
              "model_provider_calls": 0, "task_calls": 0, "native_evaluator_calls": 0}
    save_json(HERE / output_name, result)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-name", default="ISOLATION_CERTIFICATION_V2.json")
    args = parser.parse_args()
    print(json.dumps(run(args.output_name), ensure_ascii=False, sort_keys=True))
