# B02 Kitex development repeat — results and audit handoff

Execution commit: `38816b3a3eb758a97120116a898f26188d345acc`.
Batch: `m1-p-kitex-b02-20260929`. Task: `roadmapbench:ktx-0.13.0-roadmap`.
Both records launched once, serially, from independent containers. No record-level retry,
post-result tuning, additional model run, evaluator rerun, or mechanism change occurred.

| Record / run ID | Native result | Task chat spans | Supervisor successful usage rows / attempts | Final decision |
|---|---|---:|---:|---|
| kitex-m1 / pilot-b02-20260929-01 | 1/6, reward 0.3 | 87 | 94 / 95 | allow completion-4 |
| kitex-m1-p / pilot-b02-20260929-02 | 1/6, reward 0.3 | 117 | 102 / 102 | allow completion-3 |

Task chat spans are an OTel count, not a substitute for all response/attempt counters.
M1 had one retryable provider error followed by successful attempt 2; this was transport
recovery within the same record. P had no recorded Supervisor retry. Neither hit 300 turns
or the task wall deadline. Native trial exception_info is null, wrapper return code is 0,
and round_end_seen is true. Both archived GA process return codes are 143 and stderr contains
a multiprocessing semaphore cleanup warning; these facts are retained, not rewritten as clean
process exits. Agent execution lasted approximately 31m59s / 36m38s; native evaluation
approximately 76.9s / 20.2s (M1 / P). Exact times are in FACTS.json and original result.json.

## Identity and scope

Supervisor is M1 `746a695adac4325d6440941d384d543d1364fef9`; Task source is
`8b67de43cebf51d73b4327065713428cb049f161`. P source bytes and SHA are recorded
in operator/authorization.json and each pilot_binding.json. Actual bundled Monitor source
hashes were checked against the bindings; no mismatch was found. pilot_source_identity
records the container import path and commits. launch_identity.json preserves effective
credential-free profiles, launcher import hashes and LF/CRLF equivalence.

Both final adapter receipts show max_turns=300, Monitor enabled, correct profiles and
GA_MONITOR_ARTIFACT_DIR=/logs/agent/monitor. budget_enabled=false; DCEC and semantic
continuation are enabled, view=4000, native review cap=20. Image/mount health observations
are in operator/health.jsonl. The Task actual request model is Opus 4.8 in raw OTel.
Supervisor Opus 4.8 is evidenced by the effective runtime profile and native provider path;
do not misdescribe the Task-only OTel model evidence as a separate Supervisor wire capture.
No continuation event was recorded in either trajectory.

## First audit observations — not a candidate verdict

Both Supervisors made substantive public-requirement corrections, followed repair, returned
to root completion, and ultimately relaxed. Each has three ordinary intervention delivery
records and two completion-boundary continue decisions. M1 ultimately allows completion-4,
not completion-3; P allows completion-3. The raw control/tool evidence, rather than delivery
counts alone, must be used to examine proposal invalidation and repair uptake.

Both final approvals also rely on incomplete scope support. KEY_EVENTS.md identifies a
public-requirement-based M1 default-protocol concern that was withdrawn after insufficient
grep evidence, and P's structural-presence checks being promoted to broad Target 6 / root
support. These are independent of using verifier scores as semantic ground truth.

No clear candidate-attributable improvement is established by this initial audit. Equal
scores do not prove equivalence; more Task calls do not prove stronger/weaker supervision.
The visible P trajectory does not by itself establish the proposed short-path comparison
as the cause of a useful observation. Unrecorded private reasoning is not reconstructed.
Preserve the positive corrections and negative closure evidence together. Main-thread raw
audit and set-level interpretation remain pending; no promotion/freeze decision is made here.

## Raw evidence and publication boundaries

Each record contains original trial/agent/monitor/monitor_private/audit/dialogue.jsonl,
provider_history.json, request_attempts.jsonl, provider_usage.jsonl, reviews.jsonl,
progress.jsonl, command outputs, working.md, delivery feedback, runtime receipts,
task_evidence, Task output, native verifier stdout/rewards and trial/job metadata.
Full completion checkpoint tar files are preserved unchanged. Their extracted metadata is
also present; expanded task/workspace duplicates are not tracked in Git because those exact
files are distributed inside the original tar. PUBLICATION_INDEX.json describes both forms.
The mutable .task_view navigation duplicate is excluded with original source paths listed
in EXCLUSIONS.json; original events and checkpoint snapshots are retained.

Formal root: method_discovery/diagnostics/m1_p_launch_preparation_20260928/formal_kitex_b02_20260929.
Public projection: this directory, record names unchanged. Private profiles, mykey and gateway
credential files are not published. Raw bytes are not normalized for presentation.
file_manifest.json covers published files (except itself); archive_integrity.json records the
source-byte comparison and privacy scan. OTel is under each proof/raw_trace.jsonl.
Two already-committed preparation files (REGISTRATION.md and identity_check.json) have LF
Git blobs and CRLF runtime copies. Their manifest entries separately record both hashes and
deterministically checked normalized equality. No original scientific raw file was changed.

Usage is preserved by input/output/cache-read/cache-creation buckets in FACTS.json; do not
collapse cache buckets into fresh input or invent dollar rates. Dollar cost and aggregate task
waiting latency are not established here; raw timing/control data are retained for audit.
The runner's original valid=true is archived telemetry, not our scientific validity verdict.
The old four-record batch and all its missing-artifact declarations/scores remain untouched.
M1 remains provisional; P is not promoted. D1 remains closed; D2 remains deferred.
