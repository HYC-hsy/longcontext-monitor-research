# R/P candidate prototypes — preparation only

Status: offline preparation; no model calls, task runs, benchmark, verifier, or
production changes.

Anchor: M1/DCEC-v1 `746a695adac4325d6440941d384d543d1364fef9`.

This directory contains two independent, request-level candidate overlays:

* R changes only how current grounds are phrased in the existing
  `working.md`-based loop.
* P changes only the optional bounded comparison of at most two short ordinary
  observation paths. It does not add a selector, tool, agent, stage, or fixed
  extra call.

`R_OVERLAY.md` and `P_OVERLAY.md` are research-facing explanations. The
model-visible policy bodies are the neutral `R_POLICY.txt` and `P_POLICY.txt`.

The request builder uses a synthetic public task/state/history fixture. It is
not a scientific record and contains no expected answer, verifier output,
condition label, or historical candidate setting. `build_requests.py` performs
pure construction and assertions; it never imports a provider client.

`real_request_harness.py` is the separate no-network integration check. It uses
the production MonitorAgent/provider assembly and captures full provider-ready
payloads with a fake transport; `offline_checks.py` runs the adversarial diff
checks and fresh M1/R/P sessions.

E is not implemented here. Its preparation note is limited to E0/E1 capability
distinction in `E_CAPABILITY_NOTE.md`.
