# Original information fragments: four temperature-1 runs

Execution: `c7bb1941222955980539d5290511242dd1800c39` (direct parent `607dabe70bd2569c425c6dbb7ede4e4c3ca23a89`). The commit changes only the manager's system-prompt source and its prompt tests. Loaded system SHA-256: `2249eaa55eadc9950385dd4ce8f7d9be21633716c93ac8a41f746b6df89e63b8`.

Task profile SHA-256: `ed09a811b654b83097bee77942704eae2539d67291bf55aa34476692081ff02e`. Manager profile SHA-256: `42ce7b4bd30a41c612ddefd9249e6bfb33ecb9ff2b989d8cf72a281735b7d39e`. These match the preceding new-1 four-run experiment. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`. The Task agent is uncapped, with official per-task verifier timeouts and manager wake interval four.

Targeted offline checks: 10 passed; runner frontend checks: 40 passed. One separate source-fingerprint assertion failed identically on this commit and its unmodified parent; see `offline_inherited.log`. It is not reported as a passing test.

The ZIP is a redacted visible projection, not original HTTP bytes. It includes the four visible Task/manager histories, tool calls and receipts, bank and reminder records, outbound manager HTTP metadata, native result summaries, cleanup evidence, and the final Task artifacts captured before and independently read back after native evaluation. All 12 artifact identities matched. The original `ctrf.json` and `test-stdout.txt` are retained locally and excluded from publication because they may disclose hidden test material; their local paths, sizes and SHA-256 values are listed in the external index. Credentials, private profile bodies, endpoints and provider-private thinking/signatures are excluded.
