# UC-R5 execution bridge v1 — zero-model acceptance record

Status: `ready_for_main_review`, **not authorized to execute scientific slots**. The original 30 slot identities, allocation, profiles and preregistration were not edited. The independent authorization file required by `uc_r5_execution_entry.py` was not created.

## Installed integration anchors

- Installed Harbor source HEAD: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`, version `0.20.0`.
- The only local Harbor source patches remain:
  - `src/harbor/environments/docker/harbor-docker-egress-control-sidecar/Dockerfile`, SHA-256 `ac053c8b18065bb36efca75966440b6a9a77caa1aa05a1f7979a2fbe2542ffda`;
  - `src/harbor/models/task/config.py`, SHA-256 `e4d40b8aa11a9b190d285872a771d9ce19f7e3b636a412fceb10cd6247ebb4d0`;
  - `src/harbor/trial/single_step.py`, SHA-256 `82e41b897b1501dc36dc8de3ffa3801f737106840bdbcce70a2838df77fa70b5`.
- Source call order, checked by function rather than line number: `Trial.create` constructs a trial; `_emit` awaits hooks in registration order; `_run_agent_phase` emits `AGENT_START` before `agent.run` and `AGENT_END` in its `finally`; `SingleStepTrial._run` collects agent artifacts before `_run_verifier`; `_run_verifier` emits `VERIFICATION_START` before invoking the evaluator. Hook exceptions propagate to `Trial.run`, which records failure and does not continue into the next stage.
- The bridge bootstrap is a separate Harbor CLI wrapper. It must install hooks successfully before calling the original `harbor.cli.main.app`. It does not use `sitecustomize`, whose import failure could otherwise be non-fatal.

## Scope and flow

The executable research entry requires a separate exact authorization and the frozen addendum. The already committed `execution_authorized=false` preregistration cannot launch it. It delegates to the unchanged `run_ultralong_m12_proofs.run_proof`; a narrow wrapper around its existing `build_bundle` attaches only a gateway-sidecar script and private IPC mount. The wrapper around `m4.run` invokes the original Harbor CLI through the hook bootstrap. No Task/Monitor loop or runner source is copied.

At `AGENT_START`, the hook checks the actual trial, downloaded task tree, instruction, task image, main/gateway containers, network/mounts, generated source bundle/profile and output root. A gateway wrapper calls the frozen `_resolve_request` first. Before each inference send it archives the transformed body without credential headers and waits for a host permit bound to the slot, route-derived role and request SHA-256. Task and Monitor are independently checked against their actual staged input/original-task bytes; neither waits for the other. The wrapper returns the resolver tuple unchanged. The frozen Handler retains TLS, headers, response streaming and provider retry logic. A send-position close check blocks new sends after agent end.

At `AGENT_END`, the hook closes inference, stops and restarts only this trial's `main` container to terminate lingering writers while preserving its writable layer, then captures `/app` as a tar with a content/type/mode/size/symlink manifest and available Git status. At `VERIFICATION_START`, it checks the same main container ID and a second full `/app` manifest before releasing the original evaluator. A capture/binding error raises, leaving the evaluator uncalled. The final Harbor `END` receipt binds the capture digest to the original trial result identity. Proposal-time checkpoint is never used as the scoring artifact.

All wait, gate, capture and binding durations have separate mechanical receipt fields. Service-observed model identity, actual model tokens, final scoring artifact and evaluator outcome are intentionally unavailable before a real run. No `native verifier`, `test.sh`, `solve.sh` or oracle ran for this acceptance.

## Offline evidence and limits

`OFFLINE_TEST_OUTPUT.txt` contains the exact final pytest/ruff output. Tests exercise a local fake upstream (one successful synthetic send, exact transformed request body, unchanged response chunks), denial without permit (zero sends), independent Monitor-before-Task permits, role/input/cross-slot failures, close-before-send, the installed Harbor hook and single-step order, workspace manifest mismatch (zero fake evaluator calls), a separate Debian nonbenchmark container with a delayed writer killed by stop/start, and all five private offline profile bundles with gateway-only overlay. These scripted observations do not demonstrate model adoption or scientific effect.

The `OFFLINE_FIRST_SEND_*`, `OFFLINE_PRE_VERIFICATION_CAPTURE.json`, `OFFLINE_PRE_VERIFICATION_APP.tar` and `OFFLINE_VERIFICATION_RELEASE.json` files are byte-preserving copies of this offline test's generated receipts/archive, not hand-authored examples. The sample tar is 2,560 bytes and has SHA-256 `d8fb7464f40de3b6ad92c595783d836985b82e9b48b77afce9b7f462f34ee77c`.

The synthetic Docker regression creates and removes only its own uniquely named nonbenchmark container. The production capture does not rely on a sleep, parent PID or two equal hashes. It assumes the dynamically inspected task container has the frozen `sh -c 'sleep infinity'` keepalive and no external `/app` bind; otherwise it fails before inference. It archives symlink targets, not bytes outside `/app` reached by following those links. `code_run` remains the existing broad local execution tool, not an OS sandbox. A transport error after connection but before a confirmed `request_sent` is recorded as `unknown_after_connection`, not `not_started`.

The currently usable Docker engine was `29.6.1 linux`; the pre-existing Kitex image resolved to `sha256:7ffcd70e49d77031b8e67eaa99226dc8468fa046f33e615118e8922b89fff32e` (`amd64`). No benchmark container, live inference gateway, task agent or official evaluator was launched.

The following remain unobserved until separately authorized deployment: actual per-slot provider service identity, Task/Monitor token buckets, final evaluator result, and whether the exact trial's root/proposal/control receipt binds to the terminal workspace. The bridge provides the deterministic capture and release receipts needed for that later binding; it does not assign semantic validity or `false_allow`.
