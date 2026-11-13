# Chronological save audit — A/B, 45 successful writes

One row below is one successful `memory_add`, not one atomic fact. The complete proposed text, same-response public text, earlier public text **within that wake**, tool ID, success receipt and source path are in `PMA_SIX_FORECAST_AB_TEN_REAL_20261113.write_timeline.json`. These assessments use what was visible **at that wake**. Later observations are identified separately; they do not retroactively make an earlier assertion justified.

Public-process coding: **D** = a concrete supported finding and concrete tentative/untested possibility were distinguished before or with the write; **C** = a substantive future-use/source/confirmed explanation without that concrete contrast; **U** = insufficient substantive public explanation before the write. D does not mean the actual saved content respected the distinction. C is not automatically a mistake if no tentative candidate was visible. Empty public text says nothing about private reasoning. Counts: A **3 D / 7 C / 8 U** over 18 writes; B **5 D / 6 C / 16 U** over 27 writes; combined **8 / 13 / 24** over 45. These classes are exclusive. Content issues below can overlap across facts within one write; percentages must not be treated as fact-level error rates.

| ID | Task, arm, wake | Public process | Evidence-limited content observation |
|---:|---|:---:|---|
| 1 | KV A W1 | C | Saves original gRPC requirements, not implementation completion. |
| 2 | KV A W4 | D | Working `python -m grpc_tools.protoc` was observed, but file names were still phrased “should be” in the public explanation and were saved as generated fact. W5 later confirmed underscore names. |
| 3 | KV A W8 | D | Public text says the server was only “likely started”; the write records the startup command/implementation rather than claiming a verified running process. |
| 4 | KV B W1 | U | Saves original requirements plus predicted generated filenames with hyphens; W8 later documents that actual generated Python module names use underscores. |
| 5 | KV B W4 | U | Saves successful user-install/protoc observation and still says generated filenames “should have” appeared; not yet a file listing. |
| 6 | KV B W8 | U | Corrects actual underscore names; explicitly labels server-running status unclear after timeout and absent process/network utilities. |
| 7 | Reshard A W1 | U | Original constraints and intended generic use, without substantive pre-write public distinction. |
| 8 | Reshard A W4 | U | Inspection-derived 9,898-file sample and current manifest/split design; projections are not round-trip proof. |
| 9 | Reshard A W12 | C | Saves observed flat-sample round-trip and 330 shards; does not establish generic nested/large-file correctness. |
| 10 | Reshard A W16 | C | Saves observed 32 MB file split into 15/15/2 MB parts; not a complete merge/reconstruction proof. |
| 11 | Reshard B W1 | U | Original requirements and environment setup, no substantive pre-write explanation. |
| 12 | Reshard B W4 | C | Separates inspected sample characteristics from projected ~330 shards; records implementation details, not completed verification. |
| 13 | Reshard B W8 | C | Records a locally successful minimal `pyproject.toml`/`uv sync` adjustment. |
| 14 | Reshard B W12 | C | Records the flat-sample local compression/decompression and checksum evidence; larger/nested paths remained separate. |
| 15 | Reshard B W16 | D | Public and stored text separate the confirmed three-file nested test from large-file splitting still in progress. |
| 16 | RStan A W4 | C | R-source model, sampling and output requirements were read; not a claim that sampling succeeded. |
| 17 | RStan A W12 | U | Correctly observes 2,000-row vector outputs, but asserts the root cause is “saving all posterior samples.” Later shape debugging showed a wrong mean axis instead. The A-only confirmed rule did not prevent this premature cause claim. |
| 18 | RStan A W16 | U | Saves a diagnostic script and what it **will** reveal; it is a plan, not an established discovery. |
| 19 | RStan A W20 | U | Saves debug-print additions and possible causes still to distinguish; the contents remain explicitly prospective. |
| 20 | RStan A W24 | U | Saves locally observed `(3, 2000)` shapes, axis correction and four output line counts; whole-task “completed successfully” wording preceded native evaluation, which later passed 6/6. |
| 21 | RStan B W1 | U | Saves task requirements from the original description, no substantive pre-write explanation. |
| 22 | RStan B W4 | U | Saves the R-source model details after reading it; not proof that the Python conversion runs. |
| 23 | RStan B W8 | U | Saves observed installation/script creation and chosen arguments; not sampling completion. |
| 24 | RStan B W12 | U | Saves observed GCC installation and previous compiler error; “should now be able” remains a forecast. |
| 25 | RStan B W16 | U | Saves the observed rejected `seed` argument and correction to set seed in `stan.build`. |
| 26 | RStan B W20 | U | Saves wrong CSV line counts, but a “root cause identified” heading is too certain while the same note says array shape still needs inspection and speculates about a `(2000, 2000)` shape. |
| 27 | RStan B W20 | U | Records the code read and explicitly requests shape debugging; no false claim that the cause is settled. |
| 28 | RStan B W20 | U | Says some substeps completed but clearly keeps the two vector CSV outputs as an unresolved issue. |
| 29 | RStan B W20 | U | Saves a wrong-variable idea expressly as `HYPOTHESIS`/“most likely”; later shape evidence superseded it. |
| 30 | RStan B W24 | U | Saves directly observed `(3, 2000)` shapes and required axis=1 correction. |
| 31 | Eigen A W4 | C | Local baseline timings and correctness conditions; optimization had not yet been proven. |
| 32 | Eigen A W8 | C | Local Numba/power-iteration timing failures are retained with their tested scope. |
| 33 | Eigen A W12 | U | Local `eigvals`/SciPy timing comparison; not a universal speed guarantee. |
| 34 | Eigen A W16 | U | “SOLUTION FOUND” generalizes two local benchmark passes; native evaluation later passed 3/3, but that was not yet visible when saved. |
| 35 | Eigen B W1 | C | Original task constraints plus possible future approaches, not a finding that any approach works. |
| 36 | Eigen B W4 | D | Observed package installation is separated from the tentative `scipy.sparse.linalg.eigs` speed hypothesis. The stored note explicitly says “not yet confirmed.” |
| 37 | Eigen B W8 | C | Local sparse-method slowdown for 4–10 dimensions is observed; its own 2×2 result was slightly faster, so “8–10× slower” must stay scoped. |
| 38 | Eigen B W12 | D | Confirms a 2×2 correctness failure but labels the Rayleigh/normalization cause “likely”; W16 evidence revised that suspicion. |
| 39 | Eigen B W16 | D | Separates a successful single-matrix test from another failed matrix; stores possible causes as “likely,” not verified. |
| 40 | Eigen B W20 | U | One complex-pair failure is promoted to a blanket claim that power iteration cannot handle complex eigenvalues. The one case supports an algorithm/matrix failure, not that universal statement. |
| 41 | Eigen B W24 | U | Local 10×10 timing becomes “CONFIRMED SOLUTION” for 2–10 dimensions before the full evaluator; native evaluation later failed 1/3. |
| 42 | Eigen B W24 | D | Same wake's later write explicitly keeps the new implementation's full `eval.py` check as a next step, preserving that uncertainty. |
| 43 | HTML A W1 | C | Original requirements and future implementation considerations, not verified sanitizer behavior. |
| 44 | HTML A W4 | D | Public text distinguishes file creation/success echo from still-needed output verification; write nonetheless uses broad “implementation confirmed” wording. Native evaluation later failed 2/2. |
| 45 | HTML B W1 | C | Original constraints and a regex design note; no Task progress or successful sanitizer was yet observed. |

## Certainty and recall examples

- B Eigen W4's tentative sparse method and B Eigen W12/W16's likely causes retain uncertainty **in the bank**. B Eigen generated no reminder in this run, so their certainty at delivery is not tested. B W20/W24 nevertheless shows that allowing tentative notes does not stop later overconfident generalization.
- B RStan W20 stores several competing shape/variable hypotheses. The **actually delivered** reminder at Task attempt 21 still says the observations *suggest* alternatives and asks for shape inspection; it does not silently turn the hypothesis into a fact. At W24, direct shape output resolves the issue. This is a positive local example, not proof of general reliability.
- A RStan W12's premature cause claim was included in a delivered reminder at Task attempt 13. The Task later investigated fit shapes and corrected the axis; temporal succession does not prove the reminder caused that action. A's W16/W20 notes also preserve future diagnostic plans despite the “confirmed findings only” instruction.
- B KV W1's generated-file naming error was corrected in W8; both versions passed the native test. A's W4 also promoted an inferred filename to an observed result before the actual file listing. Later correctness cannot justify the earlier confidence level.

No atomic-fact error rate, model-internal reasoning claim or causal treatment effect is inferred from these rows. Task paths differ even within the same named task, and A always ran before B.
