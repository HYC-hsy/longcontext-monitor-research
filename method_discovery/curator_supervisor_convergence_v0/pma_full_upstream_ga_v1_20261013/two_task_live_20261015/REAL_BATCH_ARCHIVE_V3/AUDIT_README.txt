PMA/GA two-task discovery pilot — mechanical audit, 2026-10-15

Scope and identity
  Frozen running HEAD: bfbb4103f4d694ecd4cb0afc62e38a27a5974743
  Reviewed starting baseline: 1127f3cb89c5ca1680dc4a27859e6756f4362fe0
  Frozen manifest: ../MANIFEST_FROZEN_V3.json
  Manifest raw SHA-256: 68ede4f156bbb66e018538995154f4a37fb6c7676c56bf02ac1959092461c60c
  Batch ID: pma-ga-headless-cancel-20261015-r1
  One-use authorization raw SHA-256: 914dbd08614191b53f08e3248cff588401b677639170729603fc7a6e890ec31f
  Original private batch root: E:\pma-ga-two-task-live-20261015-r1
  Active AUTHORIZATION.json was moved to AUTHORIZATION.consumed.json after all four runs; no new run can use its original path. The redacted historical authorization is retained in raw/control/AUTHORIZATION.json.
  Official Terminal-Bench-2 source: 2fd12b88aafdd04a52c298e3940bcb189f9766d6.
  Full upstream PMA vendor: 89e5c0d6aadfe531a1aee42fd290d48be89973dd (unchanged).
  Native Harbor source: 459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc.
  Task profile byte SHA-256: ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e.
  PMA profile byte SHA-256: cc5f784b069034f44bc4527d15acd70191b1f7fc5810556c087b7b35e0ae00f1.
  Resolved model names: Task claude-opus-4-8; PMA claude-opus-4-8. Full public parameters and image/test identities are in the frozen manifest. Private credentials and endpoint are not published.
  Each task declared 900 seconds native agent and verifier; study agent limit was 300 Task turns and 14400 seconds including PMA, with multiplier 16; native verifier multiplier 1 (900 seconds). Whole-trial retries: 0.

Zero-model gate
  The archived zero_model_certification directory contains the actual four-slot fake-transport Harbor/Docker lifecycle, request bodies, PMA two-stage fake requests, reminder insertion, synthetic evaluator and cleanup proofs. The final targeted unittest returned "Ran 2 tests in 237.932s — OK"; its standalone console stream was not separately retained, while controller stdout/stderr and per-file raw fixture results were retained. Earlier fixture attempts are preserved privately at E:\pma-two-task-v3-fixture-precommit-20261015-01 through -04; the first stopped after an offline evaluator status was misclassified, the second used a wrong external GA source, the third did not yet exercise synthetic native evaluation, and the fourth completed. These are not counted as final certification. A separate existing six-task regression run had 13 tests with 2 errors and 1 skip; the historical V2 source identity correctly rejected the new source, and the missing PYTHONPATH test passed when rerun with the actual external adapter path. These failures were not deleted or presented as green.
  Disposable image preflights confirmed official Git-blob test.sh bytes, read-only /tests mounts, shell syntax, ordinary network/permissions, dependency executables, pytest and CTRF availability. The official assertions were not run in preflight. Both actual images and official verifier files are identified in the manifest.

Actual serial run (not a statistical comparison)
  Order  Task                Condition  Run ID                           Task ready/attempt/response  selected tools  PMA phase1/phase2  reminders appended  terminal          native CTRF     reward  cleanup
  1      headless-terminal   A no PMA   pma-ga-hl-a-r1-20261015          14/14/14                     13              0/0                0                   CURRENT_TASK_DONE  7 pass, 0 fail  1.0     confirmed
  2      headless-terminal   B PMA      pma-ga-hl-b-r1-20261015          21/21/21                     20              21/21              5                   CURRENT_TASK_DONE  7 pass, 0 fail  1.0     confirmed
  3      cancel-async-tasks  B PMA      pma-ga-ca-b-r1-20261015          2/2/2                        1               2/2                0                   CURRENT_TASK_DONE  6 pass, 0 fail  1.0     confirmed
  4      cancel-async-tasks  A no PMA   pma-ga-ca-a-r1-20261015          2/2/2                        1               0/0                0                   CURRENT_TASK_DONE  5 pass, 1 fail  0.0     confirmed
  Four attempted, zero unstarted, no batch stop reason, four native_recorded results. A reward of 0.0 in slot 4 is an executed test failure, not a missing score or infrastructure zero. CTRF report and native stdout for each slot are retained under raw/arms/NN/jobs/.../verifier/.
  Task request_ready, actual request_attempt, parsed visible response, provider usage, tool-selection and termination events are retained in each raw/arms/NN/jobs/.../agent/research_events.jsonl. All 39 ready requests had 39 visible attempts and 39 visible responses. The observed Task request attempt counts do not reveal provider-internal network retries. B memory_transport.jsonl records 42 and 4 completed stage calls respectively; inner LiteLLM network attempts and PMA token usage were not reliably observable and are unknown. The PMA profile field max_retries=8 is not the upstream stop_after_attempt(3) mechanism.
  In headless B, five reminder outcomes in raw/arms/02/host_private/archive/events.jsonl correspond to five pma_reminder_appended events in that arm's research_events.jsonl; actual subsequent Task request payloads are available there. In cancel B, both stages completed twice, with no reminder returned. Neither silence nor the four rewards is interpreted as method quality by this audit.

Evidence locations and limits
  MECHANICAL_SUMMARY.json: structured per-slot counts and outcomes.
  raw/control/BATCH_RESULT.json: controller dispositions, independent launcher/cleanup/native statuses, and not-started list.
  raw/arms/NN/archive/: public command, start/mount and end/freeze barriers, verification release, native execution/report checks, raw Harbor and worker stdout/stderr, final status.
  raw/arms/NN/jobs/: preserved Harbor result, Task request/response/tool events, CTRF, reward and native test stdout.
  raw/arms/02 and /03/host_private/archive/: PMA public-event receipts, phase inputs and transport status, saved bank and trajectory. A slots have no PMA worker/archive.
  FULL_LOCAL_FILE_INDEX.json indexes the 2,630 files in the private original tree by source byte size/hash; ARCHIVED_FILE_INDEX.json indexes each redacted published raw file against the original byte identity. FILE_HASHES.tsv indexes the uploaded files; raw_trajectories.zip is a convenience copy, not a substitute for individual raw files.
  CODE_DIFF_BASELINE_TO_RUN.txt contains the complete Python source diff from the reviewed baseline to the frozen run; ARCHIVE_ONLY_DIFF.txt describes the later mechanical archive generalization. No running source, fixed PMA vendor, Task task content, or official evaluator was changed during the four-slot batch.
  The preserved evidence is limited to the existing capture boundaries: user-visible Task request content and parsed visible response blocks are recorded, hidden thinking is excluded, supplier-internal attempts are unknown, and Task request_ready alone does not prove delivery. The private original tree remains outside Git; the published copy is UTF-8 redacted. The private-profile extractor found no literal secret values in the two profile files, provider URL fields were already redacted at capture, and an additional bearer/sk-token scan found no matches; this is a bounded scan, not a proof that arbitrary sensitive text is impossible. The original terminal console capture was truncated by the interactive tool, but per-slot status and Harbor stdout/stderr files are complete.
  A/B differ by fixed original PMA and any resultant Task behavior; this is a two-task, one-repeat discovery comparison, not a controlled equal-compute ablation or a general effectiveness finding. Semantic review is left to the primary researcher.

Cleanup and archival attempt
  Batch-owned Python/Docker processes and containers: none observed after completion. Each slot recorded cleanup_confirmed=true, remaining_containers=[], native report checked, and writer/freeze barrier files. Batch authorization original active path absent after consumption.
  First archive attempt was set aside privately at E:\pma-ga-two-task-archive-attempt01-20261015 because the older archiver included unrelated legacy compatibility files and labelled the four-slot summary as six-task. The mechanical archiver was then narrowly generalized after the run, and this new archive excludes those legacy files. The old attempt is retained, not used as evidence for this batch. One Copy-Item request to uppercase BATCH_RESULT raised a harmless Windows case-insensitive self-copy error; the existing lowercase file was read successfully. This failure is not hidden.
  No extra Task, PMA, native evaluation, training or scoring call was made during archival.
