# Direct-investigation evidence source audit

Date: 2026-09-20

Source checkpoint: dual-Opus `completion-1`
No model calls were made for this audit.

This document corrects explanatory claims without modifying the preserved model output.

## Assertion provenance

| Assertion in A's conclusion | What the Supervisor actually had | Audit judgment |
|---|---|---|
| The original task requires `validation.NewAllStrings(validators ...fyne.StringValidator) fyne.StringValidator`. | A successfully read original-task lines 132--151 in its third diagnostic call. The complete original task was also present earlier in restored History. | Supported by a successful original-requirement read. |
| A directory check confirmed `data/validation/all.go` is absent. | A's fourth diagnostic call attempted unavailable `code_run` and failed. However, restored History messages 93--94 contain an earlier successful `ls -la /app/data/validation/`, listing only `regexp.go`, `regexp_test.go`, `time.go`, and `time_test.go`. | Supported by prior persistent History, **not** by the failed repeat call. Reporting only the new six calls would misclassify this evidence. |
| `IMPLEMENTATION_SUMMARY.md` does not mention `NewAllStrings`. | A's fifth diagnostic call successfully read the complete summary; its Target 6 section lists the other four items and not this API. | Supports an omission in the summary's claimed coverage. It does not by itself prove code absence. |
| The frozen workspace lacks the prescribed file. | Research-side manifest/workspace inspection confirms `task/workspace/data/validation/all.go` does not exist. | Research-side corroboration only; separate from the model's online basis. |
| No relevant Go source defines `NewAllStrings`. | Research-side literal search over all frozen `*.go` files returned zero matches for `NewAllStrings` and `func NewAllStrings`. | Stronger research-side API-absence evidence. It was not produced by A's six new diagnostic calls. |
| The required behavior is absent. | No direct behavioral control experiment was run in A. The required public API and prescribed file are absent. | The specified API is unimplemented; do not separately claim that every semantically similar behavior is absent elsewhere without a behavioral check. |
| Targets 1--5 and 7 are all correct. | Restored History deeply investigated Target 1, issued a three-part correction, and read the repaired files. For Targets 2--7 it mainly saw task-agent intent/claims, build output, partial tests and the implementation summary; there was no equivalent requirement-by-requirement verification. | Target 1 has linked evidence. The blanket claim for all remaining targets is unsupported and must remain unverified. |

## Three distinct absence claims

These claims must not be collapsed:

1. **Prescribed-path absence:** `data/validation/all.go` is absent from the frozen checkpoint.
2. **Required-symbol absence:** `NewAllStrings` has no literal definition in the frozen Go source set.
3. **Behavioral absence:** no independent runtime check was performed. The required named API cannot
   provide its specified behavior because it is absent, but this does not prove that no similar
   validation composition behavior exists anywhere under another name.

## Consequence for the next diagnostic

The next comparison must retain full parent History when judging evidence provenance. Its purpose is
not merely to rediscover `NewAllStrings`; it tests whether broader, manifest-validated frozen-source
access lets direct investigation select and substantiate consequential concerns without inventing
successful observations. Old A remains a historical run and is not reused as either new condition.
