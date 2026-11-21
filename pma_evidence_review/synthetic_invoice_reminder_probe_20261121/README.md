# Synthetic invoice reminder probe (2026-11-21)

This is a three-arm, one-run-per-arm Task-only diagnostic. It is **not** a
rerun of `financial-document-processor`, a PMA experiment, or a native
evaluation. The Task model received the same short background in all arms:

> 按票据原文提取金额。初稿 CSV 已生成，请接着完成任务。

Three synthetic invoice texts were available as files under `receipts/`, not
embedded in the initial message. `summary.csv` contained one transcription
difference for invoice `INV-2418`: draft `2184.06`, source `2184.60`.
The other two draft amounts matched their sources. The initial workspace
files had identical SHA-256 values in all three arms.

## Identity and limits

- Task GA source: staged from observational commit
  `85bcbf1dcf56098e0aeafefa03a7baf086932223` (based on
  `22b850f32a46410f937d99350e85cff7be95bf2d`); observation mode and PMA
  were disabled in these arms. This archive also includes the exact local
  synthetic harness. `request_seed.json` projects the original Task system,
  seven native tool definitions and non-secret model parameters from a
  recorded pre-request state; no old Task history or provider private blocks
  were supplied to these synthetic runs.
- Configured Task model: `claude-opus-4-8`; temperature `1`, adaptive thinking,
  `max_tokens=64000`, `chat_completions`, streaming. Task profile SHA-256:
  `c3462b8d06113b5398ecb7aa6f8d22dd19584f834c3336426457ab0f29069764`.
  Gateway config SHA-256:
  `85debf4b60d18ebed9ccc006b18204d645d54b5380cb47cf0224f5bd72a2890a`.
  These are client-side identities; the service's effective sampling details
  and physical HTTP attempt counts are unknown.
- Task image ID: `sha256:ef6c9cfaaf14cdd200163008a188d5baa9f626f3bfb8d3e7d6f30c08518e6251`.
  Each arm had a fresh container, independent `/app` bind directory and model
  gateway/channel. Native GA tools were available; PMA, manager, reminders
  after the initial message, and native verifier were not run.
- Frozen order: no reminder, general reminder, targeted reminder. One attempt
  per arm, maximum four Task turns each (12 logical Task requests total).
  Configured client retry policy was unchanged; actual lower-level attempts,
  token usage, and money cost are unknown.

## Zero-model preflight

Each arm's `preflight.json` contains the actual native `file_read` receipts
for the draft and three source files plus one request assembled by the GA
loop through a simulated transport. The three systems, tool schemas, and file
receipts were identical. The first user input was exactly the common
background plus, for nonempty arms, two newlines and that arm's reminder.
No provider call was made during preflight.

## Three evidence chains

| Arm | Reminder actually in first request | Relevant tool actions and receipts | Same-invoice comparison and correction |
| --- | --- | --- | --- |
| none | none | Turn 2 `file_read` CSV (`toolu_pSXNEmCnUCDCYBjnHVKQHP`) returned `INV-2418,2184.06`; turn 3 `file_read` source (`toolu_v3E2UJ06RymmpVe0ZilAlw`) returned `Total Due: USD 2,184.60`; turn 4 `file_patch` (`toolu_hJoE2PS4ySogoo9xeLapPV`) succeeded. | Yes: patch changed the `INV-2418` row to `2184.60`. |
| general | `交付前，对照任务要求和当前结果，看看还有什么需要核对。` | Turn 2 `file_read` CSV (`toolu_I2OwBTfDVB30BhUgxMiYcR`) returned `2184.06`; turn 3 `file_read` source (`toolu_aCzBngAjXUCg1Ig2ZCw3E1`) returned `2,184.60`; turn 4 `file_patch` (`toolu_2VgNEEoAie3Et6Io0Ho8O3`) succeeded. | Yes: same row corrected to `2184.60`. |
| targeted | `交付前，可以把几笔已提取的金额和对应票据原文对一下。` | Turn 2 `file_read` CSV (`toolu_WKdftVWxT9HLOAgasNeM4r`) returned `2184.06`; turn 3 `file_read` source (`toolu_oGpW76du2kRVYFMvdCVu20`) returned `2,184.60`; turn 4 `file_patch` (`toolu_9yRgtxV2tS0rdrDRVVBKF4`) succeeded. | Yes: same row corrected to `2184.60`. |

All three arms also read both other invoice source files. Their `result.json`
files preserve the complete visible prepared Task requests, public responses,
tool calls and matching receipts for all four turns, plus the final CSV. All
three reached the planned `MAX_TURNS_EXCEEDED` boundary after a successful
patch; there was no fifth turn to observe a final Task answer. The final CSV
SHA-256 was the same in all arms:
`4a568fda1cb5f3c4e6febe1bc333282d742bbe974c81af57c40d4efce1355177`.
The exact one-line content change is in `CSV_DIFF.patch`.

This small scene provides no evidence that the targeted reminder improved
evidence acquisition over the other arms: the no-reminder and general arms
also opened the source and made the same correction. One sample per arm does
not establish stable equivalence either.

## Archive boundary

These files are visible Task projections and synthetic source artifacts, **not
raw provider HTTP bytes**. Private `model_responses.txt` and gateway
configuration (which may carry credentials, signatures or private reasoning)
remain local and are not uploaded. No original financial ticket, hidden test,
real provider endpoint, or credential is in this package. `INDEX.json` lists
each uploaded file's size and SHA-256. Every arm's `cleanup.json` records
successful removal of its Task container, gateway container and channel
volume.
