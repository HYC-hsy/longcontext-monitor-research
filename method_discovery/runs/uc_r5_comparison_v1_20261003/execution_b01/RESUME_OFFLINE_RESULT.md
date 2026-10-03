# B01 recovery: local verification boundary

- Command: `python -m pytest method_discovery/test_uc_r5_b01_resume.py -q`
- Final result: `8 passed in 0.10s`; no model, Task Agent, Harbor trial, verifier, or probe was invoked.
- An unrelated pytest temporary-directory cleanup `PermissionError` appeared in an `atexit` callback after the passed summary. No test failed.
- Fake-credential coverage: only the `monitor` route's existing `Authorization` value changes; the Task route and all other gateway JSON bytes remain equal. Missing route, wrong header, identical replacement, extra header, and absent private source fail closed. The original bundle builder completes its checks before replacement; the replacement receipt is emitted before that builder returns to the runner.
- Actual account-side revocation and replacement have **not** been verified. `UC_R5_B01_PRIVATE_CREDENTIALS` is unset; no private rotated-credential file was found or created. Scientific execution is blocked before Harbor. The operator must use the existing private account channel, not chat text, to revoke the exposed Monitor credential and provision a replacement with a private revocation attestation.
- The Task route uses a different existing authentication value. The five private Monitor profiles use the same exposed value. No credential value is included here or in the public authorization.
