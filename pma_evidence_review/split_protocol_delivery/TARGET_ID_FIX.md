# Follow-up: malformed target dependency tracking

Parent public commit: aae212467cb90f62d0288885202b7b8845daf708.
Only citation_gate_agent dependency target resolution and its synthetic tests change.
No prompts, parsing, verdicts, repair limits, transport policies or direct behavior change.

_dependency_target is called only for split. It accepts status for the known status tool,
or an existing nonempty string memory ID whose category matches the known writer (or
existing delete target). Lists/dicts/bools/numbers/unknown tools/unknown IDs identify no
tracked target. Host faults still propagate to global stop; no broad exception swallowing.
Each operation resets its target before parsing. Bookkeeping no longer reads raw args.

37 targeted tests passed, covering malformed targets -> unrelated writes proceed,
known-target dependency blocking, transport/cancellation global stop, and direct host tests.
Two initial logs retain a test-fixture error: host.write omitted empty IDs; the final test
injects memory_id=[]/{} explicitly, reproducing the actual malformed input. No production
workaround was added for that fixture issue. See TARGET_ID_FIX_VERIFIED_TESTS.txt.

The earlier PUBLICATION_REVIEW.json describes the immutable aae2124 candidate. Its two
source/test hashes are superseded by TARGET_ID_FIX_REVIEW.json for this follow-up; the
old test logs and 108-item replay index are unchanged. Any runtime certificate must bind
the new host source hash. No real model, Task, native Harbor lifecycle or evaluation ran.
