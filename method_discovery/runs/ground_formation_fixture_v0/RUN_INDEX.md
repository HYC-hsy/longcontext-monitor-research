# Ground Formation Fixture v0 — raw run index

Implementation candidate: `290d317d8d78e0003607617433057a8bc8555f8c` (sole parent `80b8374674293f0853d68b9704d0fa5d14fa7840`). Three distinct Supervisor-only initialization reviews were run once each. There was no Task Agent, transition, native verifier, or continuation experiment. The `claude_monitor_opus48` profile used `claude-opus-4-8` with DCEC, semantic continuity, a 4000-character working view, 20 review turns, and no independent child.

| Archive | Run ID | Task SHA-256 | Initial workspace manifest SHA-256 | Requests | Tools (`file_read`, `code_run`, `file_write`, `wait`) | Working writes / max chars | Checkpoint | Duration |
|---|---|---|---:|---:|---|---:|---|---:|
| `case_a/` | `gff-v0-20261002-01` | `f9d0387c655ae7f0037464fa336deed9bcc50b6ed15c8fb2cfcc338a9713bb2f` | `8f823169f4fa7308fd36e8e6026c6f82bbca9ec35c33c1f3845110c58f703bc2` | 10 | 6, 3, 2, 1 | 2 / 1314 | verified complete | 96.5 s |
| `case_b/` | `gff-v0-20261002-02` | `f9d0387c655ae7f0037464fa336deed9bcc50b6ed15c8fb2cfcc338a9713bb2f` | `ae14ad1a1e9a0246cad6da1b0d71e080395419ea88ba275498cc24bf1c8947c4` | 7 | 7, 3, 1, 1 | 1 / 780 | verified complete | 75.0 s |
| `case_c/` | `gff-v0-20261002-03` | `e1faace08e0523d16128fac910a2aa50a948f4391b82652e1bbcbc3bb02bc774` | `2bf7665fe634167abb5f57477bfe03355c6404e758b4949d651b024b80c54621` | 7 | 5, 1, 2, 1 | 2 / 867 | verified complete | 69.3 s |

All three checkpoint artifacts pass `verify_checkpoint()` and bind the complete workspace snapshot, provider History prefix, working bytes, contract/model identities, and idle review boundary. Every review ended with `wait`; no control delivery remained in flight. The captured ground's semantic adequacy has **not** been classified.

Raw per-case materials: `original_task.txt`, `initial_workspace/`, `effective_config.json` (without API key), `monitor/task_evidence/`, `monitor/monitor_private/audit/` (complete dialogue, history, usage, attempts, progress, reviews, workspace samples), `monitor/runtime_receipts.jsonl`, `checkpoints/seed-<run-id>/`, `run_facts.json`, and `contamination_audit.json`. The profile secret itself was not copied; archive scanning found no literal API key or credential field.

## Input-boundary limitation

The first-pass scripted audit reported no explicit case label, expected answer, future patch, or transition instruction in model input. A separate exact wake-context inspection found the host path `E:\lc_seed_sessions_20261002\s01` (respectively `s02`, `s03`) in the task original-path and live environment map. The token `seed_sessions` discloses the research purpose of the host directory. Thus the strict “no fixture metadata in model input” condition is **not fully met**, even though no case-specific expected outcome was exposed. Treat these as preserved engineering records with valid checkpoints, not clean uncontaminated experimental seeds. No case was rerun or modified after seeing model behavior.

No fixed observer headings (`Contrast:`, `Measurement:`, `Basis:`, `Reach:`, `Anchor:`, `Transport:`) occur in the final working notes. The full model-visible system/tool/continuation identities are the same across the three records: system `ea66387df31eaa84ae1e55b2b17923d87e2bd54bc34b706a5bc95699fd41e2e6`, tools `4e6664176e776fd179e0482ba4038eeb81ead028948d68696de7f3751535b9ab`, continuation `a662f08f7a645b9d3361a2181f808cfae188c03913b194ccc4bb54d62fc32861`, and redacted effective model config `71d94a8568646d508b95545f87d155c51e2a9cfd6156f5fcdc35f5721834f61d`.
