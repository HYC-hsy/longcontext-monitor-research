# Evidence-only Phase 1 revision guidance repair

## Scope

Local base: `9c6208ae6ba1b8a934234ba45b8c19cb88d38281`. The coordinating review verified the four prior runtime files against runtime `61b560af601a1658f55e35183807d639743ca190`; publication must preserve the later archive base `0059ea0604787a8a424eddecdaa9b32530f5ece3`, not overwrite it with this older local tree.

Only evidence_gap_agent.py changes runtime behavior: the actual Phase 1 system composition replaces the two legacy gap revision instructions with same-ID memory_save_gap(content, evidence, memory_id) guidance. Ordinary pma-gap, pinned vendor text, Phase 2, exact evidence binding, operation isolation and admission policy are unchanged. Explicit deletion of resolved, duplicate or unsupported gaps remains available.

Exact replacement anchors are checked for one occurrence in regression tests, without introducing a runtime launch gate. Tests capture actual structured-tools and XML-fallback sends, not just an isolated string helper. They also check the ordinary gap sender remains byte-for-byte PHASE1_SYSTEM + MAINTENANCE and Phase 2 remains unchanged.

SHA-256 of the changed runtime file (LF bytes):
`evidence_gap_agent.py`: `531b0cf62ca707fd2cdcdd0a593813b4a122d9cf5aeb28f9ce779b10105ba47d`

## Validation

Cloud Python 3.12 in the existing /tmp/pma_evidence_repair_env, no model provider calls.

From this candidate directory, set LITELLM_LOCAL_MODEL_COST_MAP=True and PYTHONPATH to this directory, vendor/pma_89e5c0d/src, repository root, and repository root/experiment_runner; run:

    python -m pytest tests/test_gap*.py <repository>/experiment_runner -q

Result: 231 passed, 185 subtests passed; `logs/gap_runner.txt`.
Focused agent tests: 36 passed, 19 subtests passed (included in the aggregate count).
An initial aggregate invocation omitted experiment_runner from PYTHONPATH and failed collection with ModuleNotFoundError: evaluation_cache. The corrected invocation above passed; no code or test expectations were relaxed.

Affected GA seam/parity/complete-response tests: 42 passed, 38 subtests passed; captured terminal summary and command in `logs/ga_affected.txt`. No old runtime hashes or historical manifests are rewritten.

## Stop boundary

Local validation made no provider calls, real Task runs, or new full-chain certification. Publication is handled separately by the coordinating thread; this patch does not authorize a new real run. Historical fake certificates do not certify the new outgoing prompt. Before a future real run, use the existing final-source fake acceptance procedure under the normal independent launch gate. This is a prompt-contract engineering fix, not evidence of model compliance or improved task scores.
