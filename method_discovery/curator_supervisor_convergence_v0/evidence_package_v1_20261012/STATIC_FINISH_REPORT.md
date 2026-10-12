# Host-static evidence_package_v1 limited finish

Status: static entry and method wiring passed the targeted zero-model checks. Live MonitorRuntime deployment remains uncertified and disabled. No real static batch was started.

## Scope and baseline

- Remote archive base: `2c5b95ee45b27f87045613fb1335b37caa59f586`; content base: `f42e861a059a22f81a9d6e6075fae8b1dea18ae5`.
- Implementation/test commit: `f3793d1e5ec02b5bcbf88b8e3cacb3e8abfbb4f2`, following small commits `1b1b28d2` and `b080e221`.
- This is a *new* host-static diagnostic input, not replay of the historical Supervisor process. C01 uses certified public cursor 120 and Task turn 61; C02 uses cursor 161, Task turn 83 and the certified completion handoff. Both start with empty active conversation history. The common neutral wake is derived from the certified material, not free researcher text.
- N and evidence_package_v1 share the original public task, cutoff public events, Task Book, workspace, static note, model and generation fields. System method instructions, A/B staging and frontier tool schema differ as treatment. The first actual pre-send requests and hashes are in `STATIC_FIRST_REQUEST_COMPARISON.json`; no temperature field was added.
- The known historical failure and later assessment are not in model-visible material. False-premise and environment-blocked cutoff cases remain uncertified, so the future batch manifest remains a draft.

## Limited repairs

- The Docker visibility probe now fails on each missing exclusion rather than printing unconditional success. A synthetic exposed sentinel proves the negative check fails. Actual inspect records a read-only `/app`, read-only root filesystem and `none` network; `/tests/test.sh` and host control/frontier/request roots were absent in the container. These observations certify the tested fixture, not live shared-container deployment.
- Private `go_check` uses a normalized `cwd`, conditionally changes directory, rejects option-like package arguments and keeps selected-test outcome distinct from package/parent-test outcome. A skipped child under a passing parent is not a pass. Actual Fyne/Kitex Go JSON outputs and stdout/stderr are archived.
- Private Go check definitions and bounded private source identity are captured before/after. Subsequent private commands stale earlier Go receipts. The bounded identity is not a complete dependency graph or atomic snapshot; unknown dependencies and `version_uncertain` remain explicit.
- `revise_case` now applies receipt source/scope/completion/applicability checks consistent with finding control. Changing a hypothesis or setting stale alone cannot clear an active objection. Explicit retraction records whether a premise was refuted or a problem repaired. Session polls retain the case/scope/check bound at start; cross-case reuse requires explicit sourced association.
- A/B continuation prompts and working notes are stage-labelled; parent note/history are restored across handoff and abnormal exits. Maintenance requests remain distinct from outer model cycles, including the near-budget fake continuation/format-repair case. Queue rotation is a limited static prototype, not a proof of fair or complete clue exploration.

## Executed zero-model checks

The archived `result.json` for each group contains the exact command, cwd, exit code, duration and hashes of complete stdout/stderr. Selected final groups all exited 0: core 85 passed; profile/bundle 3 passed; native Go 5 passed; prior Docker candidate 2 passed; host-static session 9 passed. The final static group took 421.56 seconds. Its host requests and tool returns are in `STATIC_FINISH_RAW_20261012/FINAL3_ARTIFACTS/`. The Go through-provider loop recorded test_passed, test_failed and all_skipped, with seven fake pre-send requests; another C01 candidate/C02 N loop recorded five and two fake requests with tool backfill. All calls intercepted the actual configured provider send boundary with fake transport and `offline.invalid`; no real endpoint was configured. The final artifact set contains 25 fake pre-send requests total, including separate fixtures. This is not a count of independent experimental attempts.

Raw earlier failures remain preserved: the first final static run had an unconfirmed Docker `--rm` inspect timing failure; the next static run exposed fake-responder fixture mistakes, subsequently corrected; the final group is the single reported passing rerun. A Windows pytest atexit temporary-directory PermissionError appeared on stderr after exit 0, and is not hidden or counted as a test assertion failure.

No real Task Agent, Supervisor model, provider API, native evaluator, training or scoring-model call occurred in this phase. The fake-post/test controls prove the tested paths did not fall through to transport. This is not a blanket runtime telemetry claim outside the tested process.

## Identity, artifacts, and limits

`STATIC_FINISH_FILE_SHA256.json` lists each raw artifact's byte count/SHA-256, all scoped changed source blob IDs, committed byte SHA-256 and tested working-tree SHA-256. The working `agent.py` byte stream differs from its committed blob (`git ls-files --eol`: index LF, working mixed endings); Git-normalized status is clean. These two byte identities are not conflated. The archive includes the complete scoped diff, original test stdout/stderr, Docker mounts, host requests/returns, raw Go outputs, stage/frontier records and preliminary failed attempts. It is a selected audit collection, not a full host image. Public task/source content and offline fixture output are included; no credentials or private endpoint text should be included.

The host-static entry is fake-transport-only and does not authorize a real static model run. Live MonitorRuntime still rejects this candidate under the unmodified deployment gate. No production Task continuation or evaluator was invoked. Real-model diagnostic quality and live isolation remain unverified.
