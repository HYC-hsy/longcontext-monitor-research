ONE-SLOT R2 STATIC RERUN — DELIVERY AND REPRODUCIBILITY

Frozen code HEAD: 9d0ab5e116c77f29ec80d9357b145991e3ebf2a2 (no tracked worktree modification before or during the run).
Only authorized slot: order=1, case_id=fix-code-vulnerability, variant=R2, occurrence=1, inclusive public event sequence=41.
Batch/run: source-v2-413c2b181e2c / source-v2-413c2b181e2c-01-r2.
Unauthorized input plan SHA-256: B0346137710D66B6700A0DEBECB6D59E99A8D1711FCBD410779D1A893DDE8FAA.
Frozen manifest SHA-256: F4BD4608F4432831AD47B81527BE61903C96BC994B3F4ABB247D5A3DA57058CD.
Private profile raw SHA-256: CC5F784B069034F44BC4527D15ACD70191B1F7FC5810556C087B7B35E0AE00F1. Public resolved model: claude-opus-4-8, adaptive/high, max_tokens=8192, temperature=1, read_timeout=300. Profile timeout=30 and max_retries=8 are not separate effective outer controls; pinned upstream internal retry is up to three attempts. Credential and endpoint values are omitted.
Fixed asset registry SHA-256: D6A3F005879EF7141584B196EC7085F06CBE991E793CD946730541965F7FE8A0. The existing prepare path reverified the authorized public projection before freezing. No old bank was loaded.

Commands executed from the research directory with its documented Python/PYTHONPATH:
python -m freeze_source_v2_batch --plan <absolute new source_memory_v3_single_r2_coordinate_20261015_plan.json> --manifest-out <new private manifest> --output-root <new private run root>
  exit 0: {"batch_id":"source-v2-413c2b181e2c","execution_authorized":false,"manifest_sha256":"F4BD4608F4432831AD47B81527BE61903C96BC994B3F4ABB247D5A3DA57058CD","slots":1}
python -m freeze_source_v2_batch --authorize --manifest-out <same manifest> --authorization-out <new private authorization> --output-root <same root> --profile <existing private profile> --authorization-source user_forwarded_20261015_single_fix_code_vulnerability_R2_coordinate_rerun
  exit 0: {"batch_id":"source-v2-413c2b181e2c","authorization_created":true,"manifest_sha256":"F4BD4608F4432831AD47B81527BE61903C96BC994B3F4ABB247D5A3DA57058CD","slots":1}
python -m static_source_screen --mode live --manifest <same manifest> --authorization <same authorization> --profile <same profile> --output <same root>
  exit 0. Final terminal JSON: {"order":1,"status":"static_prefix_complete","logical_phase_calls":42,"observable_litellm_calls":42}; {"slots_finished":1,"results":["static_prefix_complete"]}. The intervening PTY display emitted repeated LiteLLM provider-list lines and was not saved as a complete console transcript. Complete structured request/response and provider-boundary start/return records are preserved in raw/; console text is not represented as a complete capture.
python -m archive_source_v2_batch --run-root <same root> --archive-root <this new archive> --manifest <same manifest> --profile <same profile> --run-code-commit 9d0ab5e116c77f29ec80d9357b145991e3ebf2a2 --comparison-baseline 657aa0eefe0652a9b6ce8be7eae899ca076fde79
  exit 0: one started slot, raw_trajectories.zip SHA-256 B6262B5D20FB63037668A1B22CEEB480A7C91EC0F0A1D5D9858561D2D9A700FF.

Run-root summary status static_prefix_complete; 42 request rows, 42 response rows, 84 provider-boundary rows (42 starts, 42 returns), 41 public-event bank rows and 41 candidate-audit rows. The two persisted final artifacts match the hashes in the run summary. Original private authorization file was consumed/removed. No matching static_source_screen Python process remained at archival check. No Task Agent, native evaluator, training or scoring-model call was launched; reminders were not sent to Task.

Read AUDIT_COMPLETE_CORRECTED.txt first. It combines the original archive report, diff provenance correction, complete mechanical EVENT_INDEX.txt and the full comparison diff. The original AUDIT_COMPLETE.txt and its empty embedded diff are preserved as generated; see DIFF_PROVENANCE.txt. Raw readable records are in raw/ and their identical packaged copy in raw_trajectories.zip. FILE_HASHES_COMPLETE.tsv covers every other archive file by relative path; its own hash is omitted to avoid self-reference. The original archive FILE_HASHES.tsv is preserved unmodified.

The previous single-slot archive 657aa0eefe0652a9b6ce8be7eae899ca076fde79 / run code 502936c739c22ba7beda55c5e35f3622e9434c44 is descriptive history, not a randomized same-run comparison. This run is a fixed, previously exposed Task trajectory; its reminders were never delivered to Task, and structurally accepted references do not certify semantic support. No conclusion about R2 quality or Task success is drawn here.

Redaction: archive_source_v2_batch replaced the configured private API key and base endpoint in text copies before packaging. A subsequent read-only scan of 25 text files found zero literal matches to those two private values and zero matches for the checked private-key/Bearer/sk-token patterns. The unredacted run root remains outside the repository; private profile and authorization are not committed. Do not treat the hash list or this README as a substitute for reviewing the raw request and response text.

Git byte identity: Windows core.autocrlf would otherwise normalize some mixed-newline text on staging. For this delivery each authorized file was installed into the index from its exact working-tree bytes with git hash-object --no-filters plus git update-index --cacheinfo. A read-only git show :path versus read_bytes comparison covered every selected plan/archive file and found no mismatches. Thus FILE_HASHES_COMPLETE.tsv's per-file SHA-256 values also describe the committed Git blob bytes for its indexed files, not just Windows working-tree bytes; the plan SHA-256 is separately listed above. The final commit and remote are verified after upload.
