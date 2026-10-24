# PMA-gap evidence-write v1: local acceptance (zero-model)

This acceptance used the existing Windows Python 3.13.14 environment and Docker Engine 29.6.1. It did **not** call a real model, start a real Task episode, or run official SQLite tests/scoring. The fixture's synthetic reward is not a method result.

## Source and dependency identity

- Upstream delivery: `450114a29a4825c59c15f5448b1d1577276ec43f` (runtime commit `2ab84f82e485e8efb9c63323a4a375a200d67c54`); accepted by ordinary merge because the development branch had diverged.
- Final execution-source commit: `f552fd7e766c9addabf92d614772cbff2d091240`. The later certification commit `0ceb943f559cb65c39eb52e3f92208b60a1f4a1b` adds evidence and a byte-preserving `.gitattributes` rule, not runtime code.
- Interpreter: `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`, Python 3.13.14. `rpds-py==2026.9.1` installed from `evidence_requirements.txt` with the existing `uv` because this interpreter has no `pip` module.
- `MemoryEnabledTerminus2` resolved to the pinned `vendor/pma_89e5c0d/src`; `Terminus2` and `BaseLLM` to that vendor's `external/harbor/src`; `EvidenceGapMemory` and `EvidenceGapMemoryAgent` to this directory. No vendor implementation was edited.

## Offline verification and repair of local test prerequisites

- `pytest -q -rs -p no:cacheprovider` on `test_gap*.py` plus `experiment_runner`: **203 passed, 3 skipped**. The three pre-existing skips require Windows symlink privilege (`test_evaluation_cache.py` twice, `test_runtime_reuse.py` once).
- Four affected GA test files (`test_pma_upstream_ga_bridge.py`, `test_pma_capture_boundary.py`, `test_pma_upstream_parity.py`, `test_task_complete_response.py`): first **39 passed, 3 failed** because the historical parity test's pinned `research_library` checkout was absent. A byte-matched local copy of pinned PMA source was supplied at the expected ignored fixture path; rerun **42 passed**. No assertion or vendor source was weakened.
- The first A/B collector attempt rejected `B/memory.json` with `history identity mismatch`. The generic redactor had reformatted a hash-bearing source ID beginning with `[` despite reporting zero redactions. The collector now preserves the original structured-memory bytes only after a secret/hidden/URL scan confirms no sanitization is needed; otherwise it fails closed. Two new regression tests passed. The failed first attempt was retained locally and is not presented as certification.
- `test_gap_evidence_scenarios.py` passed its five development scenarios: inferred information gap from the task requirement, test-quality gap grounded in visible weak-assertion code, achievement-gap revision plus a useful procedural record, atomic rejection of a bad replacement with Phase 2 continuing, and gap visibility when ordinary BM25 filtering activates above fifty records. These are fixed-response contract tests, not real-model quality findings.

## Final-source Harbor A/B certification

Committed redacted files and per-file original/public SHA-256 identities are in [cert_evidence_gap_v1_final_20261025](cert_evidence_gap_v1_final_20261025/FILE_HASHES.json). All **43** staged blobs matched their public SHA-256 in the index; `verify_evidence(require_committed=True, research_candidate='pma_gap_evidence_v1')` passed.

| Condition | Run ID | Task requests | Worker/cleanup | Distinguishing observation |
| --- | --- | ---: | --- | --- |
| A, pure GA | `pma-80f748076bf04931` | 2 | clean | No PMA reminder or auxiliary calls |
| B, evidence-gap | `pma-ba9b3f1e28c249dd` | 2 | clean | Two `maintenance → selection` cycles; a bound gap with receipt/source; reminder in later Task request |

Both used synthetic tool execution and synthetic native evaluation, with zero real generation and zero official scoring. The B certification verifier checks the committed bound gap, task-request reminder binding, two-stage phase set, source/vendor identity, and cleanup. The later selection was silent; it did not newly inject the old reminder.

## Unified configuration entry

A new **local-only** fake configuration selected one `sqlite-with-gcov` slot, `method=pma-gap-evidence`, `condition=B`, `research_candidate=pma_gap_evidence_v1`, `fake_only=true`, and the committed certificate above. `experiment_runner plan → prepare → run` all succeeded. The frozen runtime policy was `agent_timeout=uncapped`, `task_turns=uncapped`, `verifier_timeout=official`; this is a fixture setting, not a real protocol score. The run ID was `pma-ba7e0f831c2a4967`.

The unified run recorded two fake Task requests, two accepted evidence batches, one formal gap, one source, one revision, one receipt, and four auxiliary phase calls in order `maintenance, selection, maintenance, selection`. One reminder was attached to the later Task request; no review/repair role appeared. Its synthetic evaluator returned a report, but no official SQLite assertion was run. The worker exited 0, `remaining_containers=[]`, owned volumes were clean, and the one-use fake authorization file was removed.

Private original hashes (SHA-256, bytes as saved locally; private paths/profiles are not published):

| Artifact | SHA-256 |
| --- | --- |
| Fake config | `e60d33d99f68765dca92ee5db0ae9a2a8b201565d3c92baebb5e4279e8a5630a` |
| Resolved plan | `cdd4e2a0bdabad9dabe65a3f3affd94454267b05e505a306292cb910bfa5f16f` |
| Prepared manifest | `a5889322cd3330a159a37bd64dbffc6199c083ac6994928add90f0a95d61abc9` |
| Selection result | `b7e22d24ed95e45d98855a7f8fe8b61fc48d2a899f3719623982f01cf4533656` |
| Unified run live result | `8d758ea94c23647b3fc20f0ee1f2bf33a6e09984e39cd554581cac095e6f2db1` |

No private profile, endpoint, credential, hidden reasoning, hidden test, or complete private runtime log is included. Fixed fake responses prove wiring and failure boundaries, not that a real model will choose valid evidence or improve task outcomes. The older `pma-gap` baseline remains a separate candidate and was not modified here.
