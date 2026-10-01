# Controlled Transition Micro Experiment Runner v0

Research orchestration only. `run_micro_case(...)` requires a **neutral** ID
(`micro-01`, `micro-02`, ...), a valid `epistemic-research-checkpoint/0`, an
exact researcher-specified transition source hash, and a separate operator-
supplied Supervisor continuation context plus explicit driver callback.
It never constructs a context, resumes a provider session, starts a Task Agent,
runs a verifier or chooses a transition. Missing prerequisites produce a
`not_started` receipt before any fixture or model callback.

The runner verifies E/X binding; runs the existing checkpoint-to-fixture-to-WTV
harness; gives the callback only its supplied context path, the changed
workspace path, the mechanical WTV view and a neutral output directory; and
archives the callback's raw input, output, tool, working-mutation and provider-
attempt files. It records model identity, calls, usage and duration from the
callback receipt. If a callback fails after it may have called a model, calls
remain **unknown**, never inferred as zero. No whole-task score is requested.

The callback is responsible for building the normal model request and for not
injecting case names, expected outcomes, fixture metadata or research notes.
The runner archives the actual input artifact so this boundary can be audited.
It records whether the exact WTV text appears in that artifact, raw tool-call
events, working mutation count/max length and field-like headings. It does not
infer whether the Supervisor understood the transition or should Carry/Reopen.

```text
micro-01/
  micro_run.json               # status and model-call count (null if unknown)
  checkpoint_identity.json     # E hashes, X manifest hash, cursor/turn
  continuation_source.json     # operator context identity and recovery claim
  mechanical_ref.json          # checkpoint/fixture/WTV artifact hashes
  experiments/mechanical-prefix/  # existing offline harness artifact
  supervisor_session_ref.json  # inside mechanical-prefix, reference only
  supervisor_continuation.json # caller-reported model/usage and raw-file hashes
  supervisor/                 # copied raw input/output/tools/working/attempts
  mechanism_facts.json         # deterministic WTV/tool/working facts only
```

`operator_claims_complete_recovery` is archived as a claim; the runner always
sets `runner_verified_complete_recovery=false`. Even a completed callback is
**not** proof of same-Supervisor continuation. No model-visible change is made
to Dynamic Observer, WTV, Checkpoint or Fixture.

The three tests use endpoint-file modification, validation-file modification
and no modification with a fake continuation callback. They make zero real
model calls and do not substitute for the three requested real observations.
See `CURRENT_MICRO_READINESS.json` for the currently missing live inputs.
