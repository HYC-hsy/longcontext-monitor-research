# Exact frozen M1 + P offline acceptance

Scope: engineering fixtures only. No scientific/model/task/verifier execution.
Anchor is `746a695adac4325d6440941d384d543d1364fef9`, not the current checkout.
The c6e2 prototype and its captures remain untouched; they demonstrated only
approximate request plumbing with DCEC disabled, not exact M1 acceptance.

## Reproduce

From repository root, choose an absent directory outside the current checkout:

```powershell
git worktree add --detach ../LongContext_m1_frozen 746a695adac4325d6440941d384d543d1364fef9
python method_discovery/diagnostics/m1_p_exact_acceptance_20260928/run_acceptance.py --source ../LongContext_m1_frozen --output-root ../m1-p-offline-receipts
```

`--source` is mandatory and commit/clean-tree identity is checked before imports.
The runner uses a fresh `python -I` child for every session. Native M1 bypasses
`experimental_adapter.py`; candidate-closed M1 traverses the adapter with no
policy; P uses exactly the c6e2 neutral P body; a fourth clean M1 session is
created after P. Default worker mode is native M1. No module is imported from
the current GenericAgent-main. All loaded local module paths/hashes are logged.
Working-tree bytes and Git blob bytes are separately hashed; only LF/CRLF
normalization is permitted for identity, and actual sources are not rewritten.

The model/provider settings come from the archived Fyne Supervisor role only.
Virtual credential and offline endpoint are test replacements. Native DCEC
and semantic-continuity configuration are enabled, working view is 4000,
review turn limit is the frozen constructor's 20. Other historical candidates
use the frozen source defaults (disabled); no verifier is created. Full
effective configuration, Python, OS, and requests version are in each trace.

## Fake boundary and real operations

Only `requests.post` is replaced with a scripted SSE response. Ordinary `_request`, `_request_once`, retry bookkeeping,
provider-ready Anthropic assembly (including route headers), production stream parser, normal review loop, dispatch, active view,
history, and continuation/compaction remain frozen production code. HTTP
Session.request and socket connect/create_connection fail closed and increment
actual attempt counters. Fake usage values are explicitly test data, not costs.
No local analysis subprocess or real task is launched by the scripted trace.

The trace reads original_task through file_read, writes working.md, consumes
receipts on later requests, waits, appends actual public-event bytes, exercises
pending wait rejection, intervenes, attempts old-proposal approval (rejected),
and approves a new request_id/generation. Native `_compact_with_continuation`
is invoked at its normal maintenance seam; no history threshold or production
budget is modified. Its no-tool request, note storage, history archival,
compaction commit and subsequent review are all captured.

## Evidence and mechanical comparison

`published_receipts_v2/` contains full raw provider-ready payloads, scripted responses,
tool/control events, in-memory effective configuration/source identity, and
all generated monitor-private text artifacts (including continuation response,
history archive, dialogue and progress). The file manifest is generated from
actual artifact bytes. Published archive identity additionally records actual
Git-blob SHA256 separately from runtime CRLF bytes: Git normalized outer JSON
file newlines to LF. Captured string values and research content were not
rewritten. Native and candidate-off requests are compared in full;
P is allowed exactly one declared body insertion into system at every request.

Only explicit per-trace temp root and native history archive filename mappings
are normalized. They are listed under `mechanical_mapping`; source texts,
tool/user history, task evidence and grounds are never dropped. Raw and
normalized differences are both retained. No condition labels enter task or
private paths, strategy text, or model-visible fields. Root proposal IDs are
fixed and distinct. Runtime audit IDs/timestamps are retained in raw receipts,
not treated as model-visible prompt differences.

## Platform limitation

This execution is Windows/Python, with the frozen source's genuine
Python/PowerShell tool schema. It is **not** historical Linux/Bash acceptance.
`docker info --format '{{.OSType}}'` failed because the Docker Linux engine
named pipe was absent. WSL lists docker-desktop only. No Linux environment was
invented or tool schema falsified. Linux/Bash execution parity is NOT COVERED;
these receipts do not authorize a scientific run or assert P effectiveness.
