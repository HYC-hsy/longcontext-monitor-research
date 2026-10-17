# One-use archived Phase-2 comparison

This is not a Task run. It selects the six archived public `context_decision`
requests in their fixed order and invokes U, V1, D1 once for each (18 logical
Phase-2 calls). No Phase 1 or Task event loop is started. The prior
`decision_reminder_v1_20261017/screen_draft` remains unapproved and unchanged.

From the research directory `P`, use the already installed Python 3.12 PMA
environment with `P`, `P/vendor/pma_89e5c0d/src`, and
`P/vendor/pma_89e5c0d/external/harbor/src` on `PYTHONPATH`. `prepare` and `fake`
remain offline; `freeze` creates an unapproved real-input manifest only.

```powershell
python -m decision_phase2_screen prepare --output <new-offline-draft-directory>
python -m decision_phase2_screen fake --manifest <draft>/manifest.json --output <new-fake-directory>
python -m decision_phase2_screen freeze --manifest <new-private-manifest.json> --output <new-private-run-root> --profile E:\LongContext\monitor_config\models.local.json
```

Only after the reviewed code is committed, the frozen manifest/profile/code and
source checks pass, and there is an independent explicit approval for precisely
this comparison may a fresh one-use authorization be created:

```powershell
python -m decision_phase2_screen authorize --manifest <new-private-manifest.json> --authorization <new-private-authorization.json> --profile E:\LongContext\monitor_config\models.local.json --authorization-source <approval-id>
python -m decision_phase2_screen run --manifest <new-private-manifest.json> --authorization <new-private-authorization.json> --profile E:\LongContext\monitor_config\models.local.json
```

`run` always uses the loaded `claude_monitor_opus48` Anthropic/messages Opus 4.8
profile, with the original LiteLLM retry decorator (up to three attempts),
adaptive thinking, and actual `read_timeout=300` per provider call. Profile
`timeout=30` and `max_retries=8` are recorded as profile fields but are not
separate active request limits. The run records each request before sending,
each lower-boundary attempt, response, error, and immediately updated status.
It stops after a final transport or capture/identity failure. There is no
outer retry, recovery, or extra compatibility probe.

The private run root retains complete captured transport attempts. Following
run completion or safe stop, `decision_phase2_archive` creates a *new* public
allowlist projection with per-request files, a readable TXT, and a ZIP:

```powershell
python -m decision_phase2_archive --run-root <private-run-root> --manifest <private-manifest.json> --public-root <new-public-archive-root>
```

The archive does not copy the private profile, credential, private endpoint,
raw provider choices, or unknown transport logs. Visible content that contains
thinking tags or credential-like markers is separately redacted or excluded,
with the omission recorded. Never push the private run root automatically.
