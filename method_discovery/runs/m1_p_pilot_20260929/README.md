# M1/P four-record pilot: raw archive and execution audit

These are development records, not held-out results. No P effectiveness verdict
is asserted. Original artifacts are retained; no scientific record was restarted.
Source preparation `337758d`, empty-directory repair `a7efbe4`, authorization
rebind `e0f9ed79a51e5cc609eed148cfb51236324e3d1b`.

| Record | Native phases / reward | Original completion/archive status |
|---|---|---|
| Kitex M1 / 01 | 3/6; 0.6 | Original runner finalized, `valid=true` |
| Kitex M1+P / 02 | 1/6; 0.3 | Original runner finalized, `valid=true`; Task reached 180 calls |
| Ratatui M1+P / 03 | 0/6; 0.0 | Original runner finalized, `valid=true`; Task reached 180 calls |
| Ratatui M1 / 04 | 0/6; 0.0 | Agent ended with `[ROUND END]`; host processes disappeared before native evaluation/finalization; evaluation recovered separately |

Reward is the benchmark's own weighted result, not phases_passed/total_phases.
`valid=true` is the original runner's validation output, **not** a certification
that all research requirements, parameters or Supervisor archives were satisfied.

## Confirmed execution deviations

1. The experimental launcher clears inherited `GA_*` environment and sets
   `GA_MAX_TURNS=300`, but does not set `GA_BASELINE_CONDITION`. In the pinned
   `run_ultralong_m12_proofs.py::stage4_agent_kwargs`, an absent baseline condition
   returns `{}` before forwarding max turns and monitor adapter options. All
   original trial configs lack those kwargs. The pinned adapter defaults to
   `max_turns=180` and passes that as the actual Task subprocess environment.
   Compose's `GA_MAX_TURNS=300` does not override the per-exec environment.
   Both P records have exactly 180 Task chat spans and end their protocol without
   evidence here of a final Supervisor release. The lower ceiling is a material
   deviation from authorization; no post-result fix or retake was performed.
2. The same omitted adapter options leave `monitor_enabled=false` at the Harbor
   adapter boundary, so it does not set `GA_MONITOR_ARTIFACT_DIR=/logs/agent/monitor`.
   The common compose environment still enables the actual Monitor/DCEC worker;
   Monitor is **not absent**. Its default archive is instead under
   `/opt/genericagent/temp/clean_monitor/<run_id>`, outside downloaded agent logs.
   The first three task containers were deleted by the original runner. Their
   raw dialogue, provider history, attempts, working state, receipts and
   continuation archives are absent from surviving host artifacts. This archive
   does not invent or reconstruct those files. Task/public traces cannot replace
   full Supervisor reasoning/control-chain provenance.
3. The serial operator's last status was RUNNING_RECORD for record 04, PID 2696.
   Neither that process nor the serial operator remained alive at audit; both
   tool sessions were unknown. stdout/stderr were empty. No reliable exit cause
   or host return code survives; do not infer a crash cause from container uptime.
   Record 04's Task had already ended, no Agent/Monitor process remained, and
   its output contained `[ROUND END]`. Its container/gateway remained alive.
   Original `result.json`, final proof manifest and native verifier outputs had
   not been produced. No fake original completion manifest was generated.

## Fourth-record recovery (no Agent/model rerun)

Original Task logs and the complete surviving Monitor directory were copied
from the existing container before evaluation. `recovery/monitor/` includes
raw dialogue, progress, reviews, provider history, usage, attempts, working
state, command receipts and live checkpoint archives. This Monitor made 87
successful recorded request attempts; 87 usage rows; 10 recorded reviews:
9 waits and final `allow_complete` for `completion-3`. See raw reviews rather
than treating these action counts as correctness judgments.

The still-unchanged completed task container received the native Ratatui tests
from the same frozen task cache. `/tests/test.sh` SHA256:
`e93a2b53cff4fdc025bc84149c0a61a1fb891f0f5128084cffecfdfb8f1715ba`.
Host and uploaded bytes matched. Neither reward nor verifier stdout existed
before this first evaluation. `timeout 1800 bash /tests/test.sh` was executed
once with stdout/stderr redirected to the normal verifier log, exit 0.
`recovery/verifier/` contains original results, not a regenerated score. The
small recovery exit marker contains literal `0n` due shell quoting; the actual
execution tool returned exit 0. The marker is retained without correction.

All six Ratatui phases, in **both** records, failed before behavioral assertions
because offline Cargo could not download `unicode-segmentation v1.12.0`.
No network or dependency repair was supplied. Consequently 0/6 is not evidence
that all six implemented behaviors were semantically wrong or that M1/P are
equivalent. Task handling of the limitation remains separate trajectory evidence.

`recovery/tracked_diff_post_verifier.patch` is a tracked Git diff obtained after
native evaluation; it is not labelled a pre-verifier snapshot and does not
include untracked Task-created files. Full record 04 workspace remains local
under `recovery_originals_20260929/workspace_post_verifier`, including files
uploaded by evaluation, and is not projected to any Agent. Final workspace/patch
payloads for records 01–03 are absent from the surviving host archive; Task
tool/edit traces are retained but are not substitutes for exact final snapshots.

## Counters, source identities and audit limits

`FACTS.json` is mechanically computed from raw files. It contains Task chat-span
counts (111, 180, 180, 119), separate uncached input/output/cache-read/cache-write
token buckets, model names, native rewards, and available Supervisor counters.
Task spans are not a count of HTTP attempts; retries for unavailable Monitor
logs remain unknown. No missing usage, USD cost or Supervisor counts are filled
with zeros. Raw span timestamps and original trial timing fields are retained.
No overall precision spending cap is asserted.

Every surviving bundle's Monitor files were rehashed against its binding; no
mismatches. Bindings record exact frozen M1, Task source, P hash and P-on/off.
Task OTel reports `claude-opus-4-8`. First-three Supervisor actual request identity
and all-step P adoption cannot be fully independently checked without missing
raw provider artifacts; configuration expectation is not promoted to evidence.

`trial/` and `proof/` hold original completed-record outputs. `recovery/` is
explicitly separate. Secret profiles, mykey files, gateway secret configurations,
researcher credentials and full duplicated source bundles are excluded.
`file_manifest.json` gives original-byte hashes of the copied files.
The redundant `.task_view` workspace (including its nested Git repository) is
not added to the public commit; original live-checkpoint tar files are retained
with their manifests/identities, and the full recovered directory remains local.
The public file manifest excludes that redundant directory.

This panel is execution-deviated and provenance-limited. Kitex scores are facts,
not a stable causal verdict on P. Ratatui outcome discrimination is blocked by
the frozen offline dependency limitation. The main research thread decides the
scientific disposition; no automatic rerun, tuning, model call or new panel is
authorized by this audit. M1 anchor, D1 closure and D2 deferral are unchanged.
