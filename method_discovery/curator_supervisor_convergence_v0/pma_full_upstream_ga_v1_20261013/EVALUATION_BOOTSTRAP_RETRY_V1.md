# SQLite evaluation-only bootstrap_retry_v1

This is an opt-in evaluator preparation protocol, not a change to the Task,
method, assertion files, test selection, CTRF report interpretation, or reward
mapping. Select it with top-level experiment configuration
`"evaluation_bootstrap_protocol": "bootstrap_retry_v1"`; omission means the
original protocol. It is accepted only for real `sqlite-with-gcov` preparation.
The value is copied into the single-run plan, frozen manifest method config and
hash, live spec, and verifier receipt. The host checks manifest/spec equality.

The pinned original `test.sh` is SHA-256
`4770437ea96c3cc84684b4f99d55fb148fcac09f9ea1e8ef49de487716e6c334`.
For this exact byte string only, the code separates the known installation
prefix at the unique `# Check if we're in a valid working directory` boundary.
The remaining original test/reward suffix is copied byte-for-byte. The effective
script SHA-256 is
`574e48fdbcac3c837a07f1589f2dfdc0e168ed431d56fbdeb664e725bc186a21`.
It sources the installed uv environment and sets `UV_OFFLINE=1`, preventing
`uvx` from turning first test execution into an unclassified download attempt.
Original and effective identities are recorded separately. Neither original
file nor hidden assertion content is modified.

Preparation runs after stopped-agent and evaluator-source hash checks. APT
uses `Acquire::Retries=3` for failed files and `APT::Update::Error-Mode=any`;
the existing package set remains `curl`. The pinned uv 0.9.5 installer fetch
uses finite curl retries and pipefail. The host checks `curl`, `uvx 0.9.5`,
the resolved `pytest==8.4.1` and `pytest-json-ctrf==0.3.5`, and the `--ctrf`
plugin option without importing or executing task tests. Installed uvx binary
SHA-256 and command output hashes are recorded. Each preparation command has a
600-second request timeout; there is no shell loop around APT and no replay of
the whole test script. A failed stage is `bootstrap_failed`, with zero test
starts. Once ready, Harbor enters the byte-preserved test suffix exactly once.
Test assertion failure is not a bootstrap failure. Missing/invalid current
CTRF still makes reward unavailable, even if the shell returns zero.

The archive records `bootstrap_retry_v1_stages/*.json`, an optional
`bootstrap_retry_v1_test_started.json`, and terminal
`bootstrap_retry_v1.json`. These are separate from the original evaluator
upload and test-execution records. Existing source and evaluator-file identity
checks remain enabled. Future live runs require certification for this new
source version; no old certificate was rewritten here.

## Offline and isolated validation (2026-10-22)

Interpreter: `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`
(Python 3.13.14). `pytest==8.4.1` was installed into that local test
environment to execute the existing pytest-style evaluator delivery tests;
this does not change the task image or repository package requirements.

Final commands and exit codes:

- `python -B -m unittest ...tests.test_evaluation_bootstrap -q`: 14 passed,
  0 failures/errors/skips, exit 0.
- `python -B -m unittest discover -s experiment_runner -t . -p test_*.py -v`:
  68 passed, 0 failures/errors/skips, exit 0.
- `python -B -m unittest ...test_live_evaluator_delivery ...test_live_wiring
  ...tests.test_evaluation_bootstrap -q`: 20 passed, exit 0.
- With `PMA_OFFICIAL_SOURCE_GIT=E:\pma_d1_tb2_source_20261017`,
  `python -B -m pytest .../test_live_evaluator_delivery.py -q`: 12 passed,
  exit 0. The first invocation without that required fixed-source setting had
  10 passed and 2 setup errors; it was rerun after restoring the existing
  local source path, with no task test or scoring run.

Synthetic fault injection covered recoverable first 502 (represented as an
APT-internal retry, one host invocation), exhausted 502 at each preparation
stage, missing curl, uv dependency acquisition failure, wrong versions,
signature/hash failure, stale reports, missing report after test start,
synthetic test assertion failure, and unchanged original-mode dispatch. It
does not claim to have recreated an actual network 502 inside the container.
An initial harness run failed because the existing `_atomic` helper is
create-once; the implementation now uses append-only numbered stage records
and a single terminal receipt. No failed test is hidden from this account.

Clean temporary container: image
`alexgshaw/sqlite-with-gcov:20251031`, image ID
`sha256:f986820b00c74ce75db7288719d364df313fde7c7917bea6eb6352a08431a89f`.
APT update/install, curl installer, `uvx --version`, uvx dependency resolution,
and offline `pytest --help | grep -- --ctrf` succeeded. Observed versions:
curl `8.5.0-2ubuntu10.16`, ca-certificates
`20260816ubuntu0.24.04.1`, uvx `0.9.5`, pytest `8.4.1`,
pytest-json-ctrf `0.3.5`. Observed uvx SHA-256:
`421b1bb58429180a04ade98da066b5a5b6763e8ed74edef97359701c4cb42db8`.
Only a synthetic `SYNTHETIC_TEST_BOUNDARY_REACHED` sentinel ran; the official
SQLite tests, Task, model, and evaluator were not invoked. The identified
temporary container was removed, and `docker ps -a` no longer listed it.

## Old episode, read-only

`pma-d1847af4750941c0` ended its Task. Its original task package has
Dockerfile SHA-256 `f4be72b64b710962e5d9d5236716b4823ec72401a5379423039101cc00a73cd6`
and test file SHA-256
`b165f8504bb93a901451b80c4ea73344b71b6af377ebdabef745fbcdd1d2993b`.
The old container and model-channel volume no longer exist; `public_task/solution`
is empty and the archived artifact manifest says `empty`. The archive contains
Task/evaluator logs, but no immutable post-Task workspace/product snapshot
that would establish exactly what could be re-evaluated. `agent_end_native.json`
SHA-256 is `8e961f78c64ce1cade2807ed0a98f11d143414d18e1407dc0922bcec4b1777cb`;
artifact-manifest SHA-256 is
`fec9d4db2bfa276936207948d76ec87d47d8ffe9d29f54ca6aa25dfa2446817f`.
No re-evaluation or reconstruction was attempted; its reward remains
`unavailable`.

Remaining limitations: APT and uv downloads still depend on live upstream
availability. The original test script pins direct Python package versions but
not every transitive artifact hash; uv's installer reports no checksum to
verify. This protocol checks observed versions and results, but one successful
download does not prove future network reliability or bit-for-bit historical
environment equivalence. A separately frozen dependency image/cache would be
a different protocol and is not claimed here.
