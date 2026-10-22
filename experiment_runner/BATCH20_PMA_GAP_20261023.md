# PMA-gap 20-task diagnostic selection (2026-10-23)

This is a frozen, pre-outcome task selection, not a result or an effect claim.
The source is the pinned task pool at `2fd12b88aafdd04a52c298e3940bcb189f9766d6`.
The existing catalog accepted 88 task IDs. The extra directory
`install-windows-3.11` is not a valid catalog task and was not in the pool.
Public resource requirements disclosed no task requiring a GPU or more than
8192 MB of memory; this 16.7 GB Linux/amd64 Docker host has no additional
known machine-compatibility exclusion. Selection did not use past rewards.

From the sorted 88 IDs, `random.Random(20261023).sample(ids, 20)` produced
the following distinct IDs. The listed order is the serial execution order;
each occurrence is 1, and failures are not replaced by another task.

1. git-leak-recovery
2. git-multibranch
3. feal-linear-cryptanalysis
4. query-optimize
5. mcmc-sampling-stan
6. fix-ocaml-gc
7. rstan-to-pystan
8. merge-diff-arc-agi-task
9. break-filter-js-from-html
10. nginx-request-logging
11. circuit-fibsqrt
12. multi-source-data-merger
13. filter-js-from-html
14. largest-eigenval
15. make-mips-interpreter
16. kv-store-grpc
17. sanitize-git-repo
18. build-pov-ray
19. reshard-c4-data
20. db-wal-recovery

Method: `pma-gap` / B / `pma_gap_memory_v0`, unchanged two-stage method.
Agent time and Task turns: uncapped diagnostic. Verifier timeout: official
per-task setting. Evaluation preparation: `download_retry_v1`, at most three
download attempts including the first; no persistent evaluation cache.
Batch policy: serial, `on_slot_failure=continue` only after isolated finality,
evidence preservation, and cleanup. Identity, authorization, or uncertain
survival stops the batch. This is not a same-time-limit benchmark score.

The local private configuration contains machine and profile paths; it is not
committed. Fixed entry: `python -m experiment_runner plan`, `prepare`, `run`
with the same configuration and a new output directory. Real Task/model and
native evaluation outcomes will be recorded separately after execution.
