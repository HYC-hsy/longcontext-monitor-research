# Financial task provider-response capture (one run)

- Execution commit: `22b850f32a46410f937d99350e85cff7be95bf2d`
- Run ID: `pma-b4e9c2d1d0b34e64`
- Task: `financial-document-processor`, once; no W20 replay or task retry.
- Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.
- Native result: reward `0.0`; 3 of 7 tests passed. Task and manager processes, containers, and owned volume were cleared.
- Manager HTTP audit: 45 attempts, 45 responses, 45 complete one-to-one captures, 0 missing/incomplete/duplicate. All 45 complete responses were classified `not_returned` for protocol-level reasoning fields. This does not establish whether the service performed internal reasoning.
- Task: 33 actor steps. Manager: 9 wakes, 45 logical responses, 9 successful `memory_read`, 23 successful `memory_add`, 4 successful `send_reminder`. Four reminders entered actual Task requests at actor attempts 13, 17, 21, and 25. No Task knowledge-file read was observed.

At wake 32, the manager's visible input included the Task's final file-count and CSV check. Its response at call sequence 42 described the task as complete and saved an `ALL REQUIREMENTS MET` entry. That visible check did not independently establish the correctness of every document classification. No later manager reminder was generated, so this run does not show a subsequent reminder using that completion entry to prevent a recheck. The full visible coordinates are in `manager/memory_payload.jsonl` (wake 32, call 40), `manager/memory_response.jsonl` (wake 32, call 42), `manager/memory_tool_results.jsonl` (call 42), and `task_agent/research_events.jsonl` within the ZIP. This is a source-location note, not a causal claim about the final score.

The ZIP is a redacted visible projection, not raw provider HTTP bytes. Provider raw responses, signatures, credentials, private profiles and endpoints, and native verifier bodies remain local. `CAPTURE_RECONCILIATION.json` inside the ZIP preserves each request coordinate, capture status, response ID when available, raw-byte count, and SHA-256 without publishing the raw body. The adjacent index records original-to-public file hashes and ZIP member hashes. The production prompt, request parameters, and Task input were not altered for publication.
