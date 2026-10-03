# B01 generated bundle byte reconciliation

The prior two RP attempts ended before a Harbor trial or model request. Read-only comparison of the second generated bundle and its frozen staged counterpart found 274 files on each side and exactly one differing relative path: `isolated_transport.py`. Its frozen staged SHA-256 is `4923dba1a7ecfe44452bd21de25cd8eade53e73f59fae836fabf8290d68e9077` (CRLF, 10,928 bytes); the current checkout SHA-256 is `0b7c4e010e01339e8e0853061f48f8f1fe9e4c382588d3058d3a0613d5a46e98` (LF, 10,680 bytes). LF-normalized contents match. All five staged bundles have the same frozen transport-file hash.

Replacing only that file's bytes in a virtual digest of the preserved failed bundle yields the exact preregistered RP snapshot SHA-256 `207a92d16990b510e97f38c6d540ec80f7425e4cc6bb9d6bfea121b2d8d47823`. The research-side adapter performs this substitution only after the original bundle builder, recalculates its deterministic snapshot identity, and then calls the original bridge identity gate. Any other source difference still fails.

Offline command: `python -m pytest method_discovery/test_uc_r5_b01_bundle_entry.py -q`. Final result: `4 passed in 0.30s`. An unrelated pytest temporary-directory cleanup warning appeared after the passing summary. No model, Task Agent, Harbor trial, native verifier, or independent probe was invoked by this check.
