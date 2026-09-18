# Autonomous selection plus C experiment (pre-run, 2026-09-19)

This is the next diagnostic after the frozen C cursor repair. It is not wired
into the online Monitor Agent and has not used a real model call yet.

## Conditions

- **Direct C:** one independent C verifier receives the case question and the
  complete fixed material union.
- **Autonomous selection + C:** a parent Supervisor receives the same question
  and material union, selects one concise decision-relevant local question,
  an independent C verifier investigates that question, and the same parent
  session makes the final scoped decision from the C result.
- Both conditions use the same original task, turn-60 public event prefix,
  materialized workspace, permissions, and total six logical provider calls.
  Selection, child verification, and final parent decision all consume the
  autonomous condition's six-call budget. The final parent decision has a
  reserved call and an unfinished result is not scored as correct.
- The model never sees evaluator labels or scoring rationales. No function or
  defect is named in the autonomous prompt; both conditions can inspect the
  same union of task, events, build observation, and workspace files.

The pilot uses four confirmed-label checkpoints: App Metadata (support), JSON
Theme API (contradiction), build-only behavior (insufficient evidence), and
post-correction validator (support). The two disputed-label checkpoints are
not included. C remains the local verification mechanism; D is not used.

## Required evaluation

Record whether the parent selected a decision-relevant question, whether C
obtained discriminating evidence, and whether the final parent decision is
correct. Independently audit the conclusion for unsupported claims. A budget
exhaustion or incomplete parent/child chain is recorded as incomplete, never
as a cautious correct result.
