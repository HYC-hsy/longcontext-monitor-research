# Manager response capture: three real task attempts

Execution commit: `22b850f32a46410f937d99350e85cff7be95bf2d`. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`. Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.

The runs were serial and each task was attempted once. RStan (`pma-a7843144b386448e`) and ARC (`pma-f3cae5d396794e5f`) each have native reward 1.0 and confirmed resource cleanup. Raman (`pma-9f5bf04ca57b485f`) reached `CURRENT_TASK_DONE`, but the native evaluator did not produce a report after an apt dependency download returned HTTP 502. Raman has no native score, not a score of zero. Its resources were cleaned; the queue stopped and did not retry.

The optional capture was enabled only in the batch process. Manager outbound attempts, responses, and complete one-to-one raw capture matches were 36/36/36 for RStan, 20/20/20 for ARC, and 20/20/20 for Raman. No missing, incomplete, duplicate, or request-error records were found. All 76 complete responses were classified `not_returned` for reasoning at this capture interface. This does not describe inaccessible service-internal processing.

The ZIP contains redacted visible Task and manager records, tool calls and receipts, knowledge banks, reminder delivery evidence, effective policy/identity, capture reconciliation, available native summaries, and cleanup evidence. It is a public projection, **not original HTTP bytes**. Raw provider responses and signatures, credentials, private profiles and endpoints, and hidden verifier bodies remain local. The adjacent index records public sizes and SHA-256 hashes plus hashes for the retained private originals where available. `RESULTS.json` and per-run `RESULT.json` describe observed status; `CAPTURE_RECONCILIATION.json` maps manager attempts to locally retained raw response hashes without publishing raw bytes.

No replay, model rerun, or retrospective response generation was performed. A native test dependency failure is reported separately from a Task failure.
