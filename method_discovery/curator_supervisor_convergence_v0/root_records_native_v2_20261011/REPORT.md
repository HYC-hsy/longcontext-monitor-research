# root_records_native_v2: zero-model engineering record

Status: implemented as an opt-in candidate; **not activated in the pilot profile** and not live-provider certified.

## Identity and scope

- Archive baseline: `afd9fbc21275ef3aa5d389ad27299e4b32882a69`.
- Second-batch production code: `8cfc4ef2aac99c2378d98a0489fc0cad45511573`.
- Current pilot profile remains `monitor_history_projection=root_records_v1`. The generic default remains `off`.
- No Task Agent, Supervisor model, provider API, native evaluator, training, or scoring-model call occurred.
- No CRS/RHR/RER decision rule, Task prompt, context/history limit, retry, or budget was changed.

## Representation and transaction

`root_records_native_v2` applies at the existing root-entry boundary, once per distinct handoff. It validates exact known Anthropic history blocks and complete unique tool-use/result pairing. It retains user blocks and native historical tool blocks byte-for-byte at the JSON value level, removing only the v1-defined assistant text, thinking, and redacted thinking. Assistant messages left empty are removed and identified in the manifest. It creates no text ledger and no new executable calls.

Before replacing active history, the root hook durably writes and reads back the complete source, projected history, per-block manifest, and commit receipt. The candidate refuses use without the pilot pre-send capture hook. Existing tool-payload archival and complete-exchange-prefix retirement remain responsible for capacity. A v2-only callback records and checks each actual provider transform: archived before-image, after-image, safe cut, retained tail, and continuation-note hash. An unavailable or altered archive fails closed. No safe cut or an oversized retained tail still raises capacity failure.

The pilot's actual pre-transport capture independently reads the committed projection and each transform receipt. It checks the current handoff, model/system/tools, exact initial root input, request-local context or maintenance prompt, and append-only continuity against the previous saved request. A continuation/format-repair usage record does not consume pending root verification. Only an accepted, matching review response marks it verified; an incomplete, empty, cancelled, expired, or discarded response does not. Subsequent review sends in that root review remain checked. Native RER's own branch reset remains native; the projection parent is not inserted into the fresh branch.

## Read-only Kitex-S compatibility result

Source: `live_batch2_20261011/arms/kitex_s/monitor/audit/provider_history.json`, raw SHA-256 `2105467ed7926f35fca0e2c0316c168f64c740966f83f0bdc143dac64c66b473`. Five archived projection directories were authenticated against their source, projected history, manifest, commit, and exact ledger text before recursive decoding. The test-only forensic helper rejects unproven ledger-like text, duplicate/cyclic references, altered rows, and altered manifests. It restores only retained v1 records; removed analysis is not reconstructed.

The archived final provider history has two user messages and zero recognizable exchange cuts. Forensic rehydration yields 250 native messages, 189 paired historical tool exchanges, and 101 recognizable safe exchange cuts. The current v2 codec removes zero additional blocks from this forensic input; its UTF-8 JSON size is 630,786 bytes versus 702,649 bytes for the archived v1 final history. This is **not** historical online-state restoration, a rerun, or a successful Kitex outcome.

No effective private `context_win` or history-limit value was recoverable from the archived public material. The explicit offline assumption is the provider default `context_win=200000`, limit 700,000 UTF-8 bytes, target 574,000. Under that assumption the 630,786-byte rehydrated history is below the trigger limit, so automatic maintenance would not yet run. A separately forced, model-free pressure check against the target archived three large tool results (578,126 bytes), then retired a 65-message complete prefix with `FAKE_CONTINUATION_TEST_ONLY`, leaving 186 messages and 430,346 bytes. That forced check uses a fake archive locator and does not prove a real continuation note preserves cognition or that the provider accepts the representation.

The five projection source-byte SHA-256 values are recorded in `OFFLINE_RESULT.json` and the Git archive. Original batch files were only read, never modified.

## Test evidence and limitations

Zero-model tests cover parallel batches, empty assistant deletion, malformed/duplicate/open exchanges, repeated root handoffs, actual pre-send blocking before transport, tampered source/transform/prior request, fake SSE purpose switching and stopped-response discard, fake continuation transaction, native payload archival and safe retirement, no-safe-cut exhaustion, RER branch reset/parent restore, and no replay of historical tool calls.

The targeted suite passed 141 tests with one deselected legacy byte-identity assertion. Running that assertion without deselection produced 1 failure because it requires `provider.py` to equal commit `29bdcb...` byte-for-byte; baseline `afd9fbc...` already differs from that old commit. This assertion was not edited. On this host pytest also prints an atexit permission warning about an old temporary directory after reporting exit code 0; it is not hidden or counted as a test pass.

Live provider acceptance of an assistant tool-use message after removing its earlier signed thinking remains unverified. The forensic helper is test-only and is not enabled as a live history migration. No new pilot or historical run has been started. The separate CRS evidence re-display candidate remains untouched.
