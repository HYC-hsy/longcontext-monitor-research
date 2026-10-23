# PMA-gap 20-task diagnostic: full visible audit projection

Executed source commit: `a3c56129589a6e72062a9c4186cd44912e5e9746`.
Method: `pma-gap` / B / `pma_gap_memory_v0`, original two stages only.
The pinned task pool is `2fd12b88aafdd04a52c298e3940bcb189f9766d6`;
the pre-outcome selection and exact order are in
`experiment_runner/BATCH20_PMA_GAP_20261023.md` in the repository.
Both public model identities were `claude-opus-4-8` (Task and PMA). This is an
uncapped-Agent-time diagnostic, **not** the original Agent-time protocol.
Each task kept its official verifier time. `download_retry_v1` was selected
with at most three download attempts including the first; no persistent
evaluation bundle was selected. Existing model-provider retry settings were
not changed.

The batch attempted all 20 distinct slots, one episode per slot. Fifteen
native evaluations produced reports: nine reward 1.0 and six reward 0.0.
Five evaluations failed during `apt_update` dependency preparation (exit 100),
before the test entry: reward **unavailable**, not zero. These five were
isolated and cleaned before the serial controller continued. The original
APT output body was not retained, only its SHA-256 and exit status, so the
precise reason for exit 100 cannot honestly be classified as transient or
permanent from this archive. No task or evaluation was automatically retried.

| # | Task | Run ID | Reward | Test entry |
|---:|---|---|---:|---:|
| 1 | git-leak-recovery | pma-cb0b575d800d4fee | 1.0 | 1 |
| 2 | git-multibranch | pma-2326225f84424007 | 1.0 | 1 |
| 3 | feal-linear-cryptanalysis | pma-8c4abb17d76348fc | 1.0 | 1 |
| 4 | query-optimize | pma-0e550e2780074721 | 0.0 | 1 |
| 5 | mcmc-sampling-stan | pma-d74aea1ebca5445c | 1.0 | 1 |
| 6 | fix-ocaml-gc | pma-95d98de7ae9342d6 | 1.0 | 1 |
| 7 | rstan-to-pystan | pma-99dc9b266c4b4c25 | 0.0 | 1 |
| 8 | merge-diff-arc-agi-task | pma-0acafe2bf79b4f33 | 0.0 | 1 |
| 9 | break-filter-js-from-html | pma-1c9d4f1020cf433f | 0.0 | 1 |
| 10 | nginx-request-logging | pma-f89740d1580e4b3c | 1.0 | 1 |
| 11 | circuit-fibsqrt | pma-dec896031a6048a6 | unavailable | 0 |
| 12 | multi-source-data-merger | pma-5b04cf41bce94266 | 1.0 | 1 |
| 13 | filter-js-from-html | pma-bf6695cc54774795 | 0.0 | 1 |
| 14 | largest-eigenval | pma-f9a29cf55df945a4 | 1.0 | 1 |
| 15 | make-mips-interpreter | pma-c18bf64a6c774e51 | unavailable | 0 |
| 16 | kv-store-grpc | pma-2885bf27cbb44364 | 1.0 | 1 |
| 17 | sanitize-git-repo | pma-0c3e7fd09f3e4db7 | unavailable | 0 |
| 18 | build-pov-ray | pma-4fa96ed378164716 | unavailable | 0 |
| 19 | reshard-c4-data | pma-0f5b80fc63aa410e | 0.0 | 1 |
| 20 | db-wal-recovery | pma-6e4e420a95fe42b0 | unavailable | 0 |

The directory for each slot contains *all recorded rows* of the Task-visible
event stream, both PMA-stage requests, recorded visible responses, memory
transport, gap cycles, accepted events, and final memory/trajectory. They are
losslessly gzip-compressed **after** field/value redaction, not replaced by a
developer narrative. `INDEX.json` maps every source file and line SHA-256 to
each public member and line; the private originals remain local. A gzip file
can be read with `gzip -dc <file>.gz`. `BATCH_RESULTS.json` gives every task's
durations, call/action counts, delivery count, reward, and source hashes.

Redaction excludes hidden thinking, credentials, profile contents, private
endpoints and literal URLs. Hidden test source, assertions and test stdout are
not exported; only CTRF aggregate counts, result identity and original report
hashes are present. An independent pass verified all 505 compressed members
against their public and private-source hash maps; a separate scan found no
profile value, credential pattern, URL or hidden-thinking tag in the public
files. Public materials are projections, not original HTTP bytes.

Two optional visible-response-capture rows are absent from
`gap_visible_transport.jsonl`: slot 11 cycle 104 selection and slot 12 cycle 1
maintenance. Both cycles have a raw response in the separately exported
`trajectory_memory.json.gz`; the public result marks these capture gaps. Do
not count the absent transport rows as successful independently captured
responses. There were 1,235 maintenance and 1,235 selection logical requests,
590 selected reminders present in subsequent Task requests, 432 explicit
`<no_intervention/>` responses, and 213 other non-reminding cycles. The latter
are **not** silently reclassified as legal silent responses. Task provider
attempt events total 1,301; auxiliary physical HTTP attempt counts were not
captured with equal fidelity and are marked unavailable, not zero.

All 20 run containers/volumes reported clean removal. The 20 one-use
authorization files were removed after batch finality; `AUTHORIZATION_INDEX.json`
contains their pre-removal hashes only. This is one development batch, not
evidence that PMA-gap improves over another method or that unscored tasks
failed their underlying task tests.
