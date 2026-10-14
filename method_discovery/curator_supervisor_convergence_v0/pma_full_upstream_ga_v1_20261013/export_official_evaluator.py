"""One-use binary export of the two fixed official evaluator trees."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


COMMIT = "2fd12b88aafdd04a52c298e3940bcb189f9766d6"
EXPECTED_SH = {
    "db-wal-recovery": "4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334",
    "fix-code-vulnerability": "f1611da693cb4cfc5e8482698c6a1858a5c67220ae9db89b50aed66584e9b17f",
}
STAGE = Path(__file__).resolve().parent / "posthoc_official_20261014"


def git(source: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(source), *args], check=True,
                          capture_output=True).stdout


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-git", type=Path, required=True)
    args = parser.parse_args()
    source = args.source_git.resolve(strict=True)
    if git(source, "rev-parse", "FETCH_HEAD").decode().strip() != COMMIT:
        raise RuntimeError("official source commit mismatch")
    if STAGE.exists():
        raise FileExistsError(STAGE)
    listing = git(source, "ls-tree", "-r", "-z", COMMIT).split(b"\0")
    selected = []
    for row in listing:
        if not row:
            continue
        identity, filename = row.split(b"\t", 1)
        mode, kind, blob = identity.decode("ascii").split()
        name = filename.decode("utf-8")
        if not any(name.startswith(task + "/tests/") for task in EXPECTED_SH):
            continue
        if kind != "blob" or mode not in ("100644", "100755"):
            raise RuntimeError(f"unexpected official evaluator member: {name}")
        raw = git(source, "cat-file", "blob", blob)
        selected.append((name, mode, blob, raw))
    expected_names = {f"{task}/tests/{name}" for task in EXPECTED_SH
                      for name in ("test.sh", "test_outputs.py")}
    if {item[0] for item in selected} != expected_names:
        raise RuntimeError("official evaluator file set differs from expected source")
    for name, _, _, raw in selected:
        task = name.split("/", 1)[0]
        if name.endswith("/test.sh") and hashlib.sha256(raw).hexdigest() != EXPECTED_SH[task]:
            raise RuntimeError(f"official test.sh hash mismatch: {task}")
    STAGE.mkdir()
    members = []
    for name, mode, blob, raw in selected:
        destination = STAGE / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(raw)
        if destination.read_bytes() != raw:
            raise RuntimeError(f"official blob export readback mismatch: {name}")
        members.append({"path": name, "git_blob": blob, "mode": mode,
                        "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                        "crlf": raw.count(b"\r\n"), "bare_lf": raw.count(b"\n") - raw.count(b"\r\n"),
                        "bare_cr": raw.count(b"\r") - raw.count(b"\r\n"),
                        "utf8_bom": raw.startswith(b"\xef\xbb\xbf")})
    provenance = {"source": "https://github.com/harbor-framework/terminal-bench-2",
                  "commit": COMMIT, "export": "git cat-file blob to binary write_bytes",
                  "members": members,
                  "amendment": "Earlier Windows worktree evaluator hashes describe newline-transformed bytes; "
                               "this independent tree restores fixed upstream Git blobs without changing prior records."}
    (STAGE / "PROVENANCE_AMENDMENT.json").write_text(
        json.dumps(provenance, indent=2), encoding="utf-8")
    print(json.dumps({"commit": COMMIT, "members": members}, indent=2))


if __name__ == "__main__":
    main()
