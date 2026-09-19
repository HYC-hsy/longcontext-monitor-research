# Recovery-scope state source audit

Date: 2026-09-20

Sources: the original dual-Opus root checkpoint, its exact 95-message parent History, and the two
R6 branch-private `working.md` files. No model calls were made.

| Judgment | Source | What it actually supports | Persisted for later use? |
|---|---|---|---|
| The required path `data/validation/all.go` was absent | A successful `ls -la /app/data/validation/` observation already present in restored parent History messages 93--94 | Absence of that prescribed path at the captured checkpoint and observation time | Yes, in parent History; R6 also copied the conclusion into both branch notes |
| `NewAllStrings` had zero matches in the declared frozen source search | R6 `frozen_query` literal search over 2,465 candidates / 2,257 text files, with evaluator-style prefixes excluded and binary files skipped | No literal match in the reported manifest-validated text scope; not unrestricted whole-machine or hidden-material absence | Yes, but only in the R6 `frozen_query` branch note; not in the original checkpoint note |
| Target 1 repairs were complete | Task-Agent repair events plus the Supervisor's subsequent reads of the repaired files in restored History | The specific Target 1 corrections that were inspected; not all seven targets | Yes, in parent History; the original note still retains the older issue description rather than a clean final state |
| Targets 2--7 / all remaining requirements were complete | Mostly Task-Agent progress/completion statements, build and partial-test reports, plus implementation summary; the Supervisor independently inspected only selected parts | Claimed progress and limited observations, not requirement-by-requirement support for every target | The broad “all other targets appear complete” statement was **not** in the original checkpoint note. R6 newly wrote it into both branch-private notes and repeated it in final explanations |
| The implementation summary omitted `NewAllStrings` | Successful R6 read of the summary | Omission from the task-side summary only; not by itself source-code absence | Present in R6 History/results, not the original checkpoint private note |

Research-side inspection after the run is kept separate. It confirms that the captured source had
no prescribed file and no literal symbol, but those findings are not retroactively inserted into
what the parent Supervisor knew before R6.

## Consequence for the recovery diagnostic

The derived state must retain the original parent History and original checkpoint note. The local
repair is supplied as a later, explicitly research-constructed update. R6's optimistic branch notes
are audit evidence, not the seed state for the new conditions; otherwise the experiment would mix
the effect of the repair with state written by the previous diagnostic.
