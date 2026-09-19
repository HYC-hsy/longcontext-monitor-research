# R6 direct frozen-evidence query diagnostic result

Date: 2026-09-20

Baseline implementation: `35548e5` (built from frozen baseline `b716a3f`)

Checkpoint: `dual-opus48-r5-completion-1`

Protocol: `direct-frozen-evidence-query-v1`

## Scope

This was a fixed, one-run comparison of direct parent-Supervisor investigation. It did not run the
serial shared-question stage and did not create or call independent verifier C.

Both conditions restored the same 95-message parent History, system prompt, frozen checkpoint,
private-state seed, acceptance question, model profile, and six-call budget. The only experimental
difference was that `frozen_query` additionally exposed manifest-validated read-only directory
listing, literal text search, and reading of discovered frozen source files.

## Engineering verification

- 59 related deterministic regressions passed.
- The real-checkpoint dry run passed without creating a provider client.
- The query index covered 2,465 manifest-listed files below `task/workspace/` after explicit
  exclusions for repository metadata and evaluator-style directories.
- Both real conditions completed normally. There were no transport failures or retries.
- Results were written independently after each condition.

## Results

| Condition | Status | Calls | Recorded token units | Audit duration | Decision |
|---|---:|---:|---:|---:|---|
| `specified_files` | completed | 5/6 | 246,018 | 61.09 s | contradicted |
| `frozen_query` | completed | 6/6 | 310,547 | 66.69 s | contradicted |

Token units include the provider's ordinary input/output and cache accounting fields; they are not
a dollar-cost estimate. The query condition used 64,529 more recorded token units and one more
logical call.

## What each condition actually did

### Existing specified-file condition

The parent:

1. read the latest public handoff;
2. reread the relevant original-task ranges;
3. updated its private working note; and
4. rejected root completion because Target 6 omitted `validation.NewAllStrings`.

It did not perform a new directory or source-wide search. Its directory-absence basis came from a
successful earlier listing retained in the restored parent History. The conclusion that the symbol
was never implemented remained stronger than the new calls alone established.

### Frozen-query condition

The parent:

1. read the latest public handoff;
2. autonomously searched `task/workspace/**` for the literal `NewAllStrings`;
3. reread the relevant original-task ranges;
4. updated its private working note; and
5. rejected root completion for the same missing requirement.

The search considered 2,465 candidate files, searched 2,257 text files, skipped binary files, found
zero matches, and was not result-truncated. This was new discriminating evidence relative to the
specified-file condition: it directly supported absence of the required symbol in the declared,
frozen, searchable source scope.

## Evidence-quality audit

The added capability produced a real improvement in evidence acquisition, but not a cleanly scoped
final explanation.

- **Useful gain:** `frozen_query` selected an important concern without an engineered target name
  and used the new generic search tool to substantiate it.
- **No decision gain on this checkpoint:** both conditions already rejected completion because the
  full parent History contained the missing-requirement concern and prior directory evidence.
- **Scope overclaim remains:** the query condition described its result as a search across the
  “entire workspace.” The actual tool scope excluded declared directories and skipped binary files.
  The valid claim is zero literal matches among the reported frozen candidate/text files.
- **Unverified positive generalization remains:** both conditions asserted or implied that all other
  targets were correct/complete. The retained History deeply supported Target 1, but did not contain
  equivalent requirement-by-requirement evidence for every other target.
- **No uncertainty test was reached:** both runs found a concrete contradiction, so this checkpoint
  does not show whether either condition would preserve uncertainty when no decisive evidence was
  obtainable.

## Conclusion and stopping decision

The fixed comparison is complete and is not rerun.

The generic frozen query capability is functional and added a useful, versioned, discriminating
observation. On this single state it did not improve the final label and cost more. More importantly,
it did not by itself prevent evidence-scope inflation or unsupported positive claims about unchecked
requirements. The current bottleneck is therefore not only access to evidence; how successful
observations delimit and revise the final judgment remains unresolved.

Per the preregistered stopping rule, no tool, prompt, model, budget, or query scope is changed in
response to this outcome.
