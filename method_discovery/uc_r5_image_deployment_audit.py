"""Read-only Docker image and deployed-code identity audit; no task execution."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


TASKS = {
    "fyn-2.2.0-roadmap": "znpt/roadmapbench-fyn-2.2.0-roadmap",
    "ktx-0.13.0-roadmap": "znpt/roadmapbench-ktx-0.13.0-roadmap",
}


def command(args):
    result = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=180)
    if result.returncode:
        raise RuntimeError(f"{args[0]} exited {result.returncode}: {result.stderr[:500]}")
    return result.stdout


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(repo: Path, private: Path, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    assets = json.loads((output / "TASK_ASSETS.json").read_text(encoding="utf-8"))
    docker = {"context": command(["docker", "context", "show"]).strip(),
              "engine": json.loads(command(["docker", "info", "--format",
                                           "{{json .ServerVersion}}"]))}
    images = {}
    shell = (
        "for p in /app /tests /solution /logs /opt/genericagent-source "
        "/app/.git /app/monitor /app/temp; do "
        "if [ -e \"$p\" ]; then echo PRESENT:$p; else echo ABSENT:$p; fi; done; "
        "git -C /app rev-parse HEAD; git -C /app status --porcelain; "
        "find /app -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum; "
        "find /app -type f | wc -l; "
        "find /app -type d | grep -Ei '(solution|hidden|trajectory|archive|checkpoint|monitor)' | head -40 || true"
    )
    for task, tag in TASKS.items():
        info = json.loads(command(["docker", "image", "inspect", tag]))[0]
        raw = command(["docker", "run", "--rm", "--network", "none", "--read-only",
                       "--entrypoint", "sh", tag, "-c", shell])
        (output / f"IMAGE_{task}_RAW.txt").write_text(raw, encoding="utf-8")
        expected = assets["tasks"][task]["image_proposal"]["digest"]
        images[task] = {"tag": tag, "image_id": info["Id"],
                        "repo_digests": info.get("RepoDigests") or [],
                        "architecture": info["Architecture"], "os": info["Os"],
                        "working_dir": info["Config"].get("WorkingDir"),
                        "expected_digest": expected, "matches_proposal_digest": info["Id"] == expected,
                        "raw_file": f"IMAGE_{task}_RAW.txt",
                        "raw_sha256": hashlib.sha256(raw.encode()).hexdigest(),
                        "inspection_scope": "existing image /app and named hidden/old-artifact paths; no Harbor dynamic mounts"}
    source = repo / "GenericAgent-main"
    relevant = [p for p in source.glob("*.py") if not p.name.startswith("mykey")]
    relevant += [p for p in (source / "monitor_agent_core").rglob("*.py")
                 if "__pycache__" not in p.parts and "tests" not in p.parts]
    code = {}
    for condition in ("C0", "RP", "AP", "RB", "AB"):
        deployed = private / f"bundle_{condition}" / "source"
        mismatches = []
        mapped = []
        for path in relevant:
            relative = path.relative_to(source)
            target = deployed / relative
            if not target.is_file() or sha(path) != sha(target):
                mismatches.append(relative.as_posix())
            else:
                mapped.append({"path": relative.as_posix(), "sha256": sha(path)})
        code[condition] = {"checked_file_count": len(relevant),
                           "mismatches": mismatches,
                           "file_manifest": mapped,
                           "generated_profile_excluded_from_code_comparison": True}
    result = {"docker": docker, "images": images, "deployment_code": code,
              "all_images_match_proposals": all(i["matches_proposal_digest"] for i in images.values()),
              "all_deployed_code_matches_candidate": all(not c["mismatches"] for c in code.values())}
    path = output / "IMAGE_AND_DEPLOYMENT.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"images_match": result["all_images_match_proposals"],
            "code_matches": result["all_deployed_code_matches_candidate"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--private", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.repo, args.private, args.output), sort_keys=True))
