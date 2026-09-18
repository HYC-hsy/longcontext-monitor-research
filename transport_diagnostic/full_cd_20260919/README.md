# Full frozen C/D checkpoint run (2026-09-19)

This archive contains all available C/D results from the frozen checkpoint
configuration. The configuration defines 11 questions; two disputed-label
questions (`toolbar_concrete_types` and `desktop_app_interface`) are excluded
by the runner, so 9 questions × 2 groups = 18 result groups are present.

Every group includes only `result.json`, `transport.jsonl`, and the redacted
`transport_config.json`; private workspaces and response bodies are omitted.
The root-completion groups exhausted their six logical-call budget and remain
unscored. They are not counted as correct. The build-only groups completed as
explicit unresolved judgments, which is the expected evidence-insufficient
outcome. All 62 provider attempts received response headers and completed
transport logging; no network-layer failure occurred in this run.

Aggregate accounting: C used 211,374 recorded tokens and 23 logical calls;
D used 268,310 recorded tokens and 39 logical calls. Among the 16 completed
groups, outcomes were 6 `supported_in_scope`, 8 `contradicted`, and 2
`unresolved`; the two budget-exhausted root-completion groups are separate.
