# Windows offline development handoff

Use the fixed FINAL_DELIVERY_SHA from the final response. Independent branch: pma/source-links-context-v1. Current source commit: 449817cd94b846fef9dee995c6784463f5af39a3. Use the existing dependency environment.

```powershell
$env:PYTHONUTF8 = '1'
git -c core.autocrlf=false fetch origin pma/source-links-context-v1
git switch --detach <FINAL_DELIVERY_SHA>
git config --local core.autocrlf false
git status --porcelain
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --source-links-context --report <FRESH_REPORT_JSON>
if ($LASTEXITCODE -ne 0) { throw 'Stop: offline verification failed' }
```

Expected: 78 tests, zero errors/failures/skips. The suite includes a fake-client replay of the exact three visible A04 tool-call rounds from the preserved failed archive; it makes no real model requests. Do not load a real profile or add authorize-real-p1. Do not run Task/P2/eval or resume A05-06/B. Future real runs require separate instructions. Do not repeat historical real groups.

Verify MANIFEST and rebuild source_identity(candidate='source-links-context-v1'): all 62 source hashes must match SOURCE_IDENTITY; code_commit becomes the checked-out delivery SHA. Old source identities/CLI results remain historical and cannot stand in for this version. The replay fixture is included in MANIFEST; original frozen case inputs are unchanged. PYTHONUTF8=1 plus explicit UTF-8 fixture bytes avoids the Windows encoding failure without weakening production hashes.

Candidate selection remains --candidate source-links-context-v1. memory_read_source accepts optional view=sources|context and cursor. memory_delete now accepts the same frozen M alias or an original ID; ambiguity/stale objects are rejected. Original tool-call arguments remain intact, and receipts/operations record resolved IDs. Failed/invalid calls stop subsequent operations in their batch; prior committed operations remain.

Preserve raw windows/bank/results privately. Do not publish whole output directories: source_links.json contains a cursor-signing secret; remove credentials/profiles/private endpoints/hidden reasoning/signatures and rehash public projections.
