# GAP audit and phase-2 input cleanup: candidate delivery

Base: `e80648be9f40a44fd4045d75b2ad18b286208fdf`.
Scope: one authorized engineering stage with three small implementation steps.
No real model, Task, native evaluation or old-control run was executed.

## Changes

1. Reuse the existing whole-operation/subclaim gate. Host action/category selects
   a short GAP-specific audit instruction. Saving an unresolved issue does not
   require task completion; deletion needs a reason for retiring that issue, not
   merely evidence repeating it. Repair review receives the frozen initial
   action/content as interpretation context, never evidence. Narrowing, correction
   and withdrawal remain possible; changing the issue to win approval is not.
   This is a prompt-level semantic constraint, not a deterministic guarantee.
2. `operation-audit-three-column-v2` requires every O/C row to be
   `[label, verdict, brief_reason]`. All reasons are nonempty, including supported
   rows; an evidence suggestion belongs in the same reason, not another column.
   Old two-column output is not retroactively accepted. Raw responses and explicit
   protocol identity remain in diagnostics. The splitter sees semantic action,
   content and existing GAP, not bookkeeping IDs/hashes; host identity is retained.
   Unknown business fields fail explicitly instead of being silently discarded.
3. P2 receives one concentrated selectable catalogue, current internal status,
   and the same recent visible steps. Only a recognized framework-owned
   observation/content wrapper is projected; commands, public responses and
   complete tool results remain unchanged. Latest available earlier_context and
   key_info are retained once. Unknown/ambiguous wrappers stay literal. Short
   binding qualifications remain; repeated binding excerpts do not. P1 evidence
   construction, the tag selection protocol and revision/delivery checks are unchanged.

No new judge, model call, retrieval system, dependency graph, memory category,
state summarizer or SQLite-specific decision rule was added. The once-only repair
budget is unchanged. Historical results and archives are not modified.

## Evidence and limits

- `combined-checks.log`: 61 combined offline checks passed after integration,
  including full episode/dispatcher persistence, fault paths, protocol parsing,
  repair-origin wiring, P2 preservation and isolated GA-client imports.
- Optional imports used explicit doubles for regex, shortuuid and Harbor in this
  environment. The production Python environment must rerun in strict mode;
  scripted LLM clients remain mandatory. This is not a production dependency pass.
- One existing frozen-dataset comparison-plan test remains excluded by the
  inherited runner because its dataset is outside this scoped checkout. No model
  baseline was rerun. Fake verdicts test contracts, not semantic correctness.
- `DEVELOPMENT_CASES.md` freezes eight cross-domain development cases (one has
  three deletion variants). Reference judgments are separate from input blocks,
  are not held-out evidence, and must not enter model requests.
- `../selection_input_cleanup/replay_results.json`: all 18 saved public P2 inputs
  were replayed without inference. Total prompt characters: 522,809 -> 325,670;
  original peak: 51,363 -> 32,960. Exact commands/public responses/tool_results are
  equality checked. Counts are characters, not tokens or billed savings. Saved
  input lacks some accepted-event metadata retained by the live path, so lengths
  are replay measurements, not predictions of live bytes. See that README.
  Published preservation tests use newly written synthetic trajectories; the real
  archived trajectory fixture is not included in this delivery. The replay tool
  accepts a user-supplied local source and emits only hashes/counts, not raw fixtures.
- Historical semantic errors motivate this candidate but are not proof the new
  prompt fixes them. Model quality, reminder benefit and Task gains remain untested.
- This stage does not repair the external experiment-specific preflight/exporter
  or certify Windows ACL checks. Do not infer those old gates are closed.

## Developer acceptance

Use the exact final commit from the delivery message, in an independent checkout.
From its repository root, with the existing pinned production Python environment:

```powershell
$env:PMA_TEST_STRICT_IMPORTS='1'
python -m pma_evidence_review.gap_io_cleanup_delivery.run_offline_checks
```

Missing imports are a blocker, not permission to disable strict mode. Keep the
LLM fake and preserve test stdout/stderr. Confirm all new host modules are present
in the launcher's staged source/fingerprint set; do not add host packages to the
minimal GA client import path. Recheck actual protocol/request identity and full
event/JSON persistence before requesting a new real run.

Report acceptance first. A real reviewer trial or Task needs separate user
authorization; never rerun the old group automatically on the same dataset.
Only publish explicitly selected visible diagnostics, not private failure logs
or hidden request-history blocks. This delivery includes no such hidden content.
