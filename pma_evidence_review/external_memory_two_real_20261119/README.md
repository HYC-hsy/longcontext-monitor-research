# External-memory version: two full tasks

Execution commit: `1a8a18c9d524f4ac98992dda1494ac53f3d402f1`; direct parent: `c7bb1941222955980539d5290511242dd1800c39`. Production change is confined to manager system-prompt text; its loaded base system SHA-256 is `b8d9015cb70d4566501a8cb48034fb15c990a21a3f4172a889e7b509f1bc382d`.

Task profile SHA-256: `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`; manager profile SHA-256: `42ce7b4bd30a41c612ddefd9249e6bfb33ecb9ff2b989d8cf72a281735b7d39e`. These match the preceding c7bb194 runs. Dataset `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. Task policy is uncapped with official native verifier timeouts and manager wake interval four.

Targeted prompt/artifact-capture tests: 10 passed. Tool-flow/read integration and runner tests: 86 passed after including the actual runtime package directory in the test import path. The initial 81-pass/5-fail test invocation is retained separately as an environment setup diagnostic. The first RStan preparation failed because Docker Desktop was stopped; it did not start Task or manager calls. Docker was restarted, then RStan was prepared in a new directory. This failed preparation was not overwritten or counted as a real run.

Both real runs completed native evaluation and owned-resource cleanup. RStan: `pma-225bffec60684dbf`, 4/6 native tests, reward 0. ARC: `pma-9c3b8797d1724bfb`, 5/5, reward 1. All six final Task artifact identities matched before and after verifier execution. All 53 observed manager outbound requests carried temperature 1; no observed non-200 or local retry.

The ZIP is a redacted visible projection, not raw HTTP bytes. Private originals remain local. Raw CTRF and native test stdout are not published because they may include hidden test material; their local absolute paths, byte counts and SHA-256 values are in the external index. Credentials, private profile bodies/endpoints and provider-private thinking/signatures are excluded.
