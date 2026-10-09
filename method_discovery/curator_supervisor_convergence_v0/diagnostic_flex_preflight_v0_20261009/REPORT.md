# Supervisor diagnostic-order contrast: stage-0 offline preflight

Status: **DIAGNOSTIC_PREFLIGHT_BLOCKED** for a live, faithful Supervisor diagnostic continuation. No model/provider, Task Agent, Supervisor, benchmark, evaluator or training execution occurred. This package contains source-bound *candidate* inputs and deterministic checks only; it is not an executable trial or a claim about supervisory quality.

## Repository and reference identity

The shell initially opened in `E:\LongContext`, an older `m2-from-m1c` worktree. `git worktree list` identified the relevant checkout as `E:\longcontext-cqs-v0-20261005`, branch `crs-v0-20261007`, HEAD `8ff2675f92b979eb4747540e32ddba8e9fc0b2a9`, remote `public` at `HYC-hsy/longcontext-monitor-research`. Root `AGENTS.md` and relevant run/archive conventions were read. Existing untracked `GenericAgent-main/monitor_agent_core/__pycache__/` and vendor `__pycache__/` entries were preserved, not staged or cleaned. No reset or historical edit. This report commit is intentionally **not pushed**, per the current task's explicit instruction.

The priority archive is `method_discovery/curator_supervisor_convergence_v0/crs_rhr_rer_fyne_high_budget_20261007/archive/r1/`. Git blobs at the reference commit were checked. Priority files:

| Archived file | Bytes | SHA-256 | Records |
| --- | ---: | --- | ---: |
| `monitor/audit/dialogue.jsonl` | 1,097,866 | `6281ae9a8ae85f70df2339e38f4e4b130d644d085f3a1628e60bface980b0409` | 614 |
| `monitor/task_evidence/public_events.jsonl` | 654,818 | `f2a007c9afa3ed8d097e249d6b96d55717066d61217c1229f823764bb6ad9441` | 161 |
| `monitor/private/reference.md` | 5,598 | `f6f070f65896a81ba3eeda1b9034b9eb34f23627099e5356e2bde24d24c77355` | one file |
| `agent/output.txt` | 107,488 | `c5256bdca2018264ead2c70bfe536647e43b89783de01618e16b039eefc4cc7e` | one file |
| `runner/manifest.json` | 5,128 | `bcaa8ef8074b431b6b9cd2af84f5439bd26a0ae34d8b947c979fbd95a6f37e9b` | one file |

These record counts and hashes establish archive-file identity, **not** an independently recoverable live process. `bridge/gateway_control_raw.zip` SHA is `79c3c753f070c71075df270bd5d3a00e67e8579757f073a59a0fab73ee0115a8`; it retains 56 monitor and 83 Task full request records. The dialogue's `model_input` rows are incremental input records, not complete provider payloads. The complete B requests here were read from the ZIP and checked against their matching `review_context` system and incremental `model_input` content. `provider_history.json` is a final snapshot and was not substituted for an earlier request.

The actual run manifest binds task `fyn-2.2.0-roadmap`, task image `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`, `GA` source SHA `7591357247aefe62184b2b01e8472b661a35c73db236c82474e9e1ef337f936e`, isolation `no-network-unix-inference-v1` with snapshot `209340005e5a037a69a34d7b6ebfb33ad0bf1f0d55b51db929b2edf9a0205228`, Task/Supervisor model `claude-opus-4-8`, 300 Task-turn ceiling and 10,000-second integration cap. The actual deployed private Supervisor profile was inspected in place and only whitelisted, non-secret fields were copied to `SOURCE_IDENTITY.json`: ASE, CRS-v0.2, RHR-v0 and RER-v0 all true; ASE meta regulation false; max_tokens 8192, temperature 1, high/adaptive thinking, context window 200000. The archived manifest and provider requests corroborate model/profile usage; no credential or private endpoint value is included. Actual host ordinary/root review ceilings were 300/300 per frozen runner environment. The later turn-30 causal-pair adapter disables monitor runtime and completion callback; it cannot be used to resume this Supervisor by toggling a flag.

## Checkpoint selection and recovered material

Selection was frozen before any candidate output: one ordinary-progress review after a current Task tool event, and one root investigation request after a completed source observation. See `CHECKPOINT_CANDIDATES.json` for each of the five required recovery dimensions, source lines, and explicit exclusions. The ordinary-progress scene is dialogue line 308 / Task public cursor 120, turn 61; the root scene is line 419 / public cursor 161, turn 83. The research locator was verified: line 417 is a Supervisor `code_run`, line 418 its successful source-result receipt, and line 419 the next model input. These locators are not added as hints to F or B.

The complete ordinary workspace was replayed from the historical clean task image (`HEAD 7229e889d49c81a83b0b7e09400837f67f6ddad5`, ordinary tree `a78fd1e12055de14567a74114ecef238f3b9bfdec267b7f69c19607f60b38bdf`) plus the original-task sidecar and public mutation receipts. An archived failed `file_patch` at cursor 78 was confirmed to be no-write before the production write path. All 21 post-result shell commands through cursor 161 were reviewed as `find`/`grep`/`ls`/`pwd`/`go build`; no unreviewed command form is accepted by the script, and final `go.mod`/`go.sum` bytes equal the clean image. The replay at cursor 161 matches the retained pre-verifier tar **per ordinary file**. This is a worktree certification, not a certification of a resumable host process, Git index, tool session or complete online runtime.

| Scene | Ordinary files | Replayed tree SHA-256 | Full B request | State shortfall |
| --- | ---: | --- | --- | --- |
| progress restraint, cursor 120 | 2,472 | `88b7f94d499368196bc8ac1870da4491769598eb4ce567b8c6e12a10bf289a0b` | retained in gateway; 73 messages | Task was concurrently advancing; exact paused monitor/tool session and cutoff-only readable filesystem unverified |
| root investigation, cursor 161 | 2,476 | `40acbedf3c03d863cac8514298618f74ca999c706466dc426ae8eb638708d2f0` | retained in gateway; 96 messages | pending root-handoff/review state and cutoff-only readable audit/command outputs unverified |

The retained pre-verifier tar has SHA `e4bec1565382c5d49b4e06aa051ec909d22a2319c560c4da1b2b2341362229eb` and the same ordinary tree SHA as cursor 161. Original-task source `monitor/task_evidence/original_task.txt` has SHA `cae5f11a98aa573cf93629b8fb0becc18f395c5bdad25e09b8927d06f0725080` and was used verbatim for the sidecar. Full per-file rows appear in `WORKSPACE_FILE_MANIFEST_CURSOR_120.json` and `_161.json`. No post-cutoff final workspace was used to fill the cursor-120 tree.

## Exact B/F input drafts

`B_SYSTEM.txt` is the **actual 5,813-byte recorded system** at both requests, SHA `b0f2cf6982cefc5ef1c4a556104a511453dde02fc550e986719f460177cfdaee`. It contains the production ASE `SYSTEM_PROMPT` (SHA `d1268a1c6227bdd0c02e23c65ea4f9f356717ae9cd1c8f26b265a1aa37a65648`) plus the exact archived review-control suffix, not just the source constant. `F_SYSTEM.txt` is the complete proposed 5,912-byte text, SHA `18c73247e6485097e3d31424c3ffd1c34c3c137a9c26bdd83b22b4f3e20d77b1`. The two complete before/after paragraphs and exact unified diff are in `PROMPT_DIFF.patch`. No matching local F manual/implementation was found; this text is not assumed to be an older F version.

The first replacement removes the forced *measurement-first before implementation-depth* order and lets the Supervisor choose the investigation path from the current evidence gap. The second permits a public-evidence-grounded concrete diagnosis and next investigation suggestion, while preserving default silence and Task ownership. All other B system text, seven tools, model parameters and each scene's message history are unchanged. These are **draft provider inputs**, not requests sent in this turn:

| Scene | Complete B canonical request SHA-256 | Proposed F canonical request SHA-256 |
| --- | --- | --- |
| progress restraint | `f338307c8a5279de4446eb7ade415bc34aa38d237089d6bb99b45f90c3ab3866` | `3ed0681c5698c4a17e38f84d654cd0094bc028c7196769cdd70997b9b66fb4bc` |
| root investigation | `f76f495965881672eea450c8924c406a5aac70160e501ca1bad434e04269c0af` | `037a30af53a6b5c3d1ad3113e452e26b9a1d8f02dd02e59c8749fd67afd34144` |

The four full JSON drafts are named `<scene>_B_REQUEST_DRAFT.json` and `<scene>_F_REQUEST_DRAFT.json`. Exact B JSON content equals the retained full gateway request; only JSON serialization differs from the gateway raw bytes. F differs from B only at top-level `system`. No case label, outcome, manual diagnosis, native evaluator or future result was appended to the model-visible draft.

## Offline checks and hard stop

Commands and passed/failed/skipped list are in `OFFLINE_CHECKS.json`. `freeze_inputs.py` mechanically checks actual full provider requests; `check_workspace.py` performs read-only-source, offline workspace replay in a temporary directory; `test_offline.py` has 8 tests, all passing. No script imports a provider client or starts a Task/monitor process. Draft request cursor-locator scanning found no public cursor later than its cutoff. That narrow check is **not** a proof that future archive files would be inaccessible through `file_read`/`code_run` in a future live diagnostic.

The currently **missing gate** is a certified, cutoff-only, independently cloned tool-readable filesystem and Supervisor runtime/session boundary for both arms. The historic live monitor was concurrent with Task; a static frozen view would be a shared modification of the environment, not a faithful online replay. The root scene additionally needs explicit pending-handoff state handling. We did not invent that state, filter final archive ad hoc for a model, or mount a full archive containing future events. No model experiment is authorized by this preflight.

`EXPERIMENT_MANIFEST_DRAFT.json` proposes two fixed scenes, B/F, three repeats each (12 diagnostic reviews) with balanced order, unchanged model/tools/host ceilings, all attempts counted and explicit protocol/infra failures. It proposes observing actual tool choice, evidence grounding, discrimination, concrete usefulness and false intervention on normal progress. Response length, a mere `Refresh` mention, model self-score and native outcome are not success metrics. This is a *draft*, not a run manifest.

If exact online restoration is required, the current evidence is insufficient. A separately authorized **static-material diagnostic** could compare B/F on the same certified cutoff snapshots, but would answer only how the Supervisor investigates fixed public material under changed information order, not how an online intervention changes Task outcome. A separately authorized **new full-task paired run** could test downstream behavior in a live concurrent system, but would not be a same-checkpoint replay and would require new source/isolation/resource freeze. Neither alternative was launched or silently selected.

Production changes: 0. Archived/frozen source changes: 0. Provider/API calls: 0. Task Agent calls: 0. Supervisor calls: 0. Native evaluator executions: 0. No push.
