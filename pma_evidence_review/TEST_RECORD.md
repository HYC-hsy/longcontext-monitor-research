# Offline acceptance record — 2026-10-25

Result: **34 tests passed** under installed Python **3.11.15**, `regex==2024.11.6`.
Raw nonsensitive unittest output: [test-output.txt](test-output.txt).
No semantic experiment, real model request, Task, curator revision or official
assessment was run. No human labels or semantic baseline/candidate results exist.

Executed from repository root (dependency directory was outside the repository):

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11 -m unittest discover -s pma_evidence_review/tests -v
```

Both test classes block socket connection and assert zero attempts. Fake transport records actual client
payloads, raw responses and invocation counts. The real profile adapter test injects
a fake `episode.construct_upstream` and a synthetic profile: it verifies argument
routing and credential exclusion, not live factory/provider compatibility.

Additional CLI checks succeeded: build SQLite and HTML input JSON; export SQLite
extraction request; synthetic fake run (3 client calls, 0 network calls); export the
synthetic extraction plus two evidence-first requests. New real input/request files
were saved only to the workspace's private `offline-results/` sibling directory,
not staged or published. Synthetic fixtures are generated from `tests/fixtures.py`.

## Public development samples

| Sample | Step / maintenance sequence | Visible sources | Operations | Fake client calls |
|---|---|---|---|---|
| SQLite | 14 / 27 | 54 | 3 | 4 |
| HTML | 2 / 3 | 12 | 4 | 5 |

Both selected public prompts exactly match their recorded manifest SHA. These counts
are plumbing checks, not support labels. The builder reads no evaluation files.
Future prompt/reward/selection/active-bank/irrelevant-revision mutation leaves the
actual exported SQLite request unchanged. Final retained sources are not used to
reconstruct visibility. Historical content outside the visible prompt is refused.

## Implementation steps (each below 600 added+removed code lines)

Changes were made and locally checked in separate purposes, not as a single edit:

1. Vendor selected RAG types/formatters/prompts and Sourcecheck enums: 402 lines
   including licenses; Python 3.9 import and actual prompt smoke passed.
2. Frozen-cycle builder: initially under 220 lines, then receipt-less graded alignment
   adaptation; SQLite C14 hash/54-source/3-operation smoke passed.
3. RAG-derived extraction/verification skeleton and strict parsing: <250 lines;
   AST validation passed without writing to the system Python cache.
4. Captured transport, existing profile-client route, original graded locator adapter
   and CLI: <250 lines; CLI help passed.
5. Synthetic fixture and parser/builder/fake regressions: <250 lines; 17 tests passed.
6. Small hardening edits (single-index validation, nonfactual routing, nested
   whitelist and manifest checks): <150 added+removed lines; 17 tests passed.
7. Source locator and public-index integration tests plus projection-ref correction:
   <200 added+removed lines; 25 tests passed on installed Python 3.11.
8. Historical visibility/task identity checks and regressions: <100 added+removed
   lines; final 27 tests passed. Documentation is separate from code-line accounting.

The first full-locator attempt under system Python 3.9 failed because `regex` was
absent and the existing locator requires dataclass slots. No algorithm was replaced;
used the already installed Python 3.11 and installed only regex into a task-local
folder. No Python runtime was installed or reinstalled. A default py_compile attempt
could not write the OS cache; subsequent validation used AST and no-bytecode test runs.

## Known limits

- The Library study ZIP and four reports were unavailable to this consumer. Official
  fixed source checkouts were used; see REUSE.md. ZIP integrity was not verified.
- This is an engineering acceptance, not model evidence-support effectiveness.
  Extraction completeness and type assignment remain model judgments; malformed,
  missing and incomplete output is visible, not proof of semantic coverage.
- The copied upstream mock assertions were adapted; full upstream test suites were
  not run. FActScore was inspected, not imported.
- Live path is implemented but only dependency-injected fakes were tested. A working
  existing PMA/Harbor dependency environment and separately authorized existing profile
  are required before real use. No credential file was read in this acceptance.
- Future native retry/token/cost accounting must use provider instrumentation. Client
  call counts are not a measurement of HTTP attempts in a real run.
- Graded lookup runs on visible slices and translates coordinates. It does not claim
  to reconstruct absent full-source digests or wrapper blobs; fuzzy-only/unbound
  quotes cannot carry a usable supported/contradicted report verdict.
- Partial historical memory or missing revision/tombstone identities are refused;
  redacted prompt mode is explicitly degraded, never original-equivalent replay.
- No automatic memory edits, gap close policy, pending system, NLI/retriever download,
  online timing change, new execution framework, or original-method modification.

## Independent-review repair acceptance

Added complete review-input identity validation distinct from the maintenance prompt
hash; operation content digests and sequential before/deletion consistency are enforced.
The source handle and visibility formulas are checked, and the archive adapter verifies
slot-index, compressed-file and decompressed-file hashes. Existing
`LatestEvidenceGapMemory.apply_aligned_write` consults active revisions per write, so
same-cycle update/update/delete chains are now accepted in order, never from future data.
Seven added tests cover these boundaries and archive-independent core consumption.
All 34 tests pass with zero socket connection attempts and fake clients only.
The repair step adds/removes fewer than 600 code lines; original method files are untouched.
See HANDOFF.md for the stable core contract and Chinese reproduction instructions.

## Source boundary repair 2026-10-26

Baseline: 70889040cfd9024c8832a111540d701c8b8ce9f9 (retains production 58314609
and Windows compatibility 3531386f). Successor branch:
research/pma-evidence-source-boundary-v2-20261026.

Python /opt/homebrew/bin/python3.11 (3.11.15), existing ../offline-deps with regex.
Command: `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11 -m unittest discover -s pma_evidence_review/tests -v`.
Raw stdout/stderr: test-output-source-boundary.txt. 46 tests passed; baseline 34.
No real model/Task/evaluation calls, credential reads or trajectory command execution.
Network connect guard installed in fake suites, Windows local socketpair exception preserved;
this run was macOS, not a fresh Windows execution. Profile factory tested only with a mock.
ZIP hash and two old frozen input identities verified; old responses used only to generate
new requests, never as gold or transmitted externally. No new raw diagnostic files committed.
Step 1: 156 additions + 30 deletions; step 2: 212 additions; documentation separately.


### v2.1 command-context correction

Same command/runtime/network guard: 47 tests passed. Raw output in
`test-output-source-context.txt`. Final execution requests checked for original
source projection (all identity/order/field/slice fields), SQLite export PATH plus
which sqlite3 and actual observations; command-only execution citation rejected.
Every scope retains original visible source context. No new model call or private
result publication. Original frozen packet hashes remain unchanged.
