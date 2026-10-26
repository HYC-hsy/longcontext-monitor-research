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

## Citation protocol v3 engineering acceptance (2026-10-26)

Base: `000aaec23ae64288362dfdfac25a58ccdf2c3c54`, isolated worktree; original checkout
and unrelated changes preserved. Linux Python **3.12.14**, pinned `regex==2024.11.6`
installed to `/tmp/auditor-offline-deps`, no credential files read.

Initial baseline attempt lacked regex: 47 ran, 5 failures +4 errors from locator
imports/alignment. After installing the already-required pinned dependency, an original
v2.1 archive checkout passed **47/47**. Raw successful baseline:
`test-output-citation-v21-baseline.txt`; initial failure remains local `/tmp/auditor-baseline.txt`.
The old test source came from `git archive 000aaec2 pma_evidence_review`; unchanged
host method sources were symlinked into its temporary root. No old result was changed.

Command on final code:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/tmp/auditor-offline-deps python -m unittest discover -s pma_evidence_review/tests -v
```

**61/61 passed**. Raw stdout/stderr: `test-output-citation-v3.txt`.
Existing 47 tests retained and migrated only where their former wire/scope expectations
were intentionally replaced; 11 protocol tests and 3 portability tests added.

Per implementation step, additions + deletions (not aggregate; each <600):

1. Single per-quote model schema, one-based displayed/returned identity, strict binding,
   duplicate identity and overlapping-match guards: **172 code/test/template lines**;
   6 new focused tests passed (`test-output-citation-step1.txt`).
2. Remove model-scope source eligibility and batch partition; migrate old protocol tests;
   reject partial/null offsets: **165 code/test lines**; 40 focused migrated tests passed
   (`test-output-scope-step2.txt`).
3. Remove even default/advisory scope from new model prompts per user's simplicity
   direction; retain only supplied legacy metadata in reports. Add historical raw-schema,
   typed equal-text provenance, command echo, build-directory, no-scope and portability
   regressions: **218 code/test lines**. Documentation counted separately; raw test logs
   are generated output, not source code.

Final assertions include:
- Actual captured fake-client requests in single/batch mode contain only one evidence
  schema; document headers and per-quote identity agree. Supported/contradicted examples,
  empty insufficient, absent/malformed quotes and unknown/boolean indices covered.
- Exact/partial original bounds, duplicate IDs, identical text in mixed roles, overlapping
  repeated quote ambiguity, explicit-coordinate disambiguation, no self-quote/no fallback.
- Wrong legacy labels cannot hide original task, command or observation; new extraction
  and verification prompts contain no evidence_scope classification. One batch stays one
  batch regardless of legacy labels. Full original visible context remains unchanged.
- V2.1 ZIP SHA stays `d9cdb4dc0fc2c1c5a62903e42f517f9e8ff73aad4c03222aa171cde06143a436`;
  SQLite input stays `0aa854b8a7c7eb98ae5e412cdf78180597ca3400e0884046db397e9e4c2cdb90`.
  All 14 captured old responses explicitly reject as legacy wire, including empty
  insufficient with legacy top-level index. No automatic semantic reinterpretation.
- Build-directory cases preserve command+receipt and never synthesize mv/cp. Scripted
  insufficient stays insufficient; scripted supported stays a model verdict with
  semantic_proof=false. This intentionally demonstrates the remaining semantic boundary,
  NOT proof that a real model avoids invented movement.
- UTF-8 durable capture and profile factory roundtrip; Windows socketpair exception
  simulated with a local spy (no sockets opened). No real Windows executor was used.
- Future-information, deletion/tombstone, core input identity, existing profile factory
  and graded locator regressions continue passing.

No real model/Task/eval, online integration, formal memory mutation, hidden semantic gold,
resource-cost analytics or new private diagnostic publication. All new fixtures are
synthetic or read the already committed public ZIP without copying its raw text.
Direct git push had no credential helper and failed before upload; parent uses the
connected GitHub publisher and must separately report exact remote commit/tree identity.

## Direct-operation v4, 2026-10-26

Base 4e3a52a637322c3b436552390e8c0ccb035d8cef, branch
research/pma-direct-operation-review-v4-20261026. macOS Python 3.11.15,
existing ../offline-deps (regex); no dependency reinstall. Command:
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11 -m unittest discover -s pma_evidence_review/tests -v`.
Raw outputs in test-records-v4: baseline 61, step1 63, step2 initial 68, final 70 tests,
all passed. Existing 61 tests explicitly retain legacy coverage; 9 direct-path tests added.
Step1 code 226 additions/6 deletions; step2 code 169 additions/11 deletions, below 600 each.
Documentation and generated test logs separate. No true model/Task/evaluation/trajectory
command or real profile read. Profile CLI tested using FakeClient factory replacement.
Socket connect guard remains active; Windows UTF8/socketpair changes preserved, no fresh
Windows execution claimed. v3 ZIP size/hash checked; only frozen input JSON read by new
test, no diagnosis labels transmitted. Input hashes unchanged, SQLite 3/HTML 4 direct
requests verified with full operation body and fixed deletion question. No new private
raw package/configuration uploaded. Fake verdicts are plumbing probes, not semantic gold.

### v4.1 delivery-review corrections

Same macOS/Python/command and network guard. Template correction: 71 tests passed;
combined text-capture correction: 73 tests passed. Raw outputs v41-template.txt and
v41-final.txt in test-records-v4. Final request checks include exactly one full operation
output example with actual op_index for all seven frozen development operations, no old
claim output template, and existing export/fake payload equality. Invalid tool response
retains text/model verdict and records protocol_error, never executes opaque tools;
nontext response objects are not serialized, while true call exceptions remain call_error.
No real calls or credential reads. Input hashes/source protocol unchanged; strategy v4.1.

## Single-factor prompt candidate

Archive baseline f657bb866d3bbf715b37a30ca289dfb6dbea40f1; production A fixed at
77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7. macOS, existing Python 3.11.15 and regex
via ../offline-deps. Same unittest discover command as v4.1, network guard retained.
Baseline 73 passed; final 75 passed. Raw logs in test-records-entailment include initial
runs and a post-commit test-scope failure: Git's default pathspec matched the new test
as production. Corrected test to explicit glob top-level modules/vendor, no production
change; final full suite passed. New two tests are isolation/plumbing checks, not a new
semantic dataset. All seven frozen requests compared after restoring only the comparison
paragraph: exact target/source/context/example and system/prompt/tools equality. Actual
request hashes independently recomputed for A/B; strategy metadata is outside payload.
Fixed v4 ZIP size/hash and old input identities verified. No old responses/diagnoses fed
to model; no real profile read, model/Task/evaluation call, or private upload. A/B guide
Python code syntax parsed only, never executed. Windows logic retained, not newly run.
Implementation step 112 additions/4 deletions including tests; test pathspec repair is
2 changed lines. Documentation/raw generated logs handled separately under the 600-line
code step rule. No production changes outside operation_review comparison/version.

## Whole A + verbatim focus v5

Base archive 667d05b14e0f309c27a29c5ea3fc65f4f5b613b3; whole payload baseline
77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7. Old candidate comparison and its two active
isolation tests retired (reproducible at prior commit), original 73 regressions retained.
85 tests passed: 73 original + 4 partition + 8 focus tests. macOS Python3.11.15,
existing ../offline-deps/regex; no dependency reinstall or new Windows execution.
Command: PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11
-m unittest discover -s pma_evidence_review/tests -v. Logs in test-records-focus retain
step1/step2/step3/final and initial execute_request refactor syntax failure, corrected
before commit. No real model/profile/Task/evaluation/trajectory command execution.
Fixed whole request plans and same-fake reports match A on both development inputs;
all source registries and focus hashes checked. Invalid/ambiguous/source-offset cases,
Unicode/emoji/combining characters/CRLF, coverage reconstruction, complete sentence,
local isolation, reuse/delete/skipped, disagreement versus engineering failure,
protocol raw text, CLI export/fake/profile substitute and no-overwrite exercised.
Inherited AB ZIP byte count/hash/CRC verified; no new real private input uploaded.
Implementation code steps: 172+/112-; 314+/37-; 70+/3-. Documentation and generated
logs separate. Last whitespace attachment/packaging utility is a separate small step.
Fake output establishes plumbing, not improved error detection or semantic coverage.

### v5.1 local system correction

86 tests passed under the same macOS/Python3.11.15 offline command. Raw output:
test-records-focus/v51-final.txt. Dedicated local system removes the higher-priority
whole-operation target conflict; final request tests check both system and prompt.
Existing seven frozen whole payload/report comparisons with A still pass. No real calls.

v5.2 final: 87 tests passed, raw output test-records-focus/v52-final.txt. Delete whole
call/protocol/parse/binding errors retain engineering_incomplete in per-operation
summary; normal delete and failed/unknown skipped cases remain not_applicable. Whole
payload still matches A. Intermediate v5.1 archive was not published; final package is
regenerated using final code SHA. No real requests.
