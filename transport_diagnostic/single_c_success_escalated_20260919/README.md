# Single C transport diagnostic (2026-09-19)

This directory contains one complete `app_metadata_defaults / C_isolated_direct`
probe run. It was run with the unchanged C prompt, model, and retry settings.

- `result.json`: redacted probe result and request counters.
- `transport.jsonl`: append-only, flushed provider lifecycle events; response
  bodies and credentials are not recorded.
- `transport_config.json`: redacted timeout/retry/model configuration.

The non-elevated attempt is archived separately. It failed before response
headers with a sandbox `PermissionError` in the connection retry chain. This
elevated run received HTTP 200 headers and completed both streamed requests;
therefore the earlier failure is classified as an execution-environment
permission failure, not a C/D judgment result.
