"""Run only no-model Docker tool probes and write a mechanical certificate."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile

from .adapter import HERE, materialize, save_json, sha
from .docker_tool import DockerToolPort, IMAGE


def run() -> dict:
    server = subprocess.run(["docker", "info", "--format", "{{.ServerVersion}} {{.OSType}}"],
                            capture_output=True, text=True, check=True).stdout.strip()
    image = subprocess.run(["docker", "image", "inspect", IMAGE, "--format", "{{.Id}}"],
                           capture_output=True, text=True, check=True).stdout.strip()
    if image != IMAGE or not server.endswith(" linux"):
        raise RuntimeError("Frozen Linux image/daemon unavailable")
    code = (HERE / "probe_isolation.py").read_text(encoding="utf-8")
    cases = {}
    with tempfile.TemporaryDirectory(prefix="static-diagnostic-certify-") as temporary:
        root = Path(temporary)
        for scene in ("C01", "C02"):
            fixture = root / scene
            manifest = materialize(scene, fixture)
            port = DockerToolPort(fixture)
            before = sha((port.app / "menu.go").read_bytes())
            receipt = port.execute("code_run", {"type": "python", "code": code, "timeout": 60})
            output = port.private / receipt["output_path"].removeprefix("monitor/")
            findings = json.loads(output.read_text(encoding="utf-8"))
            if (receipt["status"] != "success" or not all(findings.values()) or
                    sha((port.app / "menu.go").read_bytes()) != before):
                raise RuntimeError(f"Isolation probe failed: {scene}")
            cases[scene] = {"all_probe_checks_passed": True,
                            "probe_results": findings,
                            "probe_output_sha256": sha(output.read_bytes()),
                            "workspace_tree_sha256": manifest["workspace_tree_sha256"],
                            "visible_file_count": len(manifest["visible_files"]),
                            "historic_completed_output_count": len(port.historical)}
    result = {"status": "certified_for_offline_docker_tool_port_only",
              "isolation_certified": True,
              "not_a_live_model_authorization": True,
              "image": image, "docker_server": server,
              "tool_port_source_sha256": sha((HERE / "docker_tool.py").read_bytes()),
              "probe_source_sha256": sha((HERE / "probe_isolation.py").read_bytes()),
              "mount_policy": "app/evidence read-only; private per-attempt writable; /tests masked; no network; read-only root; no host credentials passed",
              "cases": cases,
              "provider_calls": 0, "task_agent_calls": 0, "supervisor_model_calls": 0,
              "native_evaluator_calls": 0}
    save_json(HERE / "ISOLATION_CERTIFICATION.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, sort_keys=True))
