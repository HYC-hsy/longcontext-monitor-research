# v4 split review: offline implementation handoff

Baseline: `3f607a37335433126bf8cfbf40613c169902bfb0`.
Opt-in strategy: `claim-split-same-evidence-v4`, with `gate-only` or
`gate-one-repair`; unspecified strategy and v3 retain their old behavior.
This delivery has **zero real model, Task and native-evaluator calls**.

## Mechanism and limits

- The splitter is sent A and target context only; frozen B stays host-side until
  the one batch review. The batch compares all ordered claims and the entire A
  against the same B. All claims **and** overall must be supported for publication.
- Generic examples preserve requirements, conditionality, chronology, causality
  and part/all scope. They are separate from the development test cases.
- For v4, only existing `gap` deletion is eligible. The unchanged `memory_delete`
  tool gains `reason` and `evidence` parameters *in this mode only*. The old gap
  body and active revision are target context, not evidence. Literal candidates
  from the current visible catalog are validated before model review. The draft
  deletes that exact version only after support and publication checks; rejected,
  stale, malformed or unbound cases keep the gap. Other memory deletion is still
  deferred. The host receipt records the outcome and is not external evidence.
- A replacement after one author repair is wholly re-prepared, re-split and
  re-reviewed. The original operation/target is fixed. No third version passes.
- `exact_multiple` locations remain alternatives for one quote. No retrieval,
  fuzzy upgrade, evidence-ID generation, source-coordinate output, new role or
  semantic hard-coded gate is introduced. Structural tests do not establish that
  a real model preserves every important relation or reaches correct verdicts.
- The offline small A/B has 13 development cases: four pinned eligible items
  from the frozen 29, two published historical trace fixtures, and seven manually
  derived controls. The two deletion controls are v4-only: v3 records N/A, not
  a semantic error. `SMALL_SAMPLES.json` labels/reasons are evaluation-only and
  never enter either model prompt. Manual cases are not historical episodes.

## Focused checks already executed

With the existing Python and pinned PMA/vendor Harbor on `PYTHONPATH`, focused
unit tests cover split payload, frozen B, cardinality, partial rejection,
publication, one repair, gap delete refusal/success, stale target, and v3
isolation. The archived stdout/stderr and actual counts are in the diagnostic ZIP.
The offline plan export loads the externally pinned manifest
`dcadeb1fabe2c2518307e8763ea5f6118688027394e514b575ce07d4fe482928`.
Both plans contain 13 equal material hashes; v3 has two deletion N/A entries.

## Next step: real small-sample A/B, **not executed in this delivery**

From the fixed v4 checkout root, use the already authorized local Python and
existing PMA profile. Replace the two placeholders with actual absolute paths;
each output path must not exist. The two exports are offline and may be compared
before any model request. Only a later explicit authorization permits run-profile.

```powershell
$Py = '<existing-python-3.12+-absolute-path>'
$Data = (Resolve-Path 'pma_evidence_review/benchmark/candidate_data').Path
$Profile = '<existing-private-profile-absolute-path>'
$Repo = (Get-Location).Path
$Out = '<new-private-output-parent>'
& $Py -X utf8 -B -m pma_evidence_review.split_v4_compare export --dataset $Data --strategy claim-split-same-evidence-v3 --out "$Out/v3-plan.json"
& $Py -X utf8 -B -m pma_evidence_review.split_v4_compare export --dataset $Data --strategy claim-split-same-evidence-v4 --out "$Out/v4-plan.json"
# Following real calls require a separate future authorization; do not run as part of this handoff.
& $Py -X utf8 -B -m pma_evidence_review.split_v4_compare run-profile --dataset $Data --strategy claim-split-same-evidence-v3 --repo $Repo --profile $Profile --profile-key claude_monitor_opus48 --out "$Out/v3-real" --execute-authorized-real-model
& $Py -X utf8 -B -m pma_evidence_review.split_v4_compare run-profile --dataset $Data --strategy claim-split-same-evidence-v4 --repo $Repo --profile $Profile --profile-key claude_monitor_opus48 --out "$Out/v4-real" --execute-authorized-real-model
& $Py -X utf8 -B -m pma_evidence_review.split_v4_compare score --dataset $Data --strategy claim-split-same-evidence-v3 --results "$Out/v3-real/results.json" --out "$Out/v3-score.json"
& $Py -X utf8 -B -m pma_evidence_review.split_v4_compare score --dataset $Data --strategy claim-split-same-evidence-v4 --results "$Out/v4-real/results.json" --out "$Out/v4-score.json"
```

Run v3 then v4 using the same profile/model/parameters. Stop on engineering
failure; do not silently retry, relabel, or add evidence. Compare historical
versus derived separately; do not claim generalization from this development set.
