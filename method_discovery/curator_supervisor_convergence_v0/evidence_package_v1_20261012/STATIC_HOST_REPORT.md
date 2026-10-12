# evidence_package_v1 host-static zero-model continuation audit

Status: **STATIC_METHOD_OFFLINE_BLOCKED**. The host-static cutoff, isolation,
native MonitorAgent/provider fake-request loop and bounded Go test receipt path
have positive offline evidence. The complete proposed N-versus-candidate static
experiment is **not yet certified or authorized**. The shared-container live
`MonitorRuntime` evidence-package launch gate remains enabled and unmodified.
No real model, Task Agent, provider API, native evaluator, training or scoring
model was called in this phase.

## Source, identity and call chain

This phase started at archived `ce332b5968b0dc020d8051c2e41887a19a67dc3a`
with a clean tracked tree; unrelated untracked pycaches were preserved. Small
code steps: `cf2bf5bd` materializes certified cutoff and retains packet/root
context; `b12f871b` adds host receipt identity, raw query, stage archival and
pre-send/turn safeguards; `6270fb81` adds fake-transport-only static session
and native-Go probes; `393b90db` wires controlled Go checks through actual
Monitor dispatch and records Go source identities. Final report/packet commits
are separate. Full base-to-final diff is included in `STATIC_HOST_AUDIT.txt`.

Actual static path:

`diagnostic_static_adapter.adapter.materialize(C01/C02)` → `StaticHostPort`
→ `PilotHostBridge`/`SpoolAnalysisSessions` → `MonitorAgent.review` →
`loop.run_review` → `MonitorProviderClient.complete/_request_once` with an
explicit instance fake sender → native tool `dispatch` → host-only `EvidenceFrontier`.
The controlled `go_check` additionally calls native `go test -json -count=1`
through the same spool/Docker port, reads its trusted raw output, classifies
actual JSON events, and issues a host receipt. Unknown/partial output is not a
behavioral pass. CoverUp, Agentless, Build Systems à la Carte and PMA remain
inspected references, not imported runtime code. `REUSE_MANIFEST.json` and
`SOURCE_LOCK.json` retain fixed sources, licenses, versions and reasons.

The two registered image IDs are Fyne
`sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`
and Kitex
`sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e`.
The native Go fixtures saw `go1.22.12` and `go1.23.12`, respectively, and
recorded each `go` binary and installed `test.go` SHA in `SOURCE_LOCK.json`.
The installed `cmd/internal/test2json/test2json.go` SHA was
`19b8bd6362a5101dd04f76d3ce6e937755048f1a9989648b9f524ddbda9fd482`
in both images. The exact upstream release-tag source tree was not independently
re-fetched; these claims are identities of the installed frozen images.

## Static input and isolation facts

`materialize` verifies source archive/public prefix, Task Book, ordinary-file
manifest and cutoff mutations before mounting. C01 uses cursor 120 / 2472
ordinary files; C02 cursor 161 / 2476 files. C02 host and Docker `/app/go.mod`
matched SHA `fa5391869ecec9660921234c0f926a1093fad3967ce5aa5f3ef71d84039707ed`.
The positive Docker probe observed `/app` and `/pilot_control` unwritable,
`/tmp` writable, `/tests/test.sh` absent, and host frontier/spool unavailable.
The registered Docker invocation uses `--network none`, read-only root,
dropped capabilities, `no-new-privileges`, `/app`/public evidence/private
cognition/control as read-only binds, and only per-fixture home/tmp/cache/output
as writable binds. The host protects the canonical frontier, stage branches,
request archive and new candidate dialogue outside those binds. The original
historical dialogue prefix hash remained unchanged after a complete fake root
review. This is static host/tool isolation, not a claim that the old live Task
container can safely host the frontier.

The common model-visible static note is exactly `STATIC_COMMON_CONTEXT` in
`static_session.py`; it says Task does not advance and controls are simulated.
The tested N local wait and evidence-package root intervention both archived
`simulated=true,input_sent=false` with no Task callback. The candidate root
fixture sent six complete fake requests: A opened a case/read material/created
a packet; B used only payload-visible IDs to query A's raw receipt, recorded a
finding and proposed intervention. A and B stage histories were archived in
the host-only frontier; the original parent history was restored after the
review. The actual captured requests retained model `claude-opus-4-8`,
`max_tokens=8192`, no temperature field, and purpose-specific tool schemas.
The N fixture used the same resolved pilot profile branch but C01, not a
completed same-scene paired comparison. No live endpoint compatibility claim
is made.

## Test evidence

`run_static_checks.py` ran five bounded, zero-network groups once and placed
the exact command, stdout, stderr, exit code, byte lengths, durations and
SHA-256 in `STATIC_OFFLINE_RAW_RESULTS/<group>/`. The complete files are
embedded verbatim in `STATIC_HOST_AUDIT.txt`.

| Group | Actual result | stdout SHA-256 |
| --- | --- | --- |
| core | 81 passed, exit 0 | `2e36a934884285822dfb6dd9ce617d6682fdb899af011416bfd03ad82e5c7e54` |
| profile_bundle | 3 passed, exit 0 | `4347ce3233432dc8ddd4fe1f6b6e9645b903e67d0e6e423c7698d68273f4a271` |
| static_host_session | 4 passed, exit 0 | `bceab30d7420291f295eb702add1aef275f9f0995b50d7537b11f2ad40918daa` |
| native_go | 3 passed, exit 0 | `2ad18a24d98275c291223b34bcc4bbad31d1fcda88a60f94c829dfc542f03999` |
| existing_docker_candidate | 2 passed, exit 0 | `a9c5bf13b7d6bc9896b5ad70df8566e3138625abbdeb21a3b4171d97427e1caf` |

The raw record preserves earlier targeted failures too: the first controlled
Go fixture misclassified native compiler diagnostic preamble as incomplete;
the parser was limited to require both the preamble and the native `[build
failed]` package event. The first static session run exposed a missing native
recovery deadline/stop binding; both were set on the fake session without
removing the production safeguard. C01 identity was initially omitted from
the research public-profile projection and was explicitly recorded as false.
These failed attempts were not model experiments. Pytest also emitted a
preexisting atexit `PermissionError` for a Windows temporary directory after
passing tests; exit codes were 0. No unrelated temp/pycache was cleaned.
After adding explicit assertions that no future manifest, report path or
condition-directory name appears in the model-visible static payload, the
static-host/session group was rerun once into the separate
`STATIC_OFFLINE_FOLLOWUP_RESULTS/static_host_session/` raw record; it did not
overwrite the earlier five-group evidence. This follow-up is an additional
test of the same zero-model path, not a new diagnostic attempt. It passed
4 tests with exit 0; stdout SHA-256 is
`c5dad66100c159e504b6b46244b37496b4d5adc47aa3b8273a928cef664289bb`.

Real model/API/Task/Supervisor-inference/native-evaluator/training/scoring calls:
all **0**. Counted fake sends: six in the static candidate root fixture, one
in the static N fixture, and 15 in the preexisting Docker candidate fixture;
the old core fake-provider test printed another six. Some other unit fakes do
not expose an aggregate counter, so 28 is an observed lower bound, not an
invented exact global total. The two Go image tests execute native public Go
commands only; no benchmark evaluator was invoked.

## Remaining certification gates and interpretation

1. The static session currently accepts a caller-supplied wake text and starts
   with empty provider history. It has **not** reconstructed/frozen the precise
   historical Supervisor input prefix and same-scene N/candidate first-request
   comparison. Its fake prompts are genuine requests through the real client,
   but not certified historical-request replicas. A future static model batch
   needs a frozen request assembler and pre-send identity checks.
2. The protected frontier now binds case/scope at actual reads and has an
   explicit cross-case link, but automatic relevance invalidation is still
   limited: cited live Task file changes are checked; check-definition, oracle,
   config and declared-dependency changes are not comprehensively tracked.
   Version-uncertain concurrent source observations remain uncertain. A Go
   test pass is scoped to the private fixture, not the live Task tree or whole
   behavior. Natural-language scope/causality/oracle correctness is not
   programmatically proven.
3. Root cutover, cancellation, continuation/format repair, repeated entry,
   abnormal A/B history exits and control freshness have some prior core tests,
   but this new **host-static** entry lacks the full requested matrix of
   fault-injection and paired per-scene requests. No real static batch starts.
4. C01/C02 are known historical fragments. False-premise and
   environment-blocked cases have no certified cutoff materials and are
   explicitly left missing in `FUTURE_DIAGNOSTIC_MANIFEST_DRAFT.json`; none
   were fabricated. The existing history is a static common modification,
   not online process recovery. Live Task/Monitor co-location still fails the
   protected-frontier boundary and `MonitorRuntime` refuses candidate startup.
5. Real provider compatibility and method effect are untested. The test
   `go_check` uses a synthetic private package on both images to classify
   native result types; it is not a task-specific behavioral finding.

Therefore the narrow conclusion is: **static material/tool isolation and a
limited actual fake-transport method path passed; the complete static
experiment protocol is blocked. Live deployment remains unverified/disabled.**
No outcome claim about the evidence-package method follows from this audit.
