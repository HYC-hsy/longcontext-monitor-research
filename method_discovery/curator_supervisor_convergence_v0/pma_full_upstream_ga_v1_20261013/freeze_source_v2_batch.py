"""Create one-use S2/R2 static authorization only after the code gate is frozen."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import uuid

from static_source_live import code_commit, profile_identity
from static_source_screen import (BATCH_SCHEMA, MANIFEST_V2, ordered_slots, plan_slots,
                                  resolve_config, selected_cases, sha256,
                                  verify_public_projection)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--authorization-out", type=Path)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--profile", type=Path)
    parser.add_argument("--plan", type=Path, help="v3 selection-only, unauthorized config")
    parser.add_argument("--authorize", action="store_true", help="separate future authorization step")
    parser.add_argument("--authorization-source")
    args = parser.parse_args()
    if args.plan is not None and args.authorize:
        raise ValueError("prepare and authorize are separate steps")
    if args.authorize:
        if (not args.authorization_out or not args.profile or not args.authorization_source or
                args.authorization_out.exists() or args.output_root.exists()):
            raise PermissionError("new one-use authorization requires explicit identity and unused roots")
        frozen = json.loads(args.manifest_out.read_text(encoding="utf-8"))
        if frozen.get("schema") != BATCH_SCHEMA or frozen.get("code_commit") != code_commit():
            raise PermissionError("frozen v3 code identity mismatch")
        bindings = frozen["run_bindings"]
        plan_slots(frozen)
        if any(not isinstance(b.get("run_id"), str) or b["run_id"] in {"", ".", ".."}
               or "/" in b["run_id"] or "\\" in b["run_id"] for b in bindings):
            raise PermissionError("frozen run ID must be one path segment")
        if any(b.get("run_root") != str((args.output_root / b["run_id"]).resolve())
               for b in bindings):
            raise PermissionError("authorization output root differs from frozen bindings")
        if any(Path(b["run_root"]).exists() for b in bindings):
            raise FileExistsError("frozen slot root already exists")
        profile_identity(args.profile)
        auth = {"execution_authorized": True, "authorization_source": args.authorization_source,
                "manifest_sha256": sha256(args.manifest_out), "code_commit": code_commit(),
                "profile_sha256": sha256(args.profile), "batch_id": frozen["batch_id"],
                "asset_registry_sha256": frozen["asset_registry_sha256"],
                "run_bindings": bindings, "output_root": str(args.output_root.resolve())}
        args.authorization_out.parent.mkdir(parents=True, exist_ok=True)
        args.authorization_out.write_text(json.dumps(auth, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf-8")
        print(json.dumps({"batch_id": frozen["batch_id"], "authorization_created": True,
                          "manifest_sha256": auth["manifest_sha256"], "slots": len(bindings)}))
        return
    if any(path is not None and path.exists() for path in (args.manifest_out,
                                                           args.authorization_out, args.output_root)):
        raise FileExistsError("one-use batch identity already exists")
    draft = resolve_config(json.loads((args.plan or MANIFEST_V2).read_text(encoding="utf-8")))
    if draft.get("execution_authorized") is not False:
        raise PermissionError("research draft must remain unauthorized")
    if args.profile is not None:
        profile_identity(args.profile)
    for case in selected_cases(draft).values():
        verify_public_projection(case)
    batch_id = "source-v2-" + uuid.uuid4().hex[:12]
    bindings = []
    for identity in plan_slots(draft):
        order, task, variant, occurrence = (identity[key] for key in
                                            ("order", "case_id", "variant", "occurrence"))
        run_id = f"{batch_id}-{order:02d}-{variant.lower()}"
        binding = {"order": order, "task": task, "variant": variant,
                         "run_id": run_id,
                         "run_root": str((args.output_root / run_id).resolve())}
        if args.plan is not None:
            binding.update(case_id=task, occurrence=occurrence)
        bindings.append(binding)
    manifest = {**draft, "schema": BATCH_SCHEMA if args.plan else "pma-source-memory-static-live-batch-v2",
                "status": "frozen_waiting_for_single_use_authorization",
                "batch_id": batch_id, "run_bindings": bindings,
                **({"code_commit": code_commit()} if args.plan else {})}
    args.manifest_out.parent.mkdir(parents=True, exist_ok=True)
    args.manifest_out.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                                 encoding="utf-8")
    if args.plan is not None:
        print(json.dumps({"batch_id": batch_id, "execution_authorized": False,
                          "manifest_sha256": sha256(args.manifest_out), "slots": len(bindings)}))
        return
    if args.authorization_out is None or args.profile is None:
        raise ValueError("legacy freeze requires authorization-out and profile")
    args.authorization_out.parent.mkdir(parents=True, exist_ok=True)
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
