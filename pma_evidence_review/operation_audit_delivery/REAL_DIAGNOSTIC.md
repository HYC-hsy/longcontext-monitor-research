# Operation-audit candidate: first three real reviewer-only calls

Execution code: `a0f35e1ab4586472ebc0768b87e3cc228f36aa14` (parent `48babf4302563bbe6e8f0d47e8c617d041a392b1`). Prototype materials were read and manifest-checked at `c08e84eda44a731fc4568533ac313dfa643cace6`.

The frozen cases are in `frozen_replay_cases.json`, with the historical submitted-evidence material in `historical_path_material.json`. The first is a historical delete request; the other two are explicitly artificial development controls using exactly the same submitted evidence. References were frozen before model calls and were not included in model requests. The reviewer-only replay called the production batch-review stage directly. It made three client calls, with no splitter calls, Task, evaluator, memory commit, or old-review rerun.

## Observed decisions

| Case | Frozen reference | Model overall | Final | Review of evidence and reason |
| --- | --- | --- | --- | --- |
| Historical PATH gap deletion | insufficient | insufficient | insufficient | All four subclaims were marked supported, but the complete deletion was rejected: the script-local PATH export does not establish that the old PATH gap can be retired. This is the intended complete-operation check. The reason's word “persistently” may be stronger than the old gap's literal wording; a fresh independent consumer was one possible suggested check, not a unique required test. |
| Current-shell observation | supported | supported | supported | The reviewer joined the submitted command excerpt with the event-23 stdout and recognized only the shown script's successful lookup and version line. It did not claim cross-session success. |
| Observed result plus future verification plan | supported | insufficient | insufficient | The plan subclaim was supported without requiring completed verification. The observation subclaim was rejected despite the same event-23 command and stdout supporting the narrower current-script observation in the prior case. The model reason said it could not associate them and requested a further command/output pair. This is an apparent false rejection or at minimum unstable evidential linkage, not a parser failure. |

All three responses had `engineering_status=ok`; the first and third raw responses used one permitted outer JSON fence. `model_verdict` is the raw overall judgment after parsing; final verdict additionally applies the existing all-subclaims-and-overall acceptance rule. In these three cases they agree. No result was selected or repeated. The source evidence is limited to the submitted quotes and their host-projected source roles/event order, not a reconstructed full task history.

## Engineering scope and limitations

Prototype tests: 15/15. Affected production tests: 17/17. These are engineering checks, not a model-effect guarantee. The prior production v4 already had an overall judgment and conjunction rule; this candidate changes the reviewer workflow, model-visible projection, and gap feedback. The splitter prompt hash remained `b57be62604b515cd1659a989acc228740d47dd6f53dab1fd458e3349fce7602b`; the gate, once-only repair budget, citation admission, Phase2 and model parameters were not changed.

The public ZIP contains the three complete model-visible requests, visible raw responses, parse/result records, safe run identity and original test output. It excludes the private profile, endpoint, API key, private client directory, hidden reasoning and hidden tests. The model's suggested evidence is control feedback only; it was not submitted as new evidence or entered into memory. Three development cases cannot establish general reliability or Task benefit; no SQLite Task was launched.
