# Task-readable knowledge file: stopped two-slot run

Execution: `7da7b63003f14f61709e4c7100a8daf15bc9617d`. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`. Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.

The first rstan Task started once, then stopped after a manager provider disconnect. Its terminal state is unknown, native evaluation did not run, and its run cleanup was not confirmed at the stop point. The second task was not started. One orphaned run-owned model-channel volume was removed after confirming no container used it. No Task or model request was replayed.

Zero-model reads in both frozen Task images verified the empty bank, an updated bank at the same path, and task isolation. The Windows-only Unix permission-bit assertion failed (96 other targeted tests passed). The existing startup source-file identity list omits the newly added task_knowledge_file.py; its working bytes were separately checked against the fixed commit's Git blob and its actual import path.

This ZIP is a redacted visible projection, not raw HTTP bytes or a restorable runtime. Private originals and full traceback remain local. Credentials, private endpoints/profiles, provider-private thinking and hidden verifier bodies are excluded. Exact exposed knowledge-file bytes are included as a redacted projection with source/projected hashes.
