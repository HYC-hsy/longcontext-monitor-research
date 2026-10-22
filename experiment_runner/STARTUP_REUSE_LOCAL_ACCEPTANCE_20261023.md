# Startup reuse local acceptance (2026-10-23)

This is engineering evidence, not a new Task experiment or method-effect result.
No real model, official SQLite tests, or official scoring was invoked.

## Bound source and cache

- Reference patch: `1baa1ae3a3abbc7309fcce05beafc8a127834428`, locally cherry-picked as `5427101063d869fd38b87425a265d0c20a5cb6d3`.
- Windows/Docker build adaptation: `e24fadbd`; cache/runtime integration: `869d4458`.
- Trusted base: `alexgshaw/sqlite-with-gcov@sha256:f986820b00c74ce75db7288719d364df313fde7c7917bea6eb6352a08431a89f`, `linux/amd64`; Docker image ID is the same digest.
- Local-only bundle: `E:\LongContext\evaluation-cache\e89d8f9cb01928e97428507c3d364fc890fe783c21ed9bbece5cdcebe84fb5a1`.
- Bundle manifest SHA-256: `64a47e6ed79b22bca79b395baa49d7c13d95ad24cb15567bd50a520c6ed67cd0`; payload SHA-256: `780b3532dbdf7670642284cf8ddfd116652484ad414471f270961811b08d2378`.
- The explicit online builder published the bundle. A *fresh* `--network none` container restored it and printed `CLEAN_OFFLINE_ACCEPTANCE_PASSED`; `OFFLINE_READY.json` was written only after dependency-only checks. It did not load SQLite tests. The publication and offline-ready file timestamps were 23:50:09 and 23:50:34 local time; this 25-second interval is **not** a real episode startup benchmark.

`persistent_bundle_v1` is now a separate, explicit config protocol. The host checks the frozen bundle path, manifest SHA, payload inventory, original test.sh hash, actual stopped container image ID, matching RepoDigest and platform before offline restore. Cache miss or identity failure has no network fallback and no test entry. The original test suffix/reward logic remains unchanged; the preparation method is disclosed as changed.

## Verification performed

- `python -B -m unittest discover -s experiment_runner -p 'test_*.py' -q`: 116 tests, 0 failures, 0 errors, 3 skips.
- Pinned-worker-import gap suite (`test_gap*.py`): 23 tests, 0 failures/errors/skips.
- Affected host suites (`test_six_task_native_base`, `test_live_harbor_fixture`): 12 tests, 0 failures/errors, 3 skips. Historical source-bound certificate now correctly rejects changed runtime bytes.
- `test_single_run_offline`: 9 tests, 0 failures/errors, 1 skip.
- Final source A/B zero-model Harbor fixtures: A run `pma-b186b54e46c14c7a`, B run `pma-48b8852eab1a4a9a`; each controller exit 0, synthetic report present, cleanup confirmed, fake authorization removed. B made exactly maintenance→selection in each of two cycles, saved one formal gap in cycle 1, and delivered one reminder to a later fake Task request. Source-bound redacted evidence is in `startup_reuse_cert_20261023/`; original private fixture directories remain local. The committed 42-file evidence passes `single_run_certification.verify_evidence` for A/B.

The A/B fixture intentionally uses synthetic evaluation, not `persistent_bundle_v1`: that protocol requires the official SQLite evaluator identity. The clean disconnected Docker acceptance tests the cache restore separately. These two checks are not represented as one fake official evaluation. No later real cached startup has been authorized or timed, so real startup time and future download reliability remain unmeasured. A future literal-only prompt edit can use the new short gate only with a clean baseline checkout, independently verified committed A/B proof, unchanged config/runtime fingerprint, and passing pinned gap tests. This integration changed executable code and itself used the full A/B fixture.
