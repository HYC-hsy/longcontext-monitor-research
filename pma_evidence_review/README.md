# PMA evidence reviewer v1

Standalone frozen-cycle evidence audit. **No online memory integration, memory writes,
curator retry, judge, Task, official evaluation, or completion gate.** Only the offline
fake paths were tested. The code has an explicit future real-client entry point, but
real model semantics, client/provider behavior and task outcomes are untested.

## Reproduce the offline acceptance

Check out the independent branch, then pin its delivered commit SHA from the release
report. The parent is `72152913f545ca36a75b68e8796e24a6e24f9f81`; do not substitute
`main`. The three upstream exact versions and every adapted function are in
[REUSE.md](REUSE.md). All code needed for offline execution is in this repository,
including the existing graded locator and its Apache-licensed LangExtract subset.

Use an **already available Python >=3.10**; do not reinstall Python to imitate a
previous environment. This acceptance used `/opt/homebrew/bin/python3.11` (3.11.15).
The core parser also passed under the system 3.9.6, but the existing locator uses
`dataclass(slots=True)` and therefore requires >=3.10. From repository root:

```bash
PYTHON=/opt/homebrew/bin/python3.11  # or your existing Python >=3.10
"$PYTHON" -m pip install --target .review-deps -r pma_evidence_review/requirements.txt
export PYTHONPATH="$PWD/.review-deps${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
"$PYTHON" -m unittest discover -s pma_evidence_review/tests -v
"$PYTHON" -m pma_evidence_review --help
```

Dependency installation may use a package registry. The **tests themselves** block
socket connect and use only scripted fake clients. No model package or NLI download
is needed for offline acceptance. No original tests, rewards or experiment artifacts
are rewritten. `TEST_RECORD.md` distinguishes tested behavior from limitations.

## Build real development inputs without copying new fixtures

The builder reads the already public index at:

`method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/source_window_two_real_20261025/INDEX.json`

```bash
"$PYTHON" -m pma_evidence_review build --repo . --sample sqlite --out /tmp/sqlite-review-input.json
"$PYTHON" -m pma_evidence_review build --repo . --sample html --out /tmp/html-review-input.json
"$PYTHON" -m pma_evidence_review validate --input /tmp/sqlite-review-input.json
"$PYTHON" -m pma_evidence_review export --input /tmp/sqlite-review-input.json --out /tmp/sqlite-extraction-request.json
```

Output files use exclusive creation: choose a fresh path instead of overwriting
previous evidence. SQLite selects step 14 / maintenance call 27 / cycle
`cycle_fbce65422ff14eeb82b3879bc5fd25fa`; HTML selects step 2 / call 3 / cycle
`cycle_76e8f85e13394b84a2bdea40ec901c2c`. They are **development samples, not holdout**.

The input contains `original_task`, the exact public `maintenance_prompt`, pre-cycle
revision snapshots, current write/delete operations, typed visible source slices,
manifest identities and offsets, replay status and limitations.
`request_sha256` identifies only the maintenance prompt; `review_input_sha256`
independently binds the canonical complete review material and cycle provenance.
Validation checks both, including operation content digests, sequential before/revision
consistency, and deletion target content. Re-sealing changed candidate content produces
a different input identity; hashes are not authentication or proof of historical origin.
Old packets lacking the full input identity must be rebuilt, not silently accepted. It does not contain
reward, selection decisions, hidden tests, later Task behavior, phase2 responses,
`should_inject`, `context_for_action` or `actual_phase2_prompt`. The old instructions
inside the maintenance prompt are explicitly treated as quoted audited material.

See [中文交接与接口契约](HANDOFF.md) for the reusable core interface.

The final `memory.json.gz` is opened only as a historical identity archive: the
builder selects the exact manifest, pre-cycle revisions, current-operation revisions,
receipts, and same-cycle/op-index deletion tombstones. It never projects the final
bank or active revision map. The **actual maintenance prompt** is authoritative for
visible source text; final retained sources are not a substitute. SQLite C14 has 54
manifest sources and HTML C2 has 12. Operation indices join trajectory operations to
`gap_cycle.evidence_report.operations`; no tool repr is evaluated.

The root index binds the slot index; each read gzip and its decompressed bytes are
checked against the slot index. Source handles and visibility refs use the existing
protocol hash formulas. Prompt SHA must match `manifest.request_sha256`. A different cycle can be selected
with **both** `--step N --cycle-id ID`. Missing identities/content are refused.
`--allow-redacted` explicitly marks a changed public prompt as degraded and removes
source-coordinate claims. It does not restore omitted text or waive revision integrity
checks; a redacted historical revision can still cause refusal. SQLite C6–C13 must
not be described as original-equivalent replay merely because the public text loads.
No truncation is added; original public omissions remain visible in the original text
and in replay limitations. Large inputs may exceed a future model's limit: v1 exports
whole requests and does not silently truncate them.

## Run an entirely synthetic fake audit

Create synthetic fixtures in a private scratch directory:

```bash
mkdir /tmp/pma-review-synthetic-v1
"$PYTHON" - <<'PY'
import json
from pathlib import Path
from pma_evidence_review.tests.fixtures import packet, extraction, result
root = Path('/tmp/pma-review-synthetic-v1')
(root/'input.json').write_text(json.dumps(packet()))
(root/'responses.json').write_text(json.dumps([extraction(True), result(), result()]))
(root/'extraction.json').write_text(extraction(True))
PY
"$PYTHON" -m pma_evidence_review fake --input /tmp/pma-review-synthetic-v1/input.json --responses /tmp/pma-review-synthetic-v1/responses.json --out /tmp/pma-review-synthetic-v1/run
"$PYTHON" -m pma_evidence_review export --input /tmp/pma-review-synthetic-v1/input.json --extraction-response /tmp/pma-review-synthetic-v1/extraction.json --out /tmp/pma-review-synthetic-v1/all-requests.json
```

Expected: 3 client calls, 0 network/model calls, two scripted `insufficient` results.
This is **not** an assertion that a model would produce those claims or verdicts.
The tests additionally construct requests from both real public cycles with fake
responses: SQLite 4 calls (1 extraction + 3 checks), HTML 5 (1 + 4).

Run output:

- `requests.jsonl`: exact system/prompt/tools passed to the client, with phase and call index.
- `responses.jsonl`: every raw content string or call error type; no client/profile serialization.
- `report.json`: extracted claims with exact spans and operation/kind/condition/dependency
  identity, extraction coverage, item results, source alignment, limitations and call counts.

Each factual or deletion item has `supported`, `contradicted`, or `insufficient` **only
when parsed**. Missing, duplicate, unknown, malformed and failed calls produce explicit
engineering status and null verdict. Unlocatable/fuzzy-only evidence keeps the raw
model verdict separately. A lexical match is not a semantic proof; alternatives are
not independent corroboration. Nonfactual plans/hypotheses/questions retain their types
and receive `not_applicable_nonfactual`; their independently extracted factual premises
can still be checked. Empty/incomplete extraction remains an error, not “no issues”.
Coverage is a model assertion with structural checks; v1 cannot deterministically
prove that a model extracted every implicit claim. There is no support-rate threshold
or automatic write/delete/gap closure.

The default explicitly exercises RAG's **single-claim evidence-first** prompt.
`--mode batch` uses its actual batch prompt instead. Batch fake responses must be a
JSON array with one unique `claim_index` per claim; the parser reconstructs input
order and reports missing indices. Export with `--extraction-response` uses the same
builders as execution. There is no live extraction hidden in export.

## Future real-client path (not executed here)

`run-profile` reuses the existing pinned `episode.construct_upstream` and its
profile adapter; only the returned `_memory_llm.call` is invoked, never its memory
process or actor. The existing PMA/Harbor dependency environment must already be
usable (see `D/vendor/pma_89e5c0d/pyproject.toml` and its README; `D` is the parent of
the public index). Offline dependencies alone do not provide that live runtime.
The factory and captured call contract were tested with an injected fake; native
factory initialization/provider calls were not tested or claimed validated.

Without `--execute-authorized-real-model`, this command refuses **before opening a
profile**. Only after a new explicit user authorization naming frozen input(s),
existing profile/model, execution scope and capture handling may an operator run:

```text
python -m pma_evidence_review run-profile --repo . --input INPUT.json --profile EXISTING_PRIVATE_PROFILE.json --profile-key claude_monitor_opus48 --out NEW_PRIVATE_DIRECTORY --execute-authorized-real-model
```

Record actual resource use and retry behavior. Apply only limits explicitly requested
by the user or required by the existing model configuration; do not invent new ceilings.
This flag is an execution switch, not evidence that authorization was granted. Do not
run it as a connectivity test in the current phase. No credentials are embedded in
requests or reports. Keep captures private; never publish real inputs, raw responses,
profiles, or client-native logs by default. Call counts are measured at `llm.call`:
future native provider retries/HTTP attempts require the existing provider capture
instrumentation and must not be reported as equal to logical calls. No semantic
experiment or curator repair loop was performed.

## Labels, grouping and future comparison

1. Freeze inputs and their SHA/visibility boundary first. SQLite/HTML and any derived
   variants remain development material. Do not random-split cycles from the same run
   across development and holdout; group by task/run and shared source ancestry.
2. Keep independent labels in a separate evaluator-only directory, keyed by frozen
   input SHA + operation index + claim identity. Do not place labels, diagnostic prose,
   expected answers or native rewards in input JSON, extraction responses or prompts.
   There are currently **no human labels** supplied by this component.
3. Before future semantic comparison, freeze an ordinary evidence-audit baseline and
   the candidate evidence-first mechanism on identical visible material, target
   operations, model and budgets. Predeclare whether extraction is shared/frozen or
   jointly evaluated, and account for all extraction calls. Batch versus single-claim
   is a prompt/call-budget ablation, not automatically the ordinary baseline.
4. Measure extraction coverage/type preservation, unsupported-closure detection,
   false contradiction, justified abstention, engineering failures, evidence identity
   correctness, latency and actual provider attempts/tokens/cost. Include benign
   controls, deletion cases and scoped successes. Report disagreements separately from
   gold correctness; do not use an overall support rate as an operational gate.
5. Freeze the method before untouched grouped holdout evaluation. Any real semantic
   calls, online integration, curator revision loop, Task, or official evaluation
   require separately scoped user authorization. This release claims neither semantic
   superiority nor holdout performance.
