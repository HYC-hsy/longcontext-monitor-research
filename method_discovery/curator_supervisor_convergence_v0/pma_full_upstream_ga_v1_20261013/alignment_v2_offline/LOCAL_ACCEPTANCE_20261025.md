# Alignment v2 local acceptance (2026-10-25)

This is zero-model engineering evidence, not a real Task run or a method-effect result.

## Identity and scope

- Upstream delivery: `033ad255e733b3b3e44046c7e1531dca5f4cfe2f`, fast-forwarded after exact `FETCH_HEAD` verification. Its last runtime-code change is `0d56993929066abc1e1d0bc713dbbc4ea592cff8`.
- Local runtime source commit: `717b71c43adeb040cdb8c489d9a72b6b80f4749a` (one file-specific LF checkout rule for the historical replay fixture; no method-code change). Harbor certification was committed at `a677701e5e8cb782c2e933181f4b25a55190f581`.
- Method: `pma-gap-evidence` / `pma_gap_evidence_v1`; effective alignment policy: `literal_alignment_with_explicit_unbound_v1`. Ordinary PMA and ordinary pma-gap were not modified. No real model, real Task episode, or official evaluation was invoked.
- Interpreter: `E:\LongContext\bench_runtime\m4\harbor-env\Scripts\python.exe`, Python 3.13.14. `regex==2026.9.29` and `rpds-py==2026.9.1` were installed in this interpreter. Because this virtual environment has no pip module, the pinned regex dependency was installed through the existing `uv pip install --python <interpreter> -r evidence_requirements.txt` path.
- `inspect.getfile` confirmed that `MemoryEnabledTerminus2` came from the pinned PMA vendor, `Terminus2`/`BaseLLM` from its pinned external Harbor, and the aligned agent/store from this candidate directory. The test-only `PYTHONPATH` and `LITELLM_LOCAL_MODEL_COST_MAP` values were restored after the subprocess tests.

## Offline verification

- All `tests/test_gap*.py` plus `experiment_runner`: **280 passed, 3 skipped, 0 failed**. The three skips are Windows symlink-privilege cases (`test_evaluation_cache.py` twice, `test_runtime_reuse.py` once); no privilege or assertion was changed.
- Four affected GA bridge/capture/parity/complete-response files: **42 passed, 0 skipped, 0 failed**.
- `alignment_v2_offline/replay_historical.py`: 32 historical references projected, 26 `exact_unique`, 4 `exact_multiple`, 2 `unbound`; no model requests. This is a development replay, not a replay of unchanged model choices or proof of semantic correctness.
- Initial local replay detected a Windows CRLF checkout mismatch in `evidence_interface_repair_v1_offline/real_public_fixture.json`. Its Git blob and content were unchanged; the narrow LF rule restores the published file SHA-256 `5c85e0ef994496436e3436b6f6581c54ed881a573657f9d7c7b80eb07d209d98`. The replay report then matched its committed bytes again.
- Focused tests cover the actual aligned production classes and shared bank, maintenance→selection/five-tool path, literal/multiple/unbound alignment, pending unbound revisions protecting bound values, independent successful sibling writes, failed atomic updates, save/load identity, and Phase2 visibility. Fixed responses show contract execution, not model judgment quality.

## Final-source Harbor A/B zero-model certification

Committed raw-byte-preserving, redacted certificate: [`cert_evidence_alignment_v2_final_20261025`](../cert_evidence_alignment_v2_final_20261025/FILE_HASHES.json). Its 43 files include the per-file public/private SHA-256 index. `verify_evidence(..., require_committed=True, research_candidate='pma_gap_evidence_v1', conditions=('A','B'))` passed after commit.

| Arm | Run ID | Task requests | Candidate behavior |
| --- | --- | ---: | --- |
| A / U | `pma-20590ad36585484f` | 2 | Pure GA; no PMA reminder or auxiliary stage. |
| B / pma_gap_evidence_v1 | `pma-cbfccbea182a406f` | 2 | Two complete cycles with phases `maintenance, selection, maintenance, selection`; one accepted bound gap write; policy `literal_alignment_with_explicit_unbound_v1`; first actual Phase2 prompt includes that gap; one reminder entered the next Task request, and the later silent cycle added no new reminder. |

Both arms used synthetic tools, receipts, and synthetic evaluation. Both ended with Harbor return 0, no remaining owned container or volume, and removed fixture authorization. The B memory contains one formally saved gap with an `exact_unique` source alignment; this does not test the real model's ability to choose an ID or quote. Negative and unbound branches are covered by the offline tests, not falsely claimed as observed in this finite Harbor fixture.

## Unified entry, same source and certificate

`experiment_runner plan → prepare → run` used a local one-slot SQLite configuration with `method=pma-gap-evidence`, `fake_only=true`, and the committed certificate above. The frozen plan resolved B / `pma_gap_evidence_v1`; effective Agent seconds, Task turns, and outer deadline were `null` under the explicit diagnostic runtime policy, while the task's verifier value remained 900 seconds. The local config was not committed because it contains machine-specific profile paths; no profile content was copied into this report.

The unified run `pma-82939b28a4344fa9` recorded `zero_model_fixture_only=true`, two fake Task request/response pairs, two maintenance→selection cycles, one accepted gap write, one delivered reminder, and a subsequent silent cycle. Both recorded `actual_phase2_prompt` values exactly matched their sent selection payloads and contained the formal gap. Synthetic tools/receipts and synthetic evaluation completed; the synthetic reward must not be read as an official SQLite score. Harbor/worker returned 0, cleanup was confirmed, owned containers/volumes were absent, and the temporary fake `authorization.json` was removed. No real authorization was created.

The private local run artifacts remain at `E:\LongContext\alv2_unified_prepared_20261025`. The non-sensitive identity and artifact hashes are recorded separately in [`UNIFIED_FAKE_INDEX_20261025.json`](UNIFIED_FAKE_INDEX_20261025.json); it is an index, not a replacement for the private raw logs.

## Remaining limits

No real model call, real Task, hidden official test, or official score was obtained this round. The finite fake B chain exercised a bound write, not every unbound or invalid-reference branch; those branches have deterministic local tests. A syntactically aligned quotation does not establish that the resulting natural-language conclusion is true. The full fake run does not establish that live models will use the new visible IDs correctly.
