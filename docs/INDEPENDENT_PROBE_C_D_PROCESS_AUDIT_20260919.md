# C/D local-verification process audit (2026-09-19)

Scope: frozen `app_metadata_defaults` checkpoint and the 9 confirmed-label
questions derived from the same Fyne turn-60 state. This is an offline audit of
the already completed run; no model was called for this audit. The full
redacted results and transport lifecycle logs are in
`transport_diagnostic/full_cd_20260919/`. The raw local `audit.jsonl` was not
published because it embeds the entire original task and public event bodies.

## What the labels do and do not show

C and D each finished 8 of 9 confirmed-label questions and matched the label
on those eight. Both exhausted the six-logical-call budget on the root
completion question; neither root result was scored. These are not nine
independent tasks, but nine questions about one checkpoint. C used 71,958
recorded tokens across the eight completed groups, D 181,067. Including the
two unfinished root groups gives 211,374 and 268,310 respectively. No
accuracy advantage for D was observed; retain C as the simpler working
baseline, not as a proven final method.

`score_local_result()` only checks an explicit completed `outcome` against the
label. It does not grade the supporting explanation. The D build-only result
correctly said `unresolved`, but also claimed successful compilation confirms
all required types, methods, functions, and signatures. This is false within
the same checkpoint: the JSON case identifies a required `string` parameter
versus an implemented `[]byte` parameter despite a successful build. C's
build-only explanation did not make that overclaim. Thus a label match cannot
be treated as evidence-scope correctness, especially if reasoning is later
passed back to a parent Supervisor. This is a manual process finding, not a
new automatic score.

## Root-completion tool sequence

All six provider calls in each root group returned HTTP 200 and a completed
stream. The budget was consumed by tool requests, not transport retries.

| Group | Phase | Model tool calls after reading task | Returned evidence | End |
| --- | --- | --- | --- | --- |
| C | Direct | `file_read(public_events)`; then starts 6, 8, 10, 12, 18 with large counts | Each event read reached the 20,000-character cap and returned `truncated=true` plus `next_read` | Six-call budget exhausted; no verdict |
| D | Expectation then evidence | Read task, committed seven-target expectation; evidence reads `public_events` at starts 1, 6, 8, 110 | Each event read reached the 20,000-character cap; last read still had a `next_read` | Six-call budget exhausted; no verdict |

The task read returned 178 lines / 14,467 characters without truncation.
The event log has 117 JSONL lines, many individually very long. C's six event
reads began at lines 1, 6, 8, 10, 12, and 18. D's four evidence reads began at
1, 6, 8, and 110. Every event read returned exactly 20,000 characters and a
continuation cursor. Both groups spent their budget before opening any of the
four permitted implementation files (`theme/json.go`,
`data/binding/sprintf.go`, `menu.go`, `driver/desktop/app.go`).

The following is the redacted call/return trace extracted from the local
`audit.jsonl`. `next` is the reader's `(start, offset)` continuation; every
event-log return was truncated. No event content is reproduced.

| Group | Call | Requested `start,count` | Returned `lines,chars` | `next` |
| --- | ---: | --- | --- | --- |
| C | 1 | event log default | 6, 20000 | 6, 7273 |
| C | 2 | 6, 112 | 3, 20000 | 8, 8436 |
| C | 3 | 8, 110 | 3, 20000 | 10, 9310 |
| C | 4 | 10, 108 | 3, 20000 | 12, 2677 |
| C | 5 | 12, 105 | 7, 20000 | 18, 3821 |
| C | 6 | 18, 99 | 5, 20000 | 22, 3886 |
| D | 3 | event log default | 6, 20000 | 6, 7273 |
| D | 4 | 6, 112 | 3, 20000 | 8, 8436 |
| D | 5 | 8, 110 | 3, 20000 | 10, 9310 |
| D | 6 | 110, 10 | 4, 20000 | 113, 2954 |

D's calls 1–2 were the untruncated original-task read and expectation commit.
In C, call 1 also read the untruncated original task. Neither group used an
`offset` argument in any request.

The lower-level `MonitorWorkspace.read_text()` accepts `offset` and
`max_chars`, and its `next_read` supplies them for mid-line continuation.
`IndependentVerifier._dispatch()` forwards these arguments if present, but
`IndependentVerifier._tools()` exposes only `path/start/count/tail` to the
model. The model therefore cannot directly submit the exact continuation
cursor that the reader returns. In this run C repeatedly restarted within or
near the same long JSONL region. D eventually jumped to the end, but still
did not inspect implementation files or finish. This is a specific interface
gap; the audit cannot prove it is the sole cause of the budget exhaustion.

## Experimental implication

Do not increase the budget or rewrite the probe based on these two failures.
First distinguish whether a parent Supervisor can choose a decision-relevant
local question itself, then use C to investigate it under the same total
budget as direct root verification. Include an acceptable/no-intervention
state, and audit both verdict and evidential basis. D remains an ablation,
not the default. This tests question selection rather than merely giving the
model a manually named defect and file list.
