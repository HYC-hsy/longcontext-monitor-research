# Five-slot run: engineering stop and later cleanup

Execution code remained `3bbe7f2df3c2190a269eaf857b8c0183a350e66f`. This is a factual post-run note, not an original runtime log or a repair of the recorded results.

The first slot, `rstan-to-pystan`, completed its Task, native evaluation and owned-resource cleanup (reward 0). In the second slot, `make-mips-interpreter`, the PMA worker stopped before verified `task_end` after an `APIConnectionError`; the final wrapper attempt recorded status code 500 after the configured eight retries. Native evaluation did not run. The following three slots were nevertheless started, each once, and failed during the initial PMA call with the same visible exception class and status code. They had zero Task provider request attempts and no native evaluation. No slot was replayed or repaired.

The serial supervisor had a local scripting defect: `Run-Slot` wrote status lines to PowerShell's success output and also returned a Boolean. The caller tested `-not (Run-Slot ...)`; a nonempty output array containing the status text made that test false even when the final Boolean was false. Thus the supervisor continued after the failed second slot and incorrectly wrote `SERIAL_COMPLETE`. The per-slot `batch_result.json`, not that line, is authoritative for each outcome. This defect did not change the fixed PMA method or Task inputs. The executed supervisor script is included in the ZIP unchanged. No five-slot rerun was authorized or performed.

At each failed slot's exit, `cleanup_confirmed=false` and its own `model-channel` volume remained; the original result remains unchanged. After the batch, Docker was available, no task/worker Python process or active task container was observed, and Docker reported no container referencing any of these four exact volumes. Their Compose project labels matched the four task-owned projects. Only those volumes were removed afterward:

- `public_task__uhgnmde__env_model-channel`
- `public_task__avwjqrx__env_model-channel`
- `public_task__xgqwur6__env_model-channel`
- `public_task__egzffks__env_model-channel`

This post-failure removal is distinct from successful in-run cleanup. The volume contents are not recoverable; the run originals, Task/PMA visible logs, retry records and result records remain local. The upstream reason for the provider's HTTP 500 response is unknown from the visible record.
