# Developer handoff — one fresh candidate only

Do not start from the currently published step-1 SHA. The complete candidate is local until the publication blocker is cleared and a final fixed remote SHA is confirmed.
Do not interrupt SQLite/fix-ocaml-gc runs pinned to earlier commits, change their worktrees, or automatically append an episode.

Once the complete remote SHA is provided, use a new clean detached checkout with repository-local `core.autocrlf=false`; verify MANIFEST file hashes, SYSTEMS texts/schema, and the exact bank/Agent types. Run offline checks:

```bash
python -B pma_evidence_review/tools/run_bank_display_checks.py --report /new/local/directed.json
```

Expect 57/57. The optional full strict runner command and known U/A fixture error are recorded in TEST_RESULTS.json. Use real installed dependencies; report missing packages rather than substitutes. Offline fake worker tests do not launch a Task.

Privately reuse the existing Task/model/profile, image, network, native evaluation/shared cache and approved runtime budget. Record uncapped limits as uncapped. Change only the explicit candidate fields, keep one new slot and fresh output/run IDs:

```json
{"method":"pma-gap","memory_maintenance_policy":"pma-bank-display-v1","slots":[{"task":"sqlite-with-gcov","occurrence":1}]}
```

Do not carry citation_review_gate, citation_review_strategy, old bank files, old authorization files, old code hashes or old certificates. Re-run plan/prepare from the complete fixed commit to regenerate startup identity, maintenance sources and manifest hashes. MANIFEST includes the identity-generation and launcher source paths. The store must be exactly GapMemory, with no history/evidence fields. Ready policy and actual system/schema hashes must match.

After the parent's per-run authorization, launch only one new SQLite candidate episode through the existing experiment_runner entry. Do not run old groups, additional real smoke tests or automatic replacement episodes. A failed or blocked episode is archived and stopped, not automatically retried.
Preserve complete P1/P2 inputs, raw P2 choices, parser status, selected aliases/current text and actual delivery receipts. Judge useful displays, unnecessary displays and missed opportunities; increased count alone is not benefit. Combination results cannot separately establish a P1 or P2 effect.
Complete the existing native evaluation, shared-cache protocol and resource cleanup. Publish only a sanitized diagnostic package; remotely read back ZIP bytes/SHA/CRC and per-file hashes. Do not publish credentials, endpoints, profiles, hidden thoughts/signatures or hidden test bodies.
