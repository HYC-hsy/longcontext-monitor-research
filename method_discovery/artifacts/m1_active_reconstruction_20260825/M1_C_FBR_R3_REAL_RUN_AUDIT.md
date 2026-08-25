# M1-C FBR r3 active-reconstruction real-run audit

## Identity and terminal state

- Run: `m1-treatment-fbr-2.43.0-roadmap-r3-active`
- Task: `roadmapbench:fbr-2.43.0-roadmap`
- Task Agent: Claude Opus 4.6
- Monitor: GPT-5.6-sol high
- Online checker: disabled
- Active reconstruction: enabled
- Agent execution: 2026-08-25 08:57:07Z to 10:26:37Z (about 89.5 minutes)
- Terminal GA return code: 143
- Terminal cause: monitor provider HTTP 400 `upstream_error`
- Native verifier: 7/7 phases, reward 1.0

The run is not a normally completed end-to-end treatment because the monitor provider failed before the open root repair episode released. The verifier score is real but disagrees with an unresolved public repository regression and must not be presented as ordinary task completion.

## Capability evidence

The active-reconstruction monitor retained several important M0 behaviors:

1. It remained silent during ordinary exploration and natural self-repair.
2. It inspected a missing Proxy import but stayed silent because the Agent was already repairing it.
3. It opened and completed a Proxy validation repair episode, inspecting flawed Agent-authored tests rather than accepting them as authority.
4. It caught a stale CORS test oracle that contradicted the immutable wildcard requirement, followed the correction, and released after focused evidence.
5. It preserved locally under-tested Request-ID and TLS obligations without blocking every UNKNOWN.
6. At the root completion claim it reconstructed global evidence, inspected recent trajectory, Git diff, and TLS test references, then requested one unpiped repository-wide test.
7. The requested test exposed a real regression in the unchanged `Test_Ctx_Accepts` test.
8. During causal isolation it allowed the Agent to investigate silently, intervened only before an unsupported production repair, and preserved the unchanged test oracle.

The final repair remained open. The Agent had established that the new standard-library MIME fallback changed the previously unmapped `text` token from octet-stream behavior to `text/plain`, breaking Accept negotiation compatibility. It had not yet found and validated the smallest contract-compatible repair when the provider failed.

## Verifier disagreement

The post-run native verifier passed all seven task phases, including its MIME fallback cases. However, the public repository-wide suite still had a failing pre-existing compatibility test:

- unchanged test: `Test_Ctx_Accepts`
- expected: `json`
- observed: `text`
- clean/stashed baseline: passed
- treatment worktree: failed

Thus the task-specific verifier covers the requested MIME fallback but not this interaction with the existing Accepts API. The monitor found a backward-compatibility defect that the native verifier did not reject. This is useful method evidence and a benchmark-coverage warning; it is not permission to use online hidden verification.

## Cost evidence

### Active-reconstruction r3

- Monitor provider calls: 105
- Monitor input tokens: 2,036,277
- Monitor output tokens: 146,137
- Task-Agent calls: 87
- Task-Agent ordinary input: 121,563
- Task-Agent cache read: 1,532,790
- Task-Agent cache creation: 213,310
- Monitor wire characters: min 43,871; max 103,249; mean 75,054; final 79,483
- Monitor decisions completed: 86
  - SILENT: 78
  - HOLD: 6
  - RELEASE: 2

### Previous bounded r2 legacy-context run

- Monitor provider calls: 100
- Monitor input tokens: 13,475,777
- Monitor output tokens: 89,592

Despite five more monitor calls, active reconstruction reduced monitor input by about 84.9% and monitor input-plus-output by about 83.8%. Wire size remained bounded rather than growing with raw history.

This supports the M1-C engineering cost claim for this run. It does not yet constitute a formal matched-budget paper result.

## M1 state

- Semantic objects: 64
- Relations: 72
- Update count: 60
- Last completed internal turn: 86
- Root ledger frozen: yes
- Rejected root mutations: 0

No new state explosion occurred.

## Decision

- M1-C cost repair: strong positive real-run evidence.
- M0 capability preservation under active reconstruction: strong partial evidence, including multiple complete repair loops and a valuable root-completion catch.
- M1 task-effectiveness acceptance: no; the run ended with an open repair episode and provider failure.
- Native 1.0 score: retain as verifier output, but pair with the unresolved repository-regression finding.
- Automatic rerun: prohibited pending review of this result and the next experimental decision.

## Primary artifacts

- Job: `long_context_bench/output/m1_real_tasks/treatment/fbr-2.43.0-roadmap/jobs/m1-treatment-fbr-2.43.0-roadmap-r3-active`
- Trial: `.../fbr-2.43.0-roadmap__UKpBCTU`
- Monitor decisions and state: `.../agent/m0_monitor`
- Public/research trace: `.../agent/research_events.jsonl`
- Verifier result: `.../verifier/reward.json`
- Verifier stdout: `.../verifier/test-stdout.txt`
