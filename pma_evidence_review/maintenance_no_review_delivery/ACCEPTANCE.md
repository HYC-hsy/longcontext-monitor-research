# Offline acceptance

Verdict: the new candidate's engineering checks pass; the broad suite is **not
fully green** due to one reproduced baseline test defect. No semantic effectiveness
or reward claim is made. The initial wiring was uploaded in `ec40304b80a9843c53a79ba28b2543295d8014ee`.
The final source additionally consolidates inherited GAP guidance and adds two
synthetic contract tests. Exact final bytes are listed in SOURCE_SHA256.json.

- Candidate suite: **13 run, 13 pass, 0 errors/failures/skips**, strict imports.
- Broad runner: **448 run, 447 pass, 1 error, 0 failures/skips**. PMA: 432 run,
  431 pass; pinned native Harbor import/bootstrap suite: 16/16 pass.
- No dependency doubles. CPython 3.12.13, real regex 2026.9.29 and rpds-py
  2026.9.1; full installed package versions and test inventories are in the
  sanitized TEST_RESULTS.json. The existing PMA runner's typing.TypedDict
  compatibility patch remains; native Harbor runs in a separate process at
  `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`, without vendor fallback.
- `git diff --check` passes. Git autocrlf is false only in the isolated repository.
  Baseline and vendor files were not rewritten. No other worktree was touched.
- All model completions were scripted. Socket guards are active. The final
  dedicated suite explicitly uses the local LiteLLM cost map. An earlier direct
  invocation omitted that environment setting and attempted a failed metadata
  DNS lookup; it sent no model request. Raw diagnostic logs stay local.

## What the tests establish

The broader result includes all 65 directly related existing checks, all passing:
LiveGate 29, repair JSON/fence 7, runtime boundary 9, selection context 6,
selection deployment 2, tag integration 6 and verbatim integration 6. The 13 new
candidate checks are also all successful in this final full run; they do not
substitute for those old regressions.

The actual factory returns MaintenanceNoReviewAgent over LatestEvidenceGapMemory,
with no CitationGateMemoryAgent in its MRO or review transport. Each cycle uses
maintenance and selection only. Missing/non-exact citations commit legal writes;
invalid targets/content and an actually corrupted source snapshot are rejected.
Update/delete independence, manifests, source history and round-trip bank loading
are tested. Status, GAP and experience content reaches selection.

The real PMAEpisode, EventDispatcher and worker fake path cover no intervention,
valid original-text delivery, stage transport failure, worker readiness policy,
full nested JSON logs and final memory artifacts. Original task bytes, TASK/Mn
aliases, committed revision pinning and pending-delivery revocation are exercised.
The new selector is the same moved implementation used by the old gated class.

Actual plan/manifest preparation uses synthetic asset/image boundaries and real
committed-source hashing. Policy omission/mixing rejection, source collection,
changed/missing manifest entries, changed/missing source bytes and no-gate source
verification are checked. Frontend-to-worker policy forwarding is covered; it
does not silently fall back to the old free-synthesis agent. Old gate regressions
continue to run. No runtime call to fixture-only require_bound_gap_memory was added.

Prompt assertions inspect the assembled system plus real tool descriptions.
The actual assembled P1 systems measure 6088 characters / 885 whitespace words
for old latest, 6752 / 981 for old v4 gate, and **5612 / 814** for this candidate.
An intermediate version was 7496 characters and was consolidated before final
acceptance. The inherited long GAP block was replaced by a shorter integrated
block retaining initialization, concrete test-quality checks and gap lifecycle;
matching prompt/length assertions prevent reintroducing the overlap. Counts are
not model tokens and do not establish semantic improvement.
Cross-domain scripted analytics/service/workbook examples verify the interface
and scope-preserving text delivery contract, not a model's summarization ability.

## Existing failure retained and disclosed

`test_gate_policy_preflight.GatePolicyPreflightTests.test_a_keeps_no_policy_and_rejects_gap_policy_override`
expects an early `ValueError` when a minimal U/A fixture supplies runtime_policy={};
the baseline single_run.prepare instead proceeds to output/profile handling.
An isolated reproduction executes the exact e52908b baseline function with a fresh
temporary output root and gets `AttributeError` for absent official_source_git.
The broad suite also leaves `unused/plan.json`, so subsequent attempts can instead
get FileExistsError there. This is not a no-review-policy failure. The test and U/A
runtime behavior are left unchanged; the acceptance result remains nonzero.

A separate stale v4 fake response was reproduced as failing on the baseline
selector, then corrected from the old object schema to the current three-column
batch-response array. Its assertions and production reviewer were not weakened.

## Limits and reproduction

From a clean checkout and prepared dependencies, run the existing strict runner:

```bash
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tests/run_gate_regressions.py --native-harbor-source-root /path/to/pinned-native-harbor --report-dir /new/local/report
```

For the 13 candidate tests, use the same runner's real dependency setup and network
guard while selecting the three test_maintenance_*.py suites (the file list and
inventory SHA are in TEST_RESULTS.json). Do not run an arbitrary broad pytest
collection: it includes research launchers outside this acceptance scope.

Implementation was split into reviewable steps: selector reuse/prompt contract
(533 code/test added+deleted lines), host policy/identity wiring (under 250), full
integration/frontend tests (213), two final contract tests (under 60), and prompt consolidation with its assertion (36). Each
step is below the repository's 600-line limit; documents and generated hash tables
are reported separately. Local step snapshots and raw reports were not uploaded.

The candidate can directly publish wrong claims or retire a useful gap because
semantic veto is intentionally disabled. Source matching still does not prove
truth. The combined prompt+no-review candidate does not isolate causal effects.
Real SQLite outcome, reminder benefit, costs and generalization remain untested.
