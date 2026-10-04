"""Export allowlisted, redacted human-monitor traces; never copy trial directories."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


HERE = Path(__file__).resolve().parents[2]
SOURCE = Path(r"E:\LongContext\method_discovery\artifacts\stage6d")
BENCH = Path(r"E:\LongContext\long_context_bench\output\m12_proofs\natural_ga\jobs")
DEST = HERE / "research_collaboration_private/evidence/manual_monitor_additional"

CASES = {
    "fbr243": (SOURCE / "human_test_gate_round1/fbr243",
               BENCH / "stage6d-human-test-gate-fbr243-r1"),
    "glz700": (SOURCE / "human_test_gate_round2/glz700",
               BENCH / "stage6d-human-test-gate-glz700-r1"),
    "rat022": (SOURCE / "human_test_gate_round3/rat022",
               SOURCE / "human_test_gate_round3/rat022/campaign/jobs"),
    "spc34_v2": (SOURCE / "human_loop_multi_v2/spc34",
                 SOURCE / "human_loop_multi_v2/spc34/jobs"),
    "spc34_v3": (SOURCE / "human_loop_multi_v2/spc34_v3",
                 SOURCE / "human_loop_multi_v2/spc34_v3/jobs"),
    "grammar_fuzz_v2": (SOURCE / "human_loop_multi_v2/grammar_fuzz_v2",
                        SOURCE / "human_loop_multi_v2/grammar_fuzz_v2/jobs"),
    "tpl40": (SOURCE / "stage6d-human-control-loop-tpl40-v1",
              SOURCE / "stage6d-human-control-loop-tpl40-v1/harbor_campaign/jobs"),
}

SECRET_PATTERNS = (
    (re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]{8,}"), "Bearer [REDACTED_CREDENTIAL]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"), "[REDACTED_CREDENTIAL]"),
    (re.compile(r"\bAKIA[A-Z0-9]{16}\b"), "[REDACTED_CREDENTIAL]"),
    (re.compile(r"(?i)(\b(?:api[_-]?key|authorization|access[_-]?token)\s*[:=]\s*[\"']?)[^\s\"'\\]{16,}"),
     r"\1[REDACTED_CREDENTIAL]"),
    (re.compile(r"(?i)[A-Z]:\\Users\\[^\\\s\"']+"), "[LOCAL_USER_HOME]"),
    (re.compile(re.escape(str(Path(r"E:\LongContext"))), re.I), "[LOCAL_REPO]"),
)


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def allowed_sources(control_root: Path, agent_root: Path):
    sources = []
    for subdir, pattern in (("decisions", "*.json"), ("interventions", "*.txt")):
        location = control_root / subdir
        if location.is_dir():
            sources.extend((path, f"{subdir}/{path.name}") for path in sorted(location.glob(pattern)))
    sources.extend((path, f"decisions/{path.name}")
                   for path in sorted(control_root.glob("boundary_decision_step_*.json")))
    for name in ("output.txt", "research_events.jsonl"):
        matches = sorted(agent_root.glob(f"**/agent/{name}"))
        if len(matches) != 1:
            raise RuntimeError(f"Expected one online Task {name} under {agent_root}; found {len(matches)}")
        sources.append((matches[0], f"task_online/{name}"))
    return sources


def main():
    if DEST.exists():
        raise RuntimeError(f"Publication target exists; refusing overwrite: {DEST}")
    manifest = {"schema": "manual-monitor-additional-evidence/1",
                "scope": "allowlisted human decisions/interventions and online Task output/events only",
                "excluded": ["credentials", "native verifier", "hidden tests", "solution",
                             "task workspace", "trial/container configs", "private assistant sessions",
                             "raw provider request bodies"],
                "cases": {}}
    for case, (control_root, agent_root) in CASES.items():
        entries = []
        for source, relative in allowed_sources(control_root, agent_root):
            original = source.read_bytes()
            text = original.decode("utf-8", errors="replace")
            redactions = {}
            for pattern, replacement in SECRET_PATTERNS:
                text, count = pattern.subn(replacement, text)
                if count:
                    redactions[pattern.pattern] = count
            exported = text.encode("utf-8")
            target = DEST / case / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(exported)
            entries.append({"path": f"{case}/{relative}",
                            "source_relative": str(source.relative_to(SOURCE if source.is_relative_to(SOURCE) else BENCH)).replace("\\", "/"),
                            "source_sha256": sha(original), "exported_sha256": sha(exported),
                            "exported_bytes": len(exported), "redaction_counts": redactions})
        manifest["cases"][case] = entries
    (DEST / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"cases": {key: len(value) for key, value in manifest["cases"].items()},
                      "exported_files": sum(map(len, manifest["cases"].values()))}, indent=2))


if __name__ == "__main__":
    main()
