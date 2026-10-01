"""Thin identity adapter for the frozen ADER-v2c Roadmap launch path."""

import importlib.util
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BASE_LAUNCHER = ROOT / "method_discovery/diagnostics/ader_v2c_real_dev_pilot_20261001/launch_ader_v2c.py"
spec = importlib.util.spec_from_file_location("archived_ader_v2c_launcher", BASE_LAUNCHER)
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

PARENT = "c6f6cc8fac555b638303237b64881552e38d846b"
CANDIDATE = "e52107808527cb42ad2169db721b69b450a674fc"
SOURCE = Path(r"E:\longcontext-dynamic-observer-v0c-c6f6")
RUNS = {
    "dynamic-observer-v0c-adoption-20261001-01":
        ("fyn-2.2.0-roadmap", "r1", "ader-v2c-real-dev-pilot-20261001-01", 500, 10000),
    "dynamic-observer-v0c-adoption-20261001-02":
        ("ktx-0.13.0-roadmap", "r2", "ader-v2c-real-dev-pilot-20261001-02", 300, 7200),
}


def frozen_source(destination):
    head = subprocess.check_output(["git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    tracked_dirty = subprocess.check_output(
        ["git", "-C", str(SOURCE), "status", "--porcelain", "--untracked-files=no"], text=True)
    if head != CANDIDATE or tracked_dirty:
        raise RuntimeError("frozen v0c source identity mismatch")
    parents = subprocess.check_output(
        ["git", "-C", str(SOURCE), "rev-list", "--parents", "-n", "1", "HEAD"], text=True).split()
    if parents != [CANDIDATE, PARENT]:
        raise RuntimeError("v0c is not the approved sibling")
    changed = set(subprocess.check_output(
        ["git", "-C", str(SOURCE), "diff", "--name-only", PARENT, CANDIDATE,
         "--", "GenericAgent-main"], text=True).splitlines())
    if changed != {
        "GenericAgent-main/monitor_agent_core/agent.py",
        "GenericAgent-main/monitor_agent_core/working_context.py",
        "GenericAgent-main/tests/test_dynamic_observer_v0c.py",
        "GenericAgent-main/tests/test_monitor_dcec.py",
    }:
        raise RuntimeError("v0c source has unreviewed files: " + repr(sorted(changed)))

    archive = subprocess.check_output(
        ["git", "-C", str(SOURCE), "archive", "--format=zip", CANDIDATE, "GenericAgent-main"])
    destination.mkdir(parents=True, exist_ok=False)
    with base.zipfile.ZipFile(base.io.BytesIO(archive)) as stream:
        stream.extractall(destination)
    ga = destination / "GenericAgent-main"
    (ga / "temp").mkdir(exist_ok=True)
    key = base.RUNNER_ROOT / "GenericAgent-main/mykey.py"
    profile = base.RUNNER_ROOT / "monitor_config/models.local.json"
    if base.sha(key.read_bytes()) != base.TASK_PROFILE_SHA:
        raise RuntimeError("Task private profile changed")
    if base.sha(profile.read_bytes()) != base.MONITOR_PROFILE_SHA:
        raise RuntimeError("Supervisor private profile changed")
    base.shutil.copyfile(key, ga / "mykey.py")
    (destination / "monitor_config").mkdir()
    base.shutil.copyfile(profile, destination / "monitor_config/models.local.json")
    return ga, {
        "commit": head,
        "parent_commit": PARENT,
        "source_tree": subprocess.check_output(
            ["git", "-C", str(SOURCE), "rev-parse", CANDIDATE + "^{tree}"], text=True).strip(),
        "git_archive_sha256": base.sha(archive),
        "task_profile_sha256": base.sha(key.read_bytes()),
        "monitor_profile_sha256": base.sha(profile.read_bytes()),
        "production_diff": ["monitor_agent_core/agent.py", "monitor_agent_core/working_context.py"],
    }


original_configure_runner = base.configure_runner


def configure_runner(ga, output):
    original_configure_runner(ga, output)
    base.runner.COLLECTOR_NAME = "dynamic-observer-v0c-adoption-otel"


base.HERE = HERE
base.ADER_ROOT = SOURCE
base.ADER_V1 = PARENT
base.ADER = CANDIDATE
base.BATCH = "dynamic-observer-v0c-adoption-20261001"
base.REFERENCE = ROOT / "method_discovery/runs/ader_v2c_real_dev_pilot_20261001"
base.REFERENCE_LOCAL = ROOT / "long_context_bench/output/ader_v2c_real_dev_pilot_20261001"
base.RECORDS = RUNS
base.frozen_source = frozen_source
base.configure_runner = configure_runner


if __name__ == "__main__":
    sys.argv[0] = str(HERE / "launch_adoption.py")
    base.main()
