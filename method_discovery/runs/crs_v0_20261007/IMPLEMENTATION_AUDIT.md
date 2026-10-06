# CRS-v0 implementation audit (zero-model)

Production semantic baseline: `dfec10511bdafe97e8a0041cb95d19f5bed4de9b`.
The later Fyne archive commit `d53177efdb084e0d8f7f6a3bfb7ec7d425de357d` supplies evidence only; it does not alter production bytes.

## Condition and diff boundary

`monitor_contrastive_release_state=true` requires `monitor_adaptive_supervisory_environment=true`; default is false. The candidate modifies `monitor_agent_core/agent.py` and adds `monitor_agent_core/crs_v0.py`. The ASE `SYSTEM_PROMPT`, Task Book/Reference, Control Echo, Situation, runtime feedback barrier, provider, wake, seven tool names, and non-CRS release behavior are unchanged. Only the ASE copy of the existing `allow_complete` schema acquires a required `contrast` object. No additional model or tool is installed.

## Frozen release representation

The release claim is the current root handoff as whole-task complete, derived from its `request_id`, `generation`, and public `cursor`. It is not model-authored. `contrast` has exactly five fields: `alternative` (1–1200 chars), `grounding` (1–1200), `ground_refs` (1–4 distinct locators), `discrimination` (1–1600), `observation_refs` (1–4 distinct locators). Each locator is at most 200 chars. No status, confidence, score, coverage, or per-requirement ledger is accepted.

Ground locators: `task/original_task.txt`, `monitor/reference.md`, or an existing `task/public_events.jsonl#cursor` whose archived sequence equals the cursor. Observation locators: an existing public event at that form with nonempty actual `tool_results`, or a `monitor/audit/dialogue.jsonl#line` identifying a `tool_result` paired with an earlier same-review `file_read`/`code_run` call and tool ID. Validation checks source presence and event/receipt shape, not whether grounding is correct, measurement is adequate, or an alternative is excluded. The returned audit provenance contains available path/range/SHA or code session/status/exit/error/cancel metadata without changing a running, cancelled, or failed status into a pass.

The contrast is canonical JSON with sorted keys and compact separators, hashed with SHA-256. First valid root proposal stores it in review-local memory and returns `release_not_executed`. It is appended to the next provider-ready ASE active context as the Supervisor's fallible cognition, with an injection receipt. Only a later model turn repeating that exact representation for the same handoff may release. A revision replaces it and must itself be exposed in a later model request. Two calls in one response cannot confirm. No new observation is required after the boundary. Root intervention, stale handoff, review end, exhaustion, and exception abandon pending CRS; no CRS is written into Task Book or Echo.

Audit events: `crs_release_attempted`, `crs_proposed`, `crs_surface_prepared`, `crs_surface_injected`, `crs_revised`, `crs_confirmed`, `crs_abandoned`. They contain handoff identity, hash, locator and available mechanical lifecycle metadata, not semantic verdicts.

## Test record

No Task Agent, Supervisor provider, native evaluator, or scientific trial was started. `tests/test_crs_v0.py` uses an offline patched provider response and direct deterministic tool calls. Existing Curator/ASE/DCM/runtime tests remain part of the regression set. The separate historical `test_monitor_root_contract.py` cannot collect in this local Python environment because the unrelated optional `shortuuid` package is absent; no production dependency was changed for that test. An expanded legacy `test_monitor_live_intervention.py` run has two failing old worker mocks; that test file and `runtime.py` are byte-identical to the baseline and were not repaired as part of CRS. The passing focused set excludes that legacy file; report the expanded-run failures separately, not as green.

Focused command: `python -B -m pytest -q tests/test_crs_v0.py tests/test_curator_supervisor_v0.py tests/test_ase_v0.py tests/test_dcm_v0.py tests/test_clean_monitor_runtime.py tests/test_monitor_provider.py` → 138 passed, 8 skipped. The local pytest installation emits an atexit permission warning for an older temporary directory after its exit code 0; it does not change the test result.
