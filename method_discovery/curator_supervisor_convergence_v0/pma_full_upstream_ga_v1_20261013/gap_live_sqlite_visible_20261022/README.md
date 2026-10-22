# Visible exchange supplement: `pma-b51303f481d04569`

This is a **read-only projection of the completed run**, not a replay or a new
model/evaluator call. The original private files remain unchanged. It
supplements, rather than replaces, the earlier
[`GAP_LIVE_SQLITE_AUDIT_20261022.md`](../GAP_LIVE_SQLITE_AUDIT_20261022.md).
The failed task's native reward remains `0.0`.

Open the three UTF-8 JSONL files as **one JSON object per line**:

- [`cycles.jsonl`](cycles.jsonl): all 19 cycles in order. Each row retains
  cycle/event/sequence identity; maintenance operations actually applied by
  the PMA executor; the complete candidate/review material in the actual
  role prompts; the visible maintenance, first review, gap-only revision,
  re-review and Phase 2 responses; final formal gaps; and the recorded
  accepted/stale reason. `actual_role_calls` are in call-sequence order. A
  missing phase was not fabricated. The Phase 2 prompt and response were
  checked against the independent trajectory fields for every cycle.
- [`task_turns.jsonl`](task_turns.jsonl): all 19 Task model requests and
  public response blocks in order, including the late installation, PATH,
  verification and final completion claim. Each selected tool call is paired
  with the **actual tool-result block shown in a later Task request**; 18/18
  tool calls had such a block. The stored Task request is a visible projection,
  not raw HTTP bytes. Its full original payload SHA-256 is kept separately.
- [`reminders.jsonl`](reminders.jsonl): the three verbatim reminder bodies,
  PMA event IDs, GA append IDs, exact Task request IDs, visible subsequent
  response blocks and their tool receipts. Presence in the later request and
  a corresponding provider attempt/response were checked; these are not
  merely generated-but-unsent reminders.

For the critical end of the run, filter `cycles.jsonl` by `cycle_step` 17–19
and `task_turns.jsonl` by `task_turn` 17–19. In cycle 18 the accepted formal
gap still describes PATH availability as incomplete. Cycle 19's attempted
update is marked stale with its recorded error. Task turn 19 contains the
Task's own completion claim; it is not a verifier conclusion. The corresponding
later request contains the previous turn's tool receipt. No hidden verifier
source or answer is included.

[`INDEX.json`](INDEX.json) maps every public file and public row to its
SHA-256 and byte count, and lists each selected private original file's
original-byte SHA-256. Each JSONL row also carries source file, line number,
raw-line SHA-256 and relevant cycle/call/tool IDs. A trajectory step carries
the whole original file hash plus a **canonical step-object hash**, which is
not misrepresented as a byte span from that JSON file. Original Task payload
hashes refer to the complete recorded request, whereas the public request
projection omits private metadata and hidden blocks.

The exporter used an allowlist and made these removals/replacements:

- 156 `thinking`/`redacted_thinking`/`reasoning` blocks were omitted from
  repeated Task request histories. Public response records were already
  captured as visible blocks, with `hidden_thinking_excluded_at_capture`.
  The non-secret `thinking` **configuration setting** remains visible.
- Provider/session metadata (including `user_id`) and private provider URLs,
  credentials, raw HTTP headers, private profiles, `reasoning_phase1/2`, raw
  hidden thought, and all verifier scripts/hidden test output were never
  selected. The full Task request SHA remains available to bind the projection
  to the original.
- 79 URL occurrences in selected visible text were replaced with
  `[REDACTED]`, including public URLs, as a conservative private-endpoint
  safeguard. Their field paths and counts are listed under
  `excluded_or_replaced` in `INDEX.json`. No model sentence, tool result,
  candidate or review was rewritten into an analyst summary; URL tokens are
  the only replacements in those selected strings.
- PMA tool calls in `gap_visible_transport.jsonl` were originally stored as
  string representations, not raw provider wire objects. They remain those
  strings in the export; the separate `maintenance_operations_as_recorded`
  come from the executor trajectory and show which operations actually ran.
- Tool results are the recorded **Task-visible receipts** in subsequent
  requests, not a claim to reproduce raw tool process stdout byte-for-byte.
  Repeated history appearances are deduplicated by tool-use ID; source
  request/line/block coordinates identify the first later visible receipt.

Generation was performed by
[`export_gap_visible_audit.py`](../export_gap_visible_audit.py) against the
same private run identity. Offline checks rehashed all seven selected private
source files, every exported row and all three public JSONL files; verified
19 cycles, 90 role request/response pairs, 19 Task turns, 18 matched tool
receipts and three reminder links; and rejected public URL/credential/hidden
thought markers. A second offline export with the final script produced
byte-identical `cycles.jsonl`, `task_turns.jsonl`, `reminders.jsonl` and
`INDEX.json`; its temporary copy was removed. The source and destination
hashes are separate throughout.
