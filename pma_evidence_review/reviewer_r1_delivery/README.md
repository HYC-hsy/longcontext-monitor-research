# v4-reviewer-r1: frozen reviewer-only comparison

This opt-in candidate replaces only `claim_split_semantic.VERIFY_SYSTEM` at parent
`be44ce85fd2ec1ce116e34a8683cbcb7a113f35e`. It does not change the v4 splitter,
batch protocol, aggregation, repair limit, deletion version binding, Phase2, default
strategy, v3, or literal quotation matching. No real model, Task, or native evaluation
was run to prepare this delivery. Fake checks demonstrate wiring, not semantic gain.

`FROZEN_CASES.json` contains the 13 previously selected development cases with their
*actual earlier v4 split outputs*, plus nine newly written, explicitly synthetic
controls. It was mechanically frozen by `freeze_cases.py` from the existing local
v4 results and `split_v4_delivery/SMALL_SAMPLES.json`. The source results-file and
label-spec byte hashes are recorded inside the frozen file. The 13 claims are never
re-split. Each new control has one claim copied from A, chosen without reading B.
Labels and reasons are evaluation-only; `export` and `run-profile` do not project them.
The two deletion cases remain separate. The generic “required tool” positive has a
referent ambiguity; retain its frozen label, flag the dispute after running, and do
not relabel based on model output.

Both arms use identical A, submitted B, optional target context, claim strings,
order, batch formatter, parser, and model-visible `prompt`/`tools`. The only
model-visible difference is `system`. Request identity changes accordingly.
No split call is made. `baseline` uses the exact saved v4 system text; the
candidate uses the new standalone system text. The current frozen identities are:

| Item | SHA-256 |
| --- | --- |
| Frozen data file bytes | `8b324515a931826e6baea7d5564f11e8f24c29c7f345c193d2c2b94ee14ae278` |
| Baseline system text | `fb6a2cf9904a9f65bfb88c44c81be334ae430b7ff93ff516617114861fde9f71` |
| Candidate system text | `1a62aa59030af907db257be59ac7ceeaa982099040fde06d980ca71bd5f949dc` |
| Baseline plan identity | `ac93327027d9abc42a8d83aa787eddf391d8c84c304361a8c7bfbae7dda7217c` |
| Candidate plan identity | `f5bf5c56f04c758bd5e618ce7dcf57e732c21b117e3ab289aa84dc33de302cb5` |

## Future real comparison (not executed here)

Run these commands from the checked-out repository root in PowerShell, using the
same existing Python, `claude_monitor_opus48` profile, model parameters and
conditions in both arms. Replace the two placeholders with confirmed absolute
paths. The result directory and export files must not already exist. The execution
flag requires a separate future authorization; it is not granted by this README.

```powershell
$PY = '<existing Python executable>'
$PROFILE = '<existing private profile JSON>'
$ROOT = (Get-Location).Path
$OUT = '<new private comparison parent directory>'
& $PY -X utf8 -B -m pma_evidence_review.reviewer_r1_compare export --arm baseline --out "$OUT/baseline-plan.json"
& $PY -X utf8 -B -m pma_evidence_review.reviewer_r1_compare export --arm v4-reviewer-r1 --out "$OUT/candidate-plan.json"
& $PY -X utf8 -B -m pma_evidence_review.reviewer_r1_compare run-profile --arm baseline --repo $ROOT --profile $PROFILE --profile-key claude_monitor_opus48 --out "$OUT/baseline-real" --execute-authorized-real-model
& $PY -X utf8 -B -m pma_evidence_review.reviewer_r1_compare run-profile --arm v4-reviewer-r1 --repo $ROOT --profile $PROFILE --profile-key claude_monitor_opus48 --out "$OUT/candidate-real" --execute-authorized-real-model
& $PY -X utf8 -B -m pma_evidence_review.reviewer_r1_compare score --arm baseline --results "$OUT/baseline-real/results.json" --out "$OUT/baseline-score.json"
& $PY -X utf8 -B -m pma_evidence_review.reviewer_r1_compare score --arm v4-reviewer-r1 --results "$OUT/candidate-real/results.json" --out "$OUT/candidate-score.json"
```

Before any future run, record the actual code SHA, model identifier and effective
sampling parameters without exposing the profile, credentials or endpoint. Compare
actual requests with exported requests. Report the 13 prior and nine new controls
separately; split the two deletion cases out. Distinguish three-state changes from
accept/reject changes, newly corrected errors from false rejections or admissions,
and engineering failures from semantic verdicts. Strong claims with genuinely
sufficient B must still pass. This development set is not a generalization test or
a claim about Task reward.
