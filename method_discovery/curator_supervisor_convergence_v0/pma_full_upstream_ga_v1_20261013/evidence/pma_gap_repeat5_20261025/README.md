# PMA-gap five-task repeat diagnostic: complete visible projection

Executed source: `5af52e8af831653f3ac222eb414abf1724ba3f7b`.
The five tasks are fresh, single episodes for the five evaluation-unavailable
slots of the earlier 20-task batch. They do **not** supplement or change the
original runs' rewards. The fixed task pool, PMA-gap method, both public model
identities, time policy and download policy are in [CONFIG_PUBLIC.json](CONFIG_PUBLIC.json).
Agent time/turns were uncapped for this diagnostic; these are not original
Agent-time-protocol scores. The official per-task verifier limits remained.
Existing provider retry settings were not changed.

| # | Task | New run ID | Native reward | Test entry | CTRF passed / total |
|---:|---|---|---:|---:|---:|
| 1 | circuit-fibsqrt | pma-93ac0cbbe7894351 | 0.0 | 1 | 2 / 3 |
| 2 | make-mips-interpreter | pma-44ac27a5afc44ae7 | 0.0 | 1 | 0 / 3 |
| 3 | sanitize-git-repo | pma-fe2a67c8083746e1 | 0.0 | 1 | 0 / 3 |
| 4 | build-pov-ray | pma-d23860a6006b4a1b | 0.0 | 1 | 1 / 3 |
| 5 | db-wal-recovery | pma-6e9fa66c1a154a05 | unavailable | 0 | unavailable |

All five Task agents ended and their PMA finalization, worker exit, container
and owned-volume cleanup were recorded. The fifth evaluation reached
`uv_dependencies` after successful APT, curl and uv setup, but that dependency
command returned 2. No test entry or CTRF report was produced. The retained
stage record has stdout/stderr hashes, not the error body; it does not establish
whether the cause was transient network failure or another dependency error.
There was no retry of any complete Task episode or verifier invocation.

[BATCH_RESULTS.json](BATCH_RESULTS.json) gives each task's Task requests,
recorded tool actions, PMA maintenance/selection calls, visible response counts,
reminder delivery, durations and evaluation state. Across these five runs it
records 1,137 Task request-attempt events, 1,153 tool commands, 1,137 maintenance
and 1,137 selection logical requests, and 586 selected reminders present in
subsequent Task requests. The 196 explicit `<no_intervention/>` responses are
separate from 355 other non-reminding cycles; the latter are **not** reclassified
as valid silent responses. Physical auxiliary HTTP attempts are unavailable at
equal fidelity, not zero.

Every recorded row of the Task-visible event stream, PMA request payloads,
captured public responses, memory transport, gap cycles, accepted events and
final memory/trajectory is included in each slot directory as complete
redacted gzip streams or objects. These are not developer summaries. `INDEX.json`
maps every private source file and source-line SHA-256 to each public member and
line; the private originals remain local. Use `gzip -dc <file>.gz` to inspect a
stream. The public projections are not original HTTP bytes.

For `db-wal-recovery`, 13 optional visible-response-capture rows are absent
from `gap_visible_transport.jsonl.gz` (cycle 12 selection through cycle 18
selection). All corresponding raw public responses are present in the separately
exported `trajectory_memory.json.gz`, as checked against the private original.
Do not treat this as a complete independent transport capture.

The projection excludes credentials, private endpoints/profiles, hidden
thinking, hidden test source/assertions and test stdout. Only aggregate CTRF
counts, report identities and original hashes are published. Independent
read-back checked all 154 compressed members and their public/private hash maps;
an additional scan of 22,330 public rows found no literal private profile value,
URL, bearer/key pattern, private host or hidden-thinking tag. The five one-use
authorization files were removed after finality; [AUTHORIZATION_INDEX.json](AUTHORIZATION_INDEX.json)
retains their pre-removal hashes, not their contents.

This is a repeated development diagnostic, not a new randomly sampled panel
or evidence that PMA-gap outperforms another method. The four zero rewards are
valid test outcomes; the fifth remains unscored.
