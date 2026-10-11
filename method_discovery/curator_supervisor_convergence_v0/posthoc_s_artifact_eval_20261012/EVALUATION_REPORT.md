# Post-hoc evaluation of two fixed S artifacts

This is not a continuation of either original agent run. Original archive commit:
`ea3261b7a1ef8426e744bb2351404183861f0d8b`; original execution code:
`155d30e12e261417f9fa14a86689850221b40056`. The source archive was not edited.

The evaluator was invoked exactly once for Kitex S, then once for Fyne S.
No Task Agent, Supervisor, provider, training, or scoring-model request was made.
The native test inputs were staged only after the artifact was placed in a
disposable Docker volume. The evaluator container had network disabled and no
model credentials or Docker socket mount. The pinned task image, task.toml,
test.sh, and tests-tree identities are in each `preflight.json`.

| Artifact | Input status | Native return code | Raw reward | Native phases |
|---|---|---:|---:|---:|
| Kitex S | `legal_agent_end=false`, monitor review incomplete | 0 | 0.4 | 2/6 |
| Fyne S | best-effort, non-atomic failure filesystem copy | 0 | 0.7272727272727273 | 5/7 |

`reward.json`, `reward.txt`, and full `test-stdout.txt` are the unedited native
outputs. `docker_commands_and_results.json` records each command, raw stdout,
stderr, and return code. Both disposable evaluator containers and volumes were
positively absent after cleanup. The original four-arm records remain failed /
unevaluated; these post-hoc outputs are not substituted for native scores in
that batch.

Kitex input: compressed SHA
`05a805653dc448228f82afd1c81eaff7a2b39d0f017761189c1c7d9d5906bb4a`;
uncompressed tar SHA
`5cefacd222d91056b316e06151566a6574e703f316978e370a8a2a48af78e3b4`.
Its `agent_end_frozen.json` states `writers_stopped=true`, `sidecar_clean=true`,
and `legal_agent_end=false`. The input tar contained 828 regular files and 182
directories; no links or special files.

Fyne input: compressed SHA
`5738bf9e45d11c73b06626a3f64cf0e3013b81f510c1ddb571cab1fa6b70ab55`;
uncompressed tar SHA
`568a6464c6fdcfc34884beaa06c5b500b422afb0874f2ecfe4b866ab23495eee`.
The original `failure_workspace/report.json` says capture began at epoch
`1791696989.5692542`, ended at `1791696995.7901752`, and labels consistency
`best_effort_filesystem_copy_not_atomic`. The archive has 2503 regular files
and 297 directories; no links or special files. The final public Task event is
turn 156, followed by completion review `ERROR_FAIL_CLOSED`. The archive does
not provide per-file atomic version evidence for the capture interval. A
one-to-one match of each key file to its last write/read is therefore unknown;
the tar is certified as these exact bytes, not as one historical atomic state.

Pre-evaluator setup note: an initial Kitex preflight stopped before evaluator
launch because the new script contained a one-character typo in the expected
tests-tree SHA. The actual tree SHA matched the frozen manifest, the constant
was corrected, and preflight was rerun in a fresh output directory. This was
not a second evaluator invocation. `kitex_s/preflight.json` preserves the
failed preflight observation.

All tar members were scanned before extraction. Absolute paths, parent
traversal, backslashes, links and special files were rejected. The evaluator
used `/tests/test.sh` with stdout redirected to `/logs/verifier/test-stdout.txt`
and the frozen 1800-second limit. It did not edit the original tar or source
archive. `input.tar` is a disposable decompression of the archived gzip and is
not duplicated in this commit; the input SHA and source locator identify it.
