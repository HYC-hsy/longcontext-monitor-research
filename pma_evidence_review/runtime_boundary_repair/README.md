# PMA runtime/audit boundary engineering repair

Production baseline: `7718a6a912a139494326715fc99dea1a0b98bbc8`.
Local workspace is an isolated scoped source snapshot fetched from that commit,
not the user's active checkout and not a full Git clone. The local Git root
commit is only a snapshot; apply `production.patch` to the real production base.

The old nested Context failure was reproduced offline before editing production
sources. `baseline-reproduction.log` contains two successful *expected-failure*
tests: the full episode test requires TypeError mentioning Context in three
configurations, confirms the nested object and prior gate diagnostic-write error,
and checks that an intermediate events.jsonl line had already been written.
This proves the source defect, not the unavailable historical private traceback.
The supplied historical archive identity is retained in DEVELOPER_HANDOFF.txt.

Runtime requests retain the Context for review. v4 split_request_dto explicitly
excludes that single named runtime field before v3 split/_call and before the
outer audit row. No recursive sanitizer, default=str, repr, or Context-asdict was
added. The model still receives exactly prompt/system/tools. Existing closed B,
provenance DTOs, request hashes and selected E/X views remain; original audit
input is not deleted simply because some visible source text was not selected B.

CapturedTransport logs effective_system_sha256, effective_prompt_sha256,
effective_payload_sha256 and operation_kind at the actual send boundary before
client.call, retaining existing audit_request_sha256 and phase. No prompts changed.
This fixes request-level identity; it does not fix an unavailable local launcher
that writes the obsolete preflight review hash.

Private stack records are under `private_failures/failure-<id>.json` inside the
host-private episode, review, or worker directory (new directory mode 0700, files
0600). No frame locals are captured. Traceback/message stay private; the bridge
error DTO contains only status, error_type, failure_id and existing identity
fields. Private write failure still returns error with a safe ID, marked unsaved
only internally. NEVER include private_failures in public diagnostic archives.
The untracked Windows public-ZIP/export script is unavailable here: its exclusion
must be verified by the developer. This deliverable contains source and passing
test logs, no runtime private stack files or historical hidden material.

After acceptance, a failing event fail-stops this episode instance. last_sequence
and successful response cache advance only after all required writes. Earlier
commits and intermediate events.jsonl lines are not rolled back. A failed bridge
receipt write retains a pending outcome in that dispatcher, allowing receipt I/O
retry without re-executing maintenance. Pending cache is removed after acknowledgment.
Validation failures before acceptance do not poison a subsequent legal event.
After fail-stop ordinary task_end is rejected; the existing no-inference
finalize_without_event cleanup remains available and never certifies Task success.
These are same-process guards, not restart recovery, cancellation atomicity or
exactly-once transactions. Never restart/replay accepted maintenance automatically.

Run from repository root with the production Python environment:

    PMA_TEST_STRICT_IMPORTS=1 python -m unittest pma_evidence_review.tests.test_runtime_boundary pma_evidence_review.tests.test_ga_spool_import_boundary -v
    PMA_TEST_STRICT_IMPORTS=1 python -m pma_evidence_review.runtime_boundary_repair.run_offline_checks

Executed locally with Python 3.12: 10 focused tests and 45 targeted checks passed.
One frozen-dataset comparison-plan test is excluded because that dataset is not
part of this scoped source snapshot. No old model runs or evaluations were rerun.
Here optional shortuuid, rpds, regex and Harbor imports needed documented test
stand-ins; real gate, bank, upstream wrapper methods, episode and dispatcher run.
The worker fatal-path test substitutes only the absent Harbor import's file-path
attestation, not a production startup assertion. Re-run with the real pinned
libraries before accepting production integration. Engineering tests do not prove
model semantic correctness, generalization or absence of every engineering bug.

Publication: production-only commit `5488f3e2cfa78efc68c65f773bb2416e5415fe98`
on independent branch `fix/pma-runtime-audit-boundary-7718`, parented directly by
the production baseline. The first source-tree upload was denied; one retry was
approved only after additional trusted user evidence clarified the exact target
repository and upload request. No alternate channel, force push or default merge.
Tests and handoff are a subsequent commit; consult the final delivery for its SHA.

Deployment boundary: offline_launcher copies event_spool.py into a standalone GA
staging directory (including stateful/other adapter paths); only host PYTHONPATH
includes the research audit package. Fault imports therefore live inside the
EventDispatcher.serve_once host method, never at EventClient module import. A
fresh Python -I -S subprocess imports only event_spool.py and pma_upstream_bridge.py,
asserts the host package is unavailable, and constructs both GA clients. This is
an offline import check, not a container/Task run. Public archive exclusion of
private_failures is a developer acceptance hard gate, still unverified because
the experiment-specific exporter was not supplied; do not publish runtime log
archives until that gate is satisfied.

Strict production offline acceptance: PMA_TEST_STRICT_IMPORTS=1 prohibits dependency
stand-ins before any are installed in sys.modules; missing dependencies fail import
and block acceptance. Scripted LLM replies remain required. On Windows PowerShell,
set $env:PMA_TEST_STRICT_IMPORTS='1' before either command. Here strict mode is
blocked by missing regex/rpds/shortuuid/harbor; strict-mode-blocked.log records that
expected blocker, not a passing production run. The 10/45 passing logs are from
the explicitly disclosed stand-in environment with strict mode disabled.
