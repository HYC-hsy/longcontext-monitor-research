# Batch gate preflight and overnight handoff verification

Parent source 6c85bc073fa382f1aac7326d1f0bf2e756fcd299. Python 3.12.14.
295/295 tests passed, PMA279 + native16; zero errors/failures/skips.
Batch initial verify_live_spec now receives both frozen citation_review_gate and already-validated zero_model_fixture_only.
Three new tests exercise the actual validator for both fake modes, require real certificates for real mode, and reject inconsistent fake flags.
No validator API or assertion was weakened. The original292 tests are unchanged.
No new model calls, Task starts, Docker lifecycle or native evaluator execution.

The overnight document's Python prepare/authorization and post-run guard snippets compile and were exercised in isolated temporary files.
Only external asset preparation/certificate IO was mocked in that helper check; real validate_plan and gate source hash checks ran.
Post-run guard accepts reward0 and rejects missing cleanup/native evidence. This is not a real execution approval or native certification result.
An initial helper-check shell omitted the repository from PYTHONPATH and failed at import before any action; the recorded successful rerun sets PYTHONPATH=.:/tmp/auditor-offline-deps.
The developer receives bounded authority for the four listed real slots, not this implementation process.
