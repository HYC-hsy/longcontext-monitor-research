# Static Supervisor diagnostic — stage 1 offline report

Status: **STATIC_DIAGNOSTIC_OFFLINE_BLOCKED**. The historical online Supervisor process remains unrecoverable. The cutoff fixtures and Docker tool isolation are certified offline, but the repository does not yet contain a protocol-accurate, authorized multi-request provider runner for these static diagnostics. No model experiment was run, and this report does not promote the static snapshots into historical online replay.

## Identity and scope

- Research repository: `E:\longcontext-cqs-v0-20261005`, branch `crs-v0-20261007`; stage-0 parent `e6a48ee06b1247f40327523773df52a3a40a5d29`; historical archive `8ff2675f92b979eb4747540e32ddba8e9fc0b2a9`.
- Stage-0 input and frozen prompt-diff files were not edited. Production changes: **0**. No push was performed, per this stage's explicit instruction. Existing unrelated `GenericAgent-main/monitor_agent_core/**/__pycache__` entries were left untouched.
- C01 is the ordinary request at dialogue 308 / public cursor 120; C02 is the root investigation request at dialogue 419 / cursor 161, after the source-observation receipt at dialogue 418. These are previously known fragments, not autonomous opportunity discovery. C01 is not a predefined “must be silent” case: an unresolved problem existed, so control quality depends on the particular public grounds and whether intervention would interrupt reasonable progress.
- Selection and exclusions remain in stage-0 `CHECKPOINT_CANDIDATES.json`. Static materialization freezes Task progression for both arms. It does **not** restore the historical pending process/session/root-handoff lifecycle.

## B_static / F_static request construction

The four complete request payloads are `C01_B_STATIC_REQUEST.json`, `C01_F_STATIC_REQUEST.json`, `C02_B_STATIC_REQUEST.json`, and `C02_F_STATIC_REQUEST.json`. `REQUEST_COMPARISON.json` gives their canonical hashes and machine checks. B_static is the retained full archived B request with this identical environment note appended to its system text; F_static makes that same common change and only the two exact paragraph substitutions in the unchanged stage-0 `PROMPT_DIFF.patch`:

> 这是固定截止快照上的诊断。Task 不再推进；历史工具会话不代表仍有活动进程。可以调查允许的公开材料。wait、intervene、allow_complete 在此只记录诊断提议并结束当前诊断，不会等待 Task 新反馈、向 Task 投递消息或执行真实完成放行。

The note is a common **archived B → B_static** modification, not a treatment difference. The historical messages, ordinary/root-specific seven-tool schemas, model fields and sampling/request parameters are otherwise copied. The retained requests specify `claude-opus-4-8`, `max_tokens=8192`, adaptive thinking/high effort and streaming; they do not send a temperature field. Neither static arm adds one. F is the two substitutions together, not an estimate for either sentence separately. No task answer, future result, candidate label or evaluation appears in model-visible material.

| Scene | archived B canonical SHA-256 | B_static | F_static |
|---|---|---|---|
| C01 | `f338307c8a5279de4446eb7ade415bc34aa38d237089d6bb99b45f90c3ab3866` | `280d607a96a2372c22ad17e29873258ad77ddd65a10e47f50fbc7ffa58e771f2` | `e94770454242a8a164bc8f175af93a039030b59876c9d855843e164adb1ca2a7` |
| C02 | `f76f495965881672eea450c8924c406a5aac70160e501ca1bad434e04269c0af` | `31635aae9700c23c7357ecbc4cc4ebf8d4b8a1d55c47f19dccb876c72a` | `535b8d6855de05b51befb83450b9befb3efb1e497795410b61ec7a2f254f55cb` |

Frozen stage-0 prompt SHA-256: B `b0f2cf6982cefc5ef1c4a556104a511453dde02fc550e986719f460177cfdaee`; F `18c73247e6485097e3d31424c3ffd1c34c3c137a9c26bdd83b22b4f3e20d77b1`; diff `af0201a38c07bfc76a8ca75cd373604e571d2c5e33d7cd967bf297a769e02bdf`.

## Static material and isolation

`C01_VISIBILITY_MANIFEST.json` and `C02_VISIBILITY_MANIFEST.json` enumerate each model-tool-visible file, SHA-256, size and cutoff basis. Ordinary workspace reconstruction yields C01 tree `88b7f94d499368196bc8ac1870da4491769598eb4ce567b8c6e12a10bf289a0b` and C02 tree `40acbedf3c03d863cac8514298618f74ca999c706466dc426ae8eb638708d2f0`. The former and latter fixtures contain 2,513 and 2,524 visible files respectively, including historical Git files, cutoff public evidence and certified historical outputs. Each attempt must receive a fresh materialized copy; monitor-private writes and new command output stay private to that attempt.

The tested Docker tool port uses frozen image `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`, maps `/app` and cutoff task evidence read-only, maps one attempt's monitor-private directory writable, masks `/tests`, uses a read-only container root and `--network none`, drops capabilities and passes no host credentials. `ISOLATION_CERTIFICATION.json` records actual Linux-container probes for task/public/private access, denied source/evidence writes, parent/symlink traversal, marker absence for host research/future/other arm/evaluator, credential environment absence and network denial. This certifies **this offline Docker tool port**, not arbitrary future runners or a live model invocation. No complete archive or evaluator material is mounted. File-read path checks alone were not accepted as an isolation proof.

Historical absolute source paths are mapped only to the three explicit static mounts; an unresolved path cannot fall back to the full archive. All historical code-run outputs are copied only when the cutoff dialogue receipt chain proves terminal completion and its concatenated stdout equals the retained output bytes. C01 has 11 such outputs and C02 has 18. A historical `running → success` sequence is treated as completed historical output, not a live process. Unknown/unproved session IDs return `unavailable`; new investigation commands receive fresh `static-*` IDs and are never attached to historical host processes. See `SESSION_HANDLING.json` and per-scene visibility manifests. No cutoff-relevant unavailable output was observed, but a newly requested unlisted historical result remains unavailable rather than fabricated.

## Control, budget and evidence recording

`RUN_ORDER_AND_LIMITS.json` freezes C01-R1 B/F; C02-R1 F/B; C01-R2 F/B; C02-R2 B/F; C01-R3 B/F; C02-R3 F/B. These are 12 diagnostic attempts over two historical fragments, not 12 independent tasks. Every started attempt and complete response must be retained. The first schema-valid wait/intervene/allow_complete is only a diagnostic proposal and ends that attempt; root allow_complete is a `release_proposal`, never a restored multi-turn approval. Later calls in the same response are recorded unexecuted; multiple conflicting control proposals fail protocol. Invalid arguments return a uniform mechanical error and consume the ordinary budget. A legitimate but wrong proposal is a method outcome, not infrastructure invalid. Budget exhaustion without proposal is retained as `undecided`, never silently changed to wait.

Per-attempt caps: 12 provider requests **including retries**, 48 tool calls including failures/polls, 1,200 wall seconds, 60 seconds per new command and 600 seconds cumulative tool wait. These are new common static-diagnostic limits, **not** the historical 300-turn ceiling; no countdown is model-visible. A timed-out command's container is stopped and removed. The fake controller records complete response batches, call indices, receipts, skipped calls and terminal reason. `FACT_AND_RUBRIC_TEMPLATE.json` provides per-event evidence locators and five separate review dimensions; it records erroneous intervention, erroneous release and missed necessary intervention separately, with `unknown` permitted. It does not score by length/tool count/mentioning Refresh. B/F labels and order may be hidden from later reviewers to reduce bias, not to claim full blinding. No semantic judgment was performed in this stage.

## Offline verification and remaining gate

Commands: `python -m method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.freeze`; `python -m method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.certify`; `python -m unittest method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.test_offline method_discovery.curator_supervisor_convergence_v0.diagnostic_static_adapter_v1_20261009.test_docker_tool -v`; `git diff --check`.

The request/material hashes and container certificate are in the machine-readable files. The final combined zero-model run passed **18/18** tests, 0 failed, 0 skipped, in 117.415 seconds. Model/provider sends 0; Task Agent 0; Supervisor model 0; native evaluator 0. `NoLiveProvider` raises on any attempted send; the test provider is scripted in-process only. There is no live authorization or external-transport entry in this stage.

The remaining gate before any later model experiment is a separately audited protocol-accurate provider loop/capture and fail-closed send gate using this certified container port, with complete tool-use/tool-result ordering, retries, per-attempt artifact retention and actual model-request visibility. The present fake controller and tool-port tests do not by themselves certify live provider message assembly. No model run is authorized; the online-history recovery remains **BLOCKED**. A new research instruction is required before implementing or running that missing live path.
