# Independent Monitor Agent model configuration

Private credentials live in `models.local.json` in this directory (ignored by Git).
The file maps profile names to provider configurations. Current selected profile:
`claude_monitor_opus48`, Anthropic Messages, Opus 4.8, adaptive thinking/high,
8192 output tokens, 200000 context window. These budgets are local configuration,
not claims about upstream model limits.

The Monitor core requires an explicit file argument or `MONITOR_CONFIG_FILE`;
it does not infer paths from GA's directory layout or import mykey/llmcore.
The GA adapter resolves this project's host/container locations and passes the
path to the independent loader. Never put real credentials into committed examples.

The isolated experiment builder reads the task profile from GA and the monitor
profile from this directory separately. Real credentials remain in the external
gateway. The task container receives only redacted profiles; the monitor profile
is stored under its own package, not in the task's mykey.json. A fixed local
transport route distinguishes monitor credentials when both roles use the same
model. This is routing separation, not an access-control boundary between agents
sharing a container.

Historical GPT run manifests require explicitly provisioning their named profile
in this independent file before rerunning. There is no automatic task-key fallback.
