"""Create one-use S2/R2 static authorization only after the code gate is frozen."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from static_source_live import code_commit, profile_identity
from static_source_screen import MANIFEST_V2, ordered_slots, sha256, verify_public_projection


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--authorization-out", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    args = parser.parse_args()
    if any(path.exists() for path in (args.manifest_out, args.authorization_out,
                                      args.output_root)):
        raise FileExistsError("one-use batch identity already exists")
    draft = json.loads(MANIFEST_V2.read_text(encoding="utf-8"))
    if draft.get("execution_authorized") is not False:
        raise PermissionError("research draft must remain unauthorized")
    profile_identity(args.profile)
    for case in draft["cases"]:
        verify_public_projection(case)
    batch_id = "source-v2-" + uuid.uuid4().hex[:12]
    bindings = []
    for order, (task, variant) in enumerate(ordered_slots(draft), 1):
        run_id = f"{batch_id}-{order:02d}-{variant.lower()}"
        bindings.append({"order": order, "task": task, "variant": variant,
                         "run_id": run_id,
                         "run_root": str((args.output_root / run_id).resolve())})
    manifest = {**draft, "schema": "pma-source-memory-static-live-batch-v2",
                "status": "frozen_waiting_for_single_use_authorization",
                "batch_id": batch_id, "run_bindings": bindings}
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.authorization_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    auth = {"execution_authorized": True, "authorization_source": "user-transferred S2/R2 six-slot instruction",
            "manifest_sha256": sha256(args.manifest_out), "code_commit": code_commit(),
            "profile_sha256": sha256(args.profile), "batch_id": batch_id,
            "run_bindings": bindings, "output_root": str(args.output_root.resolve())}
    args.authorization_out.write_text(json.dumps(auth, ensure_ascii=False, indent=2) + "\n",
                                      encoding="utf-8")
    print(json.dumps({"batch_id": batch_id, "code_commit": auth["code_commit"],
                      "manifest_sha256": auth["manifest_sha256"], "slots": len(bindings)}))


if __name__ == "__main__":
    main()
