# Independent audit disposition (addendum; original records unchanged)

**EXECUTION-DEVIATED / PROVENANCE-LIMITED — P EFFECT NOT ESTABLISHED.**

Kitex M1: 3/6, reward 0.6. Kitex M1+P: 1/6, reward 0.3.
Both Ratatui records: 0/6, reward 0; all six phases were stopped by the
offline absence of `unicode-segmentation v1.12.0`, not six demonstrated
behavioral failures. Both P records reached the actual 180-response Task
ceiling rather than the authorized 300. Runner `valid=true` is not a
scientific validity determination. The first three Supervisor archives
remain missing; Task telemetry cannot substitute for them. The fourth
record's recovered originals and first recovery evaluation remain distinct
from normal runner archival. No records are rerun or rescored here.

## Fourth record: retained positive and negative evidence

All paths below are relative to this directory:

- `ratatui-m1/recovery/monitor/monitor_private/delivery_feedback.jsonl`:
  three delivered corrections (cursors 83, 143, 189); the latter two return
  `completion-1` and `completion-2`. Last row allows `completion-3`.
- `ratatui-m1/recovery/monitor/monitor_private/audit/dialogue.jsonl`, original
  lines 442–460, review `e1d41eca774b473eb78daf44ca28dc94`: complete
  `src/prelude.rs` read, receipt consumption, limited Color-parser grep and
  subsequent completion approval.
- `ratatui-m1/recovery/monitor/task_evidence/original_task.txt`: public Target
  5 is the comparison authority for required exports, including `Styled`
  and `Masked`; these are absent from the complete observed prelude.
- The same dialogue records a `grep -A 5` result containing only the start
  of the Color parser, later described as verification of normalization.
- `ratatui-m1/recovery/monitor/monitor_private/audit/reviews.jsonl`,
  its sibling `progress.jsonl` and `provider_history.json`,
  `ratatui-m1/recovery/monitor/monitor_private/working.md`, and
  `ratatui-m1/recovery/monitor/runtime_receipts.jsonl` preserve the broader
  control and current-state chain. Existing `file_manifest.json` preserves
  original archive hashes.

The three corrections establish local intervention capability. The final
approval also provides a public-evidence M1 premature-closure counterexample:
many exports and a partial parser observation were promoted beyond what
they established. This does not depend on verifier zero scores, is not a
P failure, and does not isolate observation selection as the only cause.
No special rule or mechanism change follows from this addendum.

M1 remains provisional; D1 remains closed without C1 verdict; D2 remains
deferred; P has no promotion basis.
