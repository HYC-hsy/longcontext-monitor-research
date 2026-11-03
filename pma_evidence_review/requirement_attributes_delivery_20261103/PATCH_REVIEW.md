# Local audit repairs, 2026-11-03

Scope: two independently reproduced engineering defects only. No prompt, model, tool arguments, maintenance budget, requirement definition or P2 behavior changed. Publication remains on hold pending the parent thread's review and user confirmation; no remote mutation was attempted in this repair turn.

## Historical requirement paging

The original raw-character catalog limit does not bound repeated JSON escaping. Four 509-character path requirements (`Preserve path {i}: C:` plus 245 literal backslash/a pairs, total 2036 characters) could make a history directory item and repeated per-page metadata exceed 8000 characters.

RequirementHistory now measures the twice-escaped attribute representation. Small attributes retain the original full requirements metadata. Larger ones return requirements_paged, count, digest and instructions in directory/metadata, and preserve the full immutable attribute as a pageable JSON-value field named requirements. Its chunks use the existing cursor/snapshot/page machinery; no truncation, semantic completion or new handle grants are inferred. The shared history helper gains only a default-empty historical-fields hook, leaving old candidates' receipts unchanged.

The precise four-string fixture builds A, B and C in successive maintenance cycles, gets B's H from C, deletes B through its actual tool, reopens, and reads B in sources and context views. Every whole JSON page is <=8000 characters; joining requirements parts and JSON-decoding equals the original four strings. Context traverses multiple pages. Ordinary paths, large Unicode/CRLF, original snapshots, unknown/oversized requirements and existing grant rules also pass.

## Startup terminal and counts

Scenario parsing/validation, source identity, script JSON/shape validation and private client setup are inside staged failure handling. A wrapper counts actual client.call attempts and returned responses, including exceptions after calls and failed calls. Error terminals record stage/type and both counts without exception text or profile content. Argument validation before creating output still uses normal argparse errors; an existing unrelated output is never overwritten on directory-creation failure.

With no archive/config and a recorded zero-call failure in an allowed startup stage, --resume may retry startup after correction. Existing committed-state resume checks remain unchanged. A task-runner or uncertain nonzero-call failure cannot be treated as a safe unstarted run. The production CLI was exercised with invalid script JSON: exit 1, script_loading/JSONDecodeError, counts 0/0; corrected resume completed two cycles at 3/3 calls; completed resume returned 0/0 calls.

## Verification

Strict isolated suite: **118 passed, 0 failures, 0 errors, 0 skipped** (95 previous + 23 requirement tests). This includes the two provider-adapter regressions, with dirhash 0.5.0 available. Python 3.12.13; litellm 1.106.6, pydantic 2.14.2, httpx 0.28.1. No dependencies were installed or changed in this repair. Provider adapters use fake clients/network guards; tests of startup mode=real mock setup or fail before it, and make no real provider calls.

66 runtime hashes and the delivery manifest were refreshed. Source SHA is in SOURCE_IDENTITY.json; the final documentation SHA is reported separately. Offline results prove the repaired protocol paths, not model extraction quality or semantic improvement. No real profile, model, Task, P2 or native evaluator ran; no old real experiment was rerun.
