# Per-wake evidence review

`W` is the manager's cycle step; W1 is before the first Task step. `R/A` are successful `memory_read`/`memory_add` calls in that wake. `C` means a context reminder was generated and verified delivered in a subsequent Task request; `N` means accepted no-intervention. Exact requests, public text, calls, receipts, bank revisions, and delivery links are in the ZIP's `memory_cycle.jsonl`, `memory_response.jsonl`, `memory_tool_results.jsonl`, `memory.json`, Task `research_events.jsonl`, and `wake_index.json`. This table summarizes rather than replacing the full visible record.

| Task | Wake | R/A | Decision | Visible finding / limitation |
|---|---:|---:|---|---|
| KV | 1 | 1/1 | N | Saved task/server requirements before action; not yet a confirmed execution result. |
| KV | 4 | 1/1 | N | Saved observed user-level package-install workaround. |
| KV | 8 | 0/1 | N | Saved generated Python filenames; **required read was omitted** this wake. |
| KV | 12 | 1/1 | C | Saved unavailable process/port CLI tools and recalled verification alternatives; subsequent Task made a test client and ran it at steps 13–14. Temporal adjacency alone does not establish reminder causation. |
| Reshard | 1 | 1/0 | N | Empty bank read; no new fact saved. |
| Reshard | 4 | 1/1 | N | Saved observed 9,898-file flat dataset and 30-items-per-directory issue. |
| Reshard | 8 | 2/1 | N | Saved script/metadata layout from current work. |
| Reshard | 12 | 1/1 | C | Saved observed root-level 330-shard bug and recalled the 30-item constraint; Task revised hierarchy at steps 13–16. |
| Reshard | 16 | 2/1 | N | Saved tested multi-level hierarchy and restoration result; no reminder. |
| Reshard | 20 | 1/1 | C | Saved cleanup bug/fix and recalled directory cleanup context; Task retested at steps 21–23. |
| Reshard | 24 | 3/1 | N | Saved Task's completion claim after its visible checks; native evaluation later passed. |
| RStan | 1 | 1/1 | N | Saved exact PyStan and output requirements; these are requirements, not completed facts. |
| RStan | 4 | 1/1 | N | Saved Stan-model/sampling details from inspected source. |
| RStan | 8 | 1/1 | C | Saved compiler issue and recalled build-tool need from visible failure. |
| RStan | 12 | 2/1 | C | **Prematurely stated Task complete** because CSV files existed; dimensions had not been verified. Task later found incorrect 2,000-row vector outputs. |
| RStan | 16 | 2/1 | C | Recalled dimension problem but saved/speculated an incorrect data/model-dimension explanation as root cause; later observations contradicted this. |
| RStan | 20 | 1/1 | C | Recognized D/P were correct and redirected toward sample extraction; Task later verified PyStan array axes and fixed mean calculation. |
| RStan | 24 | 1/1 | N | Saved verified `(parameter dimension, samples)` array orientation and corrected axis. |
| Eigen | 1 | 1/0 | N | Attempted unopened `$ACTION_CALL` once; tool boundary rejected it. Manager then returned to memory-only role. |
| Eigen | 4 | 2/1 | N | Saved constraints from the visible evaluation setup. |
| Eigen | 8 | 1/1 | N | Saved observed Python/binary-path discrepancy. |
| Eigen | 12 | 1/1 | N | Saved benchmark showing sparse `eigs` slower for most target sizes. |
| Eigen | 16 | 2/1 | N | Saved power-iteration implementation strategy while correctness remained under test; this is a plan/progress record, not confirmed success. |
| Eigen | 20 | 2/1 | C | Saved failed power-iteration correctness and recalled ruled-out approaches. |
| Eigen | 24 | 4/2 | C | Saved eigvals speed test and Numba limitation; reminder reflected current hybrid path, which later failed a performance check. |
| Eigen | 28 | 2/2 | N | Saved failed SVD result and next possibilities; later Task found a different solution. |
| Eigen | 32 | 2/1 | N | Saved visible `scipy.linalg.eig(check_finite=False)` result; native evaluation later passed. |
| HTML | 1 | 1/1 | N | Saved task requirements; no reminder. Task ended after step 2, so no later recall opportunity was observed; native evaluation failed 0/2. |

The `R/A` detail is navigable in the full logs. Some saved entries represent requirements, plans, or the Task's own intermediate claim despite the new “confirmed findings only” instruction; model compliance is not guaranteed by the prompt. The RStan W12/W16 sequence is a concrete counterexample to treating all stored text as confirmed. The archive supports the temporal order of reminder delivery and later Task actions, but not a counterfactual claim that a reminder caused success. The previous five-task archive used a different four-variable combination, so the score change is descriptive only.
