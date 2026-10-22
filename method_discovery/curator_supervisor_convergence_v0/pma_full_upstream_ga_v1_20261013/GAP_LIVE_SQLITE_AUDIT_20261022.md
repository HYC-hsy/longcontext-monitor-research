# PMA gap SQLite single-episode diagnostic (2026-10-22)

This is a **time-relaxed diagnostic**, not a result under the task's original
900-second Agent limit. The task, image, resources and native verifier were not
changed. The executed code was commit
`56c04d0f5a686bb6c25b10914282a17aec2d3aa8`; the later archival commit
contains no change to that run's loaded source.

## Identity and pre-run checks

- Fixed entry: `python -m experiment_runner` with `catalog`, `plan`, `prepare`,
  then `run`; one serial `sqlite-with-gcov` occurrence, method `pma-gap`,
  B / `pma_gap_memory_v0`. Fresh run ID: `pma-b51303f481d04569`.
- Official task source: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`;
  image `alexgshaw/sqlite-with-gcov:20251031`, digest
  `sha256:f986820b00c74ce75db7288719d364df313fde7c7917bea6eb6352a08431a89f`.
- Task and PMA model identity: `claude-opus-4-8`, using the pre-existing private
  profiles. No profile body, endpoint or credential is included here.
- Requested Agent time and Task turns: `uncapped`; resolved effective Agent
  seconds, Task turns and research outer deadline: `null`. Native verifier
  timeout: 900 seconds. This does not relax individual request timeouts.
- Manifest raw SHA-256:
  `a03668640293b02c265c6cc18a99cd540f20c503a969025cbf1609b5a083d239`;
  frozen config hash:
  `908dbb31b860a1d32a67db54ba96a89694b660adb505cae3cc98c18dcf85140a`.
  The one-time nonfake authorization matched this manifest and run ID. Its
  private file SHA-256 was
  `93ee8449f0a2b350efa1b8655849b20a0f70b73d50562c2636b71147bbfd9432`;
  the file was removed after the run.
- `fake_only=false`; no fake provider or synthetic evaluator was carried into
  this episode. The final-code A/B Harbor full-fake certificate, separately
  committed under `gap_single_run_cert_final_20261022`, passed mechanical
  `verify_evidence` for `pma_gap_memory_v0`. The unified `experiment_runner`
  fake prepare/run also completed with the same candidate. Fake reward is not
  this run's reward.

## Observed execution

The new candidate initialized, then Task issued 19 generation requests with
19 observable responses. It selected 18 `code_run` tool calls and performed
19 memory cycles. The private host recorded 90 completed auxiliary role
calls: maintenance 19, gap review 19, gap-only repair 17, re-review 16, and
Phase 2 selection 19. These are logical/completed transport records; the
auxiliary transport does not separately expose a trustworthy count of physical
HTTP attempts or retry sub-attempts. Task-side `provider_request_attempt`
records show 19 generation attempts. No additional real diagnostic probe or
second Task episode was started.

Three gap cycles were accepted and 16 retained the previous formal gap view
as stale. The first accepted cycle ended with an empty formal gap list after
one revision; this is a model judgment, not a host proof that no obligations
remained. Many later reviews rejected or failed to accept the candidate even
after the one permitted gap-only revision. At step 18, an accepted gap
correctly recorded that `/app/sqlite/bin` had an executable but PATH
availability was still unverified/incomplete. At step 19, the attempted gap
update failed with `gap ID not found`; the prior formal gap remained and the
view was marked stale. Ordinary PMA/Task execution continued under the
specified fail-soft rule. These facts do not establish that the reviewer's
semantic judgments were all correct.

Phase 2 selected three reminders during package-installation troubleshooting.
They were appended at actor attempts 7, 8 and 10, each appeared in a prepared
Task request, a provider attempt, and a corresponding provider response.
Thus **three were observably delivered**, not merely generated. The Task
continued with real tool actions afterward; this single trajectory does not
isolate the reminders' causal effect. Later Phase 2 decisions, including the
final cycle, were silent. No last-minute generated-but-unconsumed reminder was
counted as delivered.

Task produced a normal completion proposal at turn 19 and the GA recorded
`CURRENT_TASK_DONE`; the PMA sidecar saved `task_end` and exited cleanly.
Task's final text claimed that the build and PATH requirement were complete.
The single native evaluation was released after writers stopped and returned
**reward 0.0** (three tests, zero passed). Its recorded failure is consistent
with the evaluator not resolving `sqlite3` from its execution environment;
the public report does not reproduce hidden test source or traceback. The
Task's final claim therefore is not evidence of task success. Agent execution
ran from 10:30:38 to 10:50:10 UTC; verification ran from 10:50:27 to
10:56:51 UTC. This was not a 900-second-Agent-protocol run.

Visible Task usage records sum to 24,198 input tokens, 5,963 output tokens,
14,959 cache-creation input tokens and 171,288 cache-read input tokens, each
over 19 responses. Auxiliary usage and a reliable dollar charge were not
available in the retained transport summary; neither is estimated from text
length or logical calls. No external native-count HTTP prerequisite was used
for this gap method.

Harbor and worker returned exit code 0. The native evaluator ran once;
there was no re-evaluation. The launcher reports `cleanup_confirmed=true`,
no remaining owned containers or volume, and no cleanup errors. A separate
post-run `docker ps` check found no running containers. The one-time
authorization was removed. The private original logs and result records
remain in the run directory; they were not rewritten to turn reward 0 into a
success.

## Verification and evidence boundary

- Local interpreter: `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`
  (Python 3.13.14). `experiment_runner` regression: 67/67; gap-directed
  regression: 28/28 (including the pre-existing 26); affected ordinary PMA
  regression: 6/6. Full-fake Harbor A/B certificate passed; the actual unified
  frontend fake run reached the gap candidate and native synthetic verifier.
- [GAP_LIVE_SQLITE_PRIVATE_HASHES_20261022.md](GAP_LIVE_SQLITE_PRIVATE_HASHES_20261022.md)
  indexes original private bytes. The index is not a claim that the originals
  were uploaded. The present prose is a manually reviewed, reduced public
  description; no raw private message, hidden reasoning, credential, endpoint
  or hidden verifier content is copied here.
- Engineering chain: **passed** (unified entry, candidate, Task tools, native
  evaluation, cleanup). SQLite task: **failed** (`reward=0.0`). The gap method
  was exercised but stale in 16/19 cycles. One diagnostic task cannot prove
  improvement over ordinary PMA or pure GA; the different time protocol also
  precludes a matched comparison with prior runs.

No follow-up episode, parameter search, model probe or extra evaluation was
run. The run is closed pending separate research review.
