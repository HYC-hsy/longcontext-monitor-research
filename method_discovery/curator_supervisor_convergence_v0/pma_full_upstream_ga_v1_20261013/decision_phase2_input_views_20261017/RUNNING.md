# D1 archived Phase-2 input-source diagnostic

This is a host-only, Phase-2-only comparison, not a Task run. The only model
strategy is the already frozen D1 Phase-2 system, suffix and parser. Six
archived public inputs appear in fixed order: 07/235, 14/85, 14/105, 22/7,
07/161, 18/6. Each has three independent occurrences in rotations F/EB/E,
EB/E/F, E/F/EB. A plan has 54 rows; the execution loop and archive iterate the
plan rather than a fixed count. `execution_authorized=false` in all prepared
manifests; preparation never sends a model request.

F is byte-identical to the previous D1 request for the same case. EB retains
the original bank and task description plus each archived command JSON value
and the full `Terminal Output.tool_results` array. E differs only by replacing
the bank block with `Memory bank withheld in this diagnostic condition.`.
EB/E remove `Agent Analysis` and only the *outer* `Terminal Output.content`
field, the GA working-memory wrapper. No nested text is recursively decoded or
filtered: tool stdout/stderr, code comments, echoed text and mistakes remain.
The strict JSON boundary reader rejects unknown fields, missing independent
tool results or unparsed event text. The original window, step numbers and
suffix remain. Forty-three visible steps is an input-asset check, not a loop
constant. `projection_identity.json` records per-field source paths/step
positions, retained/deleted hashes, IDs and counts; `requests.jsonl` holds the
actual prompt before each send.

Run from research directory P using installed PMA Python 3.12. Set PYTHONPATH
to repo root, P, P/vendor/pma_89e5c0d/src, and
P/vendor/pma_89e5c0d/external/harbor/src. No Docker/Harbor task container is
used. The existing `decision_phase2_screen` CLI is used throughout:

```powershell
python -m decision_phase2_screen prepare --input-views --output <new-draft-directory>
python -m decision_phase2_screen fake --manifest <draft>/manifest.json --output <new-fake-directory>
python -m decision_phase2_screen freeze --input-views --manifest <new-private-manifest.json> --output <new-private-output-root> --profile <approved-private-PMA-profile>
python -m decision_phase2_screen authorize --manifest <manifest> --authorization <new-private-authorization.json> --profile <same-profile> --authorization-source <this-approval-identity>
python -m decision_phase2_screen run --manifest <manifest> --authorization <authorization> --profile <same-profile>
python -m decision_phase2_archive --run-root <private-output-root> --manifest <manifest> --public-root <new-public-root>
```

The previous 18-row schema/authorization remains separate and cannot authorize
this plan. The new one-use authorization binds the exact manifest bytes, code,
dependencies, private profile fingerprint, all rows and new output root. The
run checks these again before every request. The actual provider is the
existing vendor LiteLLM route: Anthropic/messages, Opus 4.8, adaptive/high,
max_tokens 8192, temperature 1, read_timeout 300; the original per-call retry
decorator allows up to three attempts. There is no outer retry. Deeper network
attempts not visible at the LiteLLM boundary remain unknown. The first real F
request is the compatibility observation; there is no probe.

Private source and raw provider records remain in the private output root.
`decision_phase2_archive` emits an allowlisted public projection, per-item
request/response/result/provenance files, status table, readable TXT, hashes
and ZIP; thinking or sensitive-looking content is excluded with explicit
projection notes. Review the public projection before pushing. No reminder is
delivered to Task and no Phase 1, native evaluator, training or scoring model
is invoked. Static responses do not establish Task benefit.

Reuse: project `decision_phase2_screen`, `decision_phase2_archive`,
`episode.construct_upstream`, `decision_reminder_agent`, and fixed Apache-2.0
PMA vendor are directly used. `decision_phase2_views` is new field projection
adapting their archived requests. Memory-Collapse-Eval commit
`adf347f67a81a19fc71d2529d09108c71a1f9712` (MIT code / CC BY 4.0 data)
was consulted for the structural distinction between update and consumption
and for code-enforced visibility; no code/data was copied. STALE commit
`ea7d391103a151927cd29d2f01d87597a782bdcb` was consulted for separating
recognition, resistance and behavior in later human review; no code was
copied and no judge is run here.
