# C6 Monitor Protocol and Entry Hardening (2026-09-02)

## Scope

This stage fixes three deterministic risks found after C5: incomplete Provider tool-call closure across
Monitor wakes, message-count-based history cuts, and real-task launch paths that still selected the retired
M0 runtime. It does not change Monitor semantics or run a real task.

## Provider protocol closure

Before returning `wait`, `intervene`, or `allow_complete`, the Monitor loop now records results for every
tool call in that response:

- previously executed inspection tools receive their actual result;
- the selected control action receives an accepted receipt;
- any later calls in the same response receive an explicit not-executed receipt.

The next wake therefore starts from a valid OpenAI Responses or Anthropic Messages history rather than an
unanswered function call.

## Review-aware history compaction

Compaction no longer protects or deletes a fixed number of messages. It identifies a complete Monitor review
by an acknowledged `wait`, `intervene`, or `allow_complete` boundary. The initialization review and at least
the latest 16 messages are retained, while older history is removed only as whole closed reviews. Tests
verify that every retained function call still has its function output after compaction.

## Clean real-task entry

- GenericAgent no longer imports or constructs `AsyncMonitorRuntime`.
- `GA_M0_MONITOR_ENABLED=1` now fails explicitly instead of silently selecting historical code.
- The delayed `consume_interventions` path was removed; clean corrections use only resumable interruption.
- Harbor adapters and the ultralong runner accept explicit clean Monitor configuration through
  `GA_MONITOR_ENABLED`, `GA_MONITOR_CONFIG`, and `GA_MONITOR_EXPECTED_MODEL`.
- `method_discovery/clean_monitor_prepare_real_task_gate.py` is the canonical clean foundation manifest
  builder. Historical M3 candidate manifests remain evidence, but cannot execute through the retired path.

## Verification

- GenericAgent full suite: 333 passed.
- Ultralong, LHTB, and standard Harbor adapter suite: 88 passed.
- Monitor protocol-focused suite: 39 passed.
- A Fyne 2.2 audit manifest was generated but not executed. It contains one `clean_monitor` condition,
  `gpt-5.6-sol` high for the Monitor, no `GA_M0_*` or `GA_M3_*` keys, no online checker, and
  `prepared_not_executed` status.
- No model API, Docker task, or native verifier was run in this stage.

The next real task remains separately gated by the user.
