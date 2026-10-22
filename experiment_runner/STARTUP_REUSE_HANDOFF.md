# Startup reuse: implementation handoff

## Scope and status

Base: `103cdebaa93d0b7446fffcd8ef7d8af069f9405c` of this repository.

This is an **add-only integration patch**, not a change to the running experiment,
PMA prompts, Task image, tests or scoring. It supplies executable cache and
prompt-change classification code. It does **not yet wire these helpers into the
current launcher or replace its certificate gate**. Cherry-picking it alone does
not enable end-to-end fast startup. The integration points below are explicit so
the development thread can reuse the code instead of redesigning it.

Do not merge into or hot-edit an in-flight run. Keep the current run's source and
configuration frozen. No model, Task or official evaluation was invoked while
authoring this patch. No dependency bundle was built here: Docker is unavailable.

## 1. Prepare evaluation dependencies once

Files:
- `evaluation_cache.py`: publish/verify/restore, cached preparation, Docker build CLI.
- `sqlite_eval_cache_builder.sh`: runs **inside** the online builder container.
- `test_evaluation_cache.py`: standard-library tests with synthetic files/commands.

Use the existing host Python and Docker Desktop's Linux engine. Host Bash or a
`python3` command is not needed. From the repository root, in PowerShell:

```powershell
$PY = 'E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe'
& $PY -B -m experiment_runner.evaluation_cache build 'E:\LongContext\evaluation-cache' --base-image '<actual-task-image>@sha256:<verified-registry-digest>'
```

The placeholder must be replaced with the actual trusted Task base image's
immutable registry digest. A Docker image ID, mutable tag, or arbitrary Ubuntu
image is not interchangeable with that reference. Confirm the actual Task image
and platform from the launcher/Docker metadata; do not guess a digest.

The explicit `build` command:
1. Starts a disposable online builder from that image; downloads curl `.deb`
   dependencies, uv/uvx 0.9.5, managed Python 3.13 and the pinned pytest packages.
2. Publishes an allowlisted bundle under a host cache directory, independent of
   run cleanup. The full resolved Python version and all payload file hashes are
   recorded. It does not copy the Task workspace, tests, credentials or all of HOME.
3. Starts a **new container with `--network none`** and restores/checks dependencies
   without loading SQLite tests. Only success writes `OFFLINE_READY.json` bound
   to the manifest and payload hashes.

`COMPLETE` means the payload was atomically published, **not** that the clean
offline acceptance ran. `prepare_cached` requires both the frozen manifest hash
and the matching offline-ready record. Failed acceptance cannot silently yield a
usable cache hit. These records are integrity bookkeeping from a trusted local
builder, not cryptographic authentication of arbitrary third-party binaries.

Daily evaluation must use the resulting bundle, not call `build` again. The
`verify` subcommand checks bundle structure/integrity only; it is not an execution
permit or a substitute for `require_offline_ready`.

### Minimal verifier integration

Let `D` be:
`method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/`.

In `D/native_shared_verifier.py::NativeSharedVerifier.verify`, retain the stopped
agent, original evaluator byte checks, fresh report checks, single test entry and
CTRF validation. In a separately selected cached-preparation branch, after those
preparation prerequisites, call:

```python
from experiment_runner.evaluation_cache import prepare_cached

await prepare_cached(
    self.environment.exec,
    self.environment.upload_file,
    bundle_path,
    frozen_bundle_identity,
    record_stage,
    expected_manifest_sha256=frozen_manifest_sha256,
)
```

The caller must independently match the actual container base image/platform to
the frozen identity; an identity copied only from the bundle is not enough.
The helper intentionally cannot discover a trustworthy Docker image digest from
inside the container.

Continue using `evaluation_bootstrap.effective_script` and the byte-preserved
test/reward suffix after preparation. Record `persistent_bundle_v1` separately
from `bootstrap_retry_v1`. Freeze the bundle path/reference, identity and manifest
hash in the ordinary run configuration; propagate/check them through **all** of:
the unified entry, single-run plan, manifest/config hash, batch precheck, live spec
and verifier. Do not repeat the earlier omission at batch precheck. These are
integration requirements, not already-supported JSON fields in the current CLI.

On cache miss/corruption/platform mismatch/offline check failure, do not silently
download or run tests. Classify the failure as preparation failure and preserve
`reward=unavailable`. Check host cache availability during normal preparation so
a missing bundle is discovered before spending model calls. Explicitly rebuild
the cache outside the episode if necessary.

The restore code rejects target symlinks/hardlinks and unlisted files in its
dependency roots. It does not delete Task-created files to make them fit. `.deb`
installation uses only manifest-listed files, never a glob over existing files.
This protects the Task product but means conflicting Task-side changes can still
produce a clear preparation failure. It is not universal environment repair.

Initial Docker acceptance and Windows mount-path behavior still need to be tested
on the development machine. Same-image dependency restoration and frozen package
resolution are disclosed preparation changes, not a claim of byte-for-byte
equivalence to old online preparation. No performance number is claimed yet.

## 2. Reuse infrastructure validation for prompt-text-only edits

Files: `runtime_reuse.py`, `test_runtime_reuse.py`.

The classifier parses, but never executes, `gap_prompts.py`. Only literal text in
`MAINTENANCE`, `ATTENTION` and replacement **new text** is normalized. Replacement
search keys/order/container shape, imports, functions and other executable code
remain part of the runtime fingerprint. Merely editing a file with that name is
not enough to qualify for the short path.

The CLI validates committed A/B evidence using the original verifier in an
independent clean baseline checkout. It records baseline proof plus current full
source/runtime/prompt/config fingerprints. It never rewrites the old certificate,
claims the new prompts were exercised in the old run, or grants authorization.

```powershell
& $PY -B -m experiment_runner.runtime_reuse --help
& $PY -B -m experiment_runner.runtime_reuse --baseline '<clean-validated-baseline-checkout>' --current '<current-checkout>' --evidence 'method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/gap_prompt_cert_final_20261022' --baseline-config '<private-baseline-config.json>' --current-config '<private-current-config.json>'
```

Evidence path must actually belong to and validate against the chosen baseline;
the example name is not permission to borrow a mismatched certificate. Output
fingerprints contain repository-relative paths, not configuration contents.

Default inventory is deliberately conservative: every tracked file, no extension
wildcard exclusions. Reviewed exact Markdown paths can be listed with repeated
`--documentation`; only validated baseline evidence is automatically excluded.
Unknown files, new unclassified archives, changed configuration or executable
logic request full checking. Thus this patch does **not** claim arbitrary task,
configuration and archive changes already have a fast path. Clean source
checkouts are required; do not delete the user's unrelated files to satisfy this
helper. A clean worktree can be used instead. Avoid redirecting output to an
untracked file inside a checkout being inspected.

### Minimal gate integration

`D/prepare_six_task_manifest.py` currently couples current source identity and
`single_run_certification.verify_evidence`. Adapt that decision, not the method:

- On a verified infrastructure reuse candidate, keep the **current** source
  identity, record the baseline infrastructure proof separately, and run the
  existing short prompt/agent/host tests under the pinned worker import paths.
- Do not fill current source hashes with old certificate hashes.
- Do not treat `proof_verified=False`, self-authored `passed` JSON or the
  classifier's candidate flag alone as a passing gate.
- Preserve current task/config validation, one-use authorization and safety gates
  in `single_run.py` and the batch controller.
- Real execution archives still record their actual source and prompt identities.
- New executable code, transport/evaluator/adapter changes require the relevant
  integration checks. Introducing these helpers is itself an infrastructure
  change; future literal-only prompt edits are what can use the shorter path.

`integration_status=adapter_only_existing_gates_unchanged` is intentional. The
development thread must make this small gate adaptation before claiming a speedup.
Do not merely add a new planner step while leaving a mandatory full fake-chain
rerun behind it.

## Validation performed here

```text
Python 3.12.14, standard library only
python -B -m unittest discover -s experiment_runner -p 'test_*.py' -v
bash -n experiment_runner/sqlite_eval_cache_builder.sh
```

The tests use synthetic payloads, mock Docker commands and temporary Git repos.
A test log containing `CLEAN_OFFLINE_ACCEPTANCE_PASSED` can be mock output; it is
not evidence that this environment ran Docker. No real bundle, model, Task or
official score was produced. The development machine's existing Python 3.13.14
should be retained, not replaced to match the authoring environment.

Next development work is limited to the above adapters plus one actual clean
offline Docker restore test. Do not change the running experiment, rebuild the
method, introduce another review role, or make unrelated framework changes.
