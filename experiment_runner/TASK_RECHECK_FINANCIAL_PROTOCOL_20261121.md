# Financial Task checkpoint and short-branch protocol

This is a diagnostic continuation, not a new full-task comparison. The original
run uses the fixed 22b method plus default-off observational capture. The
capture is enabled only for this one new financial run. No Task or PMA model
input is changed by the capture. The original Task receives its original
reminder and continues to its natural terminal and native evaluation.

## Frozen cut selection (before opening final result)

Inspect post-tool/pre-next-Task-request checkpoints in ascending actor step.
Take the **first** checkpoint satisfying all of the following from the
checkpoint's own files, Task-visible history, and then-current source assets:

1. A preliminary extracted monetary amount exists in a current Task output.
2. At least one amount can be mapped to a then-readable source invoice or
   independent OCR text. An independent restore clone must use GA's real Task
   tool to read both the source and output, and preserve file hashes.
3. Before this checkpoint, the Task has not visibly compared that same amount
   against its source/OCR text.
4. Another Task request is about to be sent, so the Task still has an
   opportunity to check it.

Do not inspect the original run's final score, the native verifier, or any
future Task step while selecting. Truncation is neither required nor a reason
to reject a checkpoint. If no checkpoint qualifies, report `no_eligible_cut`
and run no branches. A failed actual-source restore probe disqualifies the cut;
continue chronologically to the next checkpoint, without inventing a source.

## Frozen branch order and budget

From one selected checkpoint, run the following independent Docker clones
serially, each for at most four Task turns: `none-1`, `fixed-1`, `targeted-1`,
`targeted-2`, `fixed-2`, `none-2`. No branch receives later PMA wakes or bank
writes; none runs a native verifier. A model's natural stop, tool failure, or
four-turn truncation is retained without replacement.

The fixed reminder is: “Before continuing, review the original task alongside
the current artifacts and execution results, and check what still needs to be
done.” The targeted reminder is: “Before continuing, compare a few extracted
amounts with the corresponding source documents or OCR text.” The `none`
branch appends nothing. Both nonempty branches use the original reminder
append function and the same current-input envelope. All earlier history,
including earlier reminders, is unchanged.

The upper bound is one full original financial Task plus 24 branch Task turns;
provider HTTP attempts and total tokens/cost are unknown before execution.
The six branches have independent banks/workspaces and fresh run IDs. Original
Task continuation is not a branch and is not used as a seventh comparison.

## Reporting

Blind review tool actions before revealing arm labels. For every branch list
the received reminder, first relevant tool action and receipt, whether the
*same* output amount was checked against source/OCR, and whether that evidence
led to a correction, rerun, or evidence-backed decision to retain the result.
Promises to check, CSV-only checks, and rerunning the same extractor without
source comparison are not counted as evidence acquisition. Report unnecessary
rework and unsupported edits separately. Conclusions are limited to this cut.
