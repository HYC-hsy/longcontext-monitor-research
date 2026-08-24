# M0 H1 install-windows-3.11 truncated run

Date: 2026-08-24

## Scope and protocol

- Task: `tb2:install-windows-3.11`
- Purpose: third cross-task M0 confirmation on a non-code, system-administration task.
- Task agent: `claude-opus-4-6`
- Monitor: `gpt-5.6-sol`, `high`
- Intended limits: 500 turns and 120 minutes.
- Online evidence: public task, Agent trajectory/actions, tool results, workspace reads and persistent monitor state only.
- Native verifier was executed only after the Agent and monitor stopped.

This run is **not a valid 120-minute confirmation run**. The adapter received a 7,200-second timeout, but Harbor's outer agent phase retained its 3,600-second timeout and terminated the Agent at exactly 60 minutes.

## Preflight and launch history

- Terminal-Bench checkout, task tree, frozen image and patched Harbor state passed the existing identity checks.
- GenericAgent source SHA-256 was pinned as `bd15829b36edb871a22bfb2b06c6ab54d93d8fea4979514895f7dc994b0a62ec`.
- An earlier `v1` launch used the invalid condition name `m0_h1`; GenericAgent rejected it before any task/model trajectory. It is retained only as an engineering failure artifact and supplies no method evidence.
- The corrected `v2` launch used baseline condition `original` and condition ID `m0-h1-install-windows-v2`.

## Outcome

- Harbor result: `AgentTimeoutError: Agent execution timed out after 3600.0 seconds`.
- Total trial wall time: approximately 62 minutes, including post-timeout verifier execution.
- Native verifier reward: `0.0`.
- Native tests: 2 passed, 2 failed.
  - Passed: network status; Windows 3.11 core-file verification.
  - Failed: QEMU running with the expected parameters; Windows-key visual feedback.
- The verifier observed no tested key causing the required 10% image change.

Because the run was involuntarily truncated, reward 0 is a factual outcome of this execution but cannot establish that H1 would fail under the approved 120-minute protocol.

## Task progress before truncation

The Agent completed substantial infrastructure work:

1. Installed and configured QEMU 8.2.2, nginx, noVNC and websockify.
2. Launched QEMU with the required image, snapshot mode, VNC display and monitor/QMP sockets.
3. Repaired an nginx configuration conflict that initially caused HTTP 502 responses; `/` and `/vnc.html` subsequently returned HTTP 200.
4. Obtained an HTTP 101 upgrade on the `/websockify` path and an initial RFB server handshake through the route-faithful path.
5. Confirmed the supplied disk image was non-empty and contained a bootable MBR, FAT16 filesystem, `MSDOS5.0` OEM marker and substantial data.
6. Reached a persistent blue 720x400 display in one controlled relaunch. A QMP Enter action then changed the display to 1024x768 black, showing that programmatic input affected the guest-visible display, but a Windows desktop was never established.

The remaining task failure was therefore not simply “the service never started.” The web/control stack became partly functional, while guest boot/display state and end-to-end keyboard-visible behavior remained unresolved.

## Monitor behavior

- Decision files: 57.
- Recovered actions: 48 `SILENT`, 9 `HOLD`.
- Invalid JSON decision archives: 6 (`0023`, `0026`, `0035`, `0036`, `0039`, `0054`). This repeats the cross-task monitor-archive encoding defect and must be treated as an engineering issue, not a method result.

High-value H1 behavior included:

1. Rejecting premature completion when service existence was being substituted for a visible, controllable Windows desktop.
2. Detecting that the first nginx configuration proxied port 80 to an absent service and directing a focused repair.
3. Distinguishing QEMU command acceptance from evidence that the guest actually reacted to the key input.
4. Rejecting a self-authored verifier that bypassed the required nginx/noVNC route and used a weak color heuristic.
5. Preventing speculative image replacement after a failed shell pipeline was incorrectly interpreted as proof that the image was empty.
6. Allowing controlled, reversible display/boot experiments once the disk image's basic validity had been established.

Observed limitations included:

1. H1 did not lead the task to a supported Windows desktop within the available 60 minutes.
2. The repair episode remained long and accumulated many environment hypotheses.
3. No `RELEASE` decision occurred before the forced timeout.
4. Six decision archives are unparsable JSON.

## Research interpretation

This truncated run is useful behavioral evidence but not a pass/fail verdict on M0.

It supports the value of persistent supervision in a domain where many plausible proxy signals exist: HTTP 200, QEMU process existence, monitor command acceptance, an RFB handshake and a nonblank image can all be true without satisfying the root contract. H1 repeatedly preserved that distinction.

It also exposes a limitation consistent with the SymPy run: once several plausible causal hypotheses accumulate, the monitor needs a better way to select the next discriminating, reversible experiment rather than merely preserve all unresolved facts. This is compatible with the candidate `decision-centered epistemic control` idea, but the current run does not validate that mechanism.

## Engineering changes used for this run

- `long_context_bench/scripts/run_harbor_tb2_m4.py`
  - Allowed the expected GenericAgent source hash to be supplied explicitly.
  - Forwarded M0 monitor configuration to the Harbor adapter when enabled.
- `long_context_bench/scripts/run_harbor_tb2_m5.py`
  - Allowed an isolated work root for this confirmation run.
  - Allowed the adapter-level timeout to exceed the task's native timeout.

Both scripts compiled successfully. The second change was insufficient because it did not also override Harbor's outer agent-phase timeout.

## Artifacts

- Failed pre-start run: `long_context_bench/output/m0_h1_cross_task_install_windows_v1_120m`
- Truncated task run: `long_context_bench/output/m0_h1_cross_task_install_windows_v2_120m`
- Trial: `jobs/m5-ga-install-windows-3.11-r1/install-windows-3.11__4G9XbTa`
- Harbor result: `jobs/m5-ga-install-windows-3.11-r1/install-windows-3.11__4G9XbTa/result.json`
- Native verifier: `jobs/m5-ga-install-windows-3.11-r1/install-windows-3.11__4G9XbTa/verifier`
- Monitor decisions and state: `jobs/m5-ga-install-windows-3.11-r1/install-windows-3.11__4G9XbTa/agent/m0_monitor`
- Raw OTel trace: `runs/m5-ga-install-windows-3.11-r1/raw_trace.jsonl`

## Stage gate

- [x] Third cross-domain real task selected and preflighted.
- [x] H1 ran without an online checker and produced auditable behavioral evidence.
- [x] Native verifier executed only after Agent termination.
- [x] Infrastructure timeout error and method observations were separated.
- [ ] Approved 120-minute protocol was not executed.
- [ ] Third-task M0 confirmation is therefore not complete.
- [ ] Harbor outer timeout must be corrected and verified before any rerun.

## Recommended next step

Do not modify H1 based on this truncated execution. First make the smallest runner-only correction that sets both the adapter timeout and Harbor outer agent timeout to 7,200 seconds, verify the generated trial configuration before launch, and then rerun the same task as `v3`. This requires user confirmation under the stage gate.
