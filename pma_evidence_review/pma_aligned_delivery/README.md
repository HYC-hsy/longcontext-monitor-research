# PMA-aligned P1/P2 combined candidate

Baseline: `d28d0ed75741f3a627721766a29745ab3ae2da9d`, including its worker
PYTHONPATH fix. Use the final fixed SHA supplied with this delivery. The old
`59fc8830e16bb64e6d0b4ea4244931c958f30754` P2-only draft remains historical;
it is not this combined candidate. No default branch was merged or force-pushed.

## Pinned original and deliberate adaptations

The original is the with_strategy prompt pair in
[yifannnwu/proactive-memory-agent@89e5c0d6](https://github.com/yifannnwu/proactive-memory-agent/blob/89e5c0d6aadfe531a1aee42fd290d48be89973dd/src/memory_agent/memory/memory_agent.py),
Apache-2.0. GitHub readback and the local unmodified vendor have identical Git
blob `216cedf07837677c198cf9b7bafdea04858e6435`; file SHA-256 is
`e00d412034b8cfebb6b8121477453d2815e26ce2d78344c9f7991a37048e0b35`.
The original P1 is 1382 characters / 203 whitespace words; original P2 is
2114 / 340. The 3462-character synthesis prompt includes our GAP/ATTENTION
extension and is not the PMA original.

| Original capability | Actual d28 | Combined candidate / reason |
|---|---|---|
| P1 manager role, facts/experience/status, four initial and four later save angles | Retained, with GAP and source-binding adaptations | Retained, including environment findings, failures, approach changes and scores. No tool/category/parameter change. |
| P1 failure reasons, lean deletion, incidental terminal output | Intentionally qualified to grounded causes, same-ID revisions and useful observations | Preserve these adaptations; do not mechanically restore unsupported causes or discard useful tool results. |
| P1 maintenance / experience / GAP rules | Overlap; repeated observations could become extra attempts, an immediate blocker could replace the original gap, experience could grow into a task diary | Consolidate existing duties. Distinct actions determine attempts; pending results stay unknown. Preserve unmet original conditions and useful experience; unchanged entries need no rewrite. |
| P1 host/binding guidance | Long assembled additions | Direct approved full system, with a shorter existing update contract; no old blocks are appended. |
| P2 Selective Attention, three PROCESS steps, four intervention and four silence criteria, strong-agent reminder role | Thin 834-character tag system omitted much of the concrete guidance | Restore the original skeleton and useful sentences through explicit replacements. Keep calibrated default silence and the strong-agent help-not-control role. |
| P2 free synthesis and connecting dots beyond verbatim memory | Incompatible with the requested original-text delivery | Replace generation with existing TASK/M alias selection. Relationships may guide the choice; output cannot invent advice. This is an intentional replacement, not verbatim reproduction. |
| P2 recent content automatically means silence | Conflicts with correcting misapplication of recent information | Silence when visible information is applied appropriately; recent misuse can still warrant a reminder. This is the second deliberate replacement. |
| P2 bank confidence / task completion | Stored summaries may be wrong or overbroad | Source matching is not truth. Exclude visible conflicts or superseded content without demanding recent reproof of older useful information. Scope, plans and justified retries are local adaptations, not claimed original rules. |

## Scope and actual system identity

Only two production files change: maintenance_no_review_agent.py (the no-review
P1 full system and two existing tool descriptions) and tag_selection_contract.py
(shared P2 SELECTION_SYSTEM only). P1 parameters/tool set are compared with d28;
input, store, strategies, parser/fences, revision and delivery checks, routes,
model parameters, launcher and source inventories are unchanged. No runtime file,
model call, review chain, GAP hierarchy or new output field is introduced.

The new P1 affects MaintenanceNoReviewAgent only; old gated P1 still uses the
unchanged latest builder. Shared P2 affects both MaintenanceNoReviewAgent and
gated-v4 VerbatimSelectionCitationGateAgent through the existing mixin. This is
not exclusive to the no-review class. Historical fixed SHAs remain available.
The next real run explicitly uses the no-review configuration.

SYSTEMS.json contains the complete P1/P2 system texts actually received by a
scripted client through the real factory/mixin, not just constant measurements:

| System | d28 chars / words | Candidate chars / words | Candidate SHA-256 |
|---|---:|---:|---|
| P1 | 5612 / 814 | 4387 / 645 | `5ad9ae10f9bdd3573a58c10edc68de153ab5d062562f28e6f79a0862bf987b8e` |
| P2 | 834 / 122 | 2847 / 449 | `f8ab207073db662a3af7e712584fdf2bb0433b1c4d42ba9a9e4dae872269d522` |

P1 is about 22% shorter. P2 grows to restore judgment criteria; combined system
characters rise from 6446 to 7234. Character/word counts are not model token or
cost measurements, and neither shorter text nor engineering success proves
semantic benefit. This is one combined candidate; its later outcome cannot be
separately attributed to P1, P2 or the earlier removal of review.

## Offline engineering acceptance

Fresh combined directed suite: **39/39 pass**. Full strict regression: **454 run,
453 pass, one retained baseline fixture error, zero assertion failures/skips**.
PMA runs 438 with one error; pinned native Harbor import/bootstrap tests pass
16/16 in a separate process. All 65 directly related existing gate, repair,
runtime-boundary and selection checks pass. Dependency substitutes are empty.
The old U/A preflight fixture expects an early ValueError; it proceeds to output
handling (fresh output can reach a missing official_source_git; an earlier
fixture's unused directory now causes FileExistsError). That test/runtime is
unchanged, and the full result remains nonzero.

Real factory/client checks pin both approved full systems, upstream save angles,
the unchanged tool parameter structure, silence/original-text delivery, pending
revision invalidation and actual committed launch-source identity. Existing
PMAEpisode/dispatcher/worker/persistence and protocol negatives run too. Initial
precommit identity rejections and final results are separated in TEST_RESULTS.json.
No old P2-only result is reused as a combined-candidate result.

```bash
python -B pma_evidence_review/tools/run_p2_selection_checks.py --report /new/local/combined-checks.json
```

The helper name is retained; its eight suites cover both P1 and P2. It uses the
existing guarded runner, strict actual imports and local LiteLLM cost map. Full
command, counts, inventories, dependency versions and local raw-report hashes are
in TEST_RESULTS.json. Raw private logs are not uploaded.

EVIDENCE_AND_CASES.md records multiple prior visible-run audits and synthetic human
boundary cases. Those expectations are development references, not model-scored
passes. No real LLM, Task, episode, live launcher/Docker or native task evaluation
was run. MANIFEST.json binds all changed deliverables, 70 runtime sources, the
71-file launcher startup identity path and pinned vendor files. HANDOFF.md gives
one new-candidate SQLite run, using newly prepared final-source identity.
