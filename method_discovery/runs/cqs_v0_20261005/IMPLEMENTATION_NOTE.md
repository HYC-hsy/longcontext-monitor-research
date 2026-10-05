# CQS-v0 implementation note (zero-model)

Parent mechanism: frozen DCM-v0 `dd4c180d4adf82ea8cc4229787e4af3fe8b7b645` via its research-only archive descendant. GCH-v0 is not implemented; RSH-v0 is not included.

When enabled, CQS replaces only the automatically injected DCEC working view in ordinary provider requests. `monitor/working.md` remains available through the seven ordinary tools, and existing continuation/compaction remains unchanged. CFS Situation is still assembled and injected as before. The system prompt, tool definitions, wake cadence, DCM release transition, root handoff, completion, and Task behavior are unchanged. The disabled path calls the previous DCEC working-view assembly.

The active CQS state is one action-derived continuity item, not a target or requirement ledger. A successfully submitted intervention records the actual message and the nearest prior nonempty natural model output. A review ending in follow records its optional reason and prior natural output. A review ending in patrol clears the active item. The first DCM release challenge does not change it. State updates occur only after the corresponding executed boundary; failed or stale tools and review exhaustion do not update it. The same state enters root; no root-specific CQS prompt exists. Audit locators refer to `monitor/audit/dialogue.jsonl` and the visible surface is capped at 1400 characters.

The callback recording `cqs_surface_emitted` runs after a provider response succeeds. The state itself is independent of working-note rewrites and History compaction. This is a mechanical continuity cue, not evidence that the correction succeeded or that any part of the task is complete.

## Offline check

Command:

```text
$env:PYTHONPATH='GenericAgent-main'; python -m pytest -q GenericAgent-main/tests/test_cqs_v0.py GenericAgent-main/tests/test_dcm_v0.py GenericAgent-main/tests/test_cfs_v0.py
```

Raw result: `26 passed in 2.49s`, exit code 0. A pre-existing Windows pytest atexit warning reported access denied for an unrelated older temp directory after success. No network provider was used.

Deterministic replay command:

```text
$env:PYTHONPATH='GenericAgent-main'; python -m method_discovery.diagnostics.cqs_v0_replay
```

Replay reads only archived DCM Fyne and Kitex `dialogue.jsonl`; it writes `CQS_REPLAY.json`. It does not infer a concern category, adequacy, or completion. Both selected archived trajectories used repeated follow and interventions but had no executed patrol-clear; the patrol-clear transition is covered by the zero-model live-loop test. Replay surfaces show what an action-derived CQS would have put in the following review, not a model response to it.

Known limits: an omitted follow reason and empty preceding natural output can leave an active but text-sparse continuity state; CQS does not semantically recover the earlier intervention in that case. It does not judge delivery, uptake, correction quality, or the appropriateness of release. Persistent History may still contain older task-status notes; CQS removes only the privileged automatic working-view injection.

Real Task Agent, Supervisor, native verifier, independent probe, and scientific record calls: 0.
