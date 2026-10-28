# Independent Python 3.12 verification

Tested exact source: f97033e98e36386474230ccc14f0c19f8a00e7ce.
Pinned native Harbor: 459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc.
Python 3.12.14: 304 tests, 0 errors, 0 failures, 0 skipped.
All original 297 test IDs retained; 7 added. PMA and native run in separate processes.
The independent 14-response replay equals the committed REPLAY_INDEX.json exactly.
review.py, citation_inputs.py, prompt_strategy.py and citation_gate_agent.py are byte-identical to a250c8aedf61a85f91ec72532ab6e8c02df96617.
Only repair response envelope parsing changed; semantic prompts and write gates did not.
No model network requests, Task, native container lifecycle, official evaluation or production memory writes were performed.
Fake tests exercise second review, rejection/no-write, withdrawal, original target and receipts.
Schema-valid replay does not prove semantic support or retrospectively change real results.

Commands (using an existing dependency-complete environment):
python -X utf8 -B -m pma_evidence_review.tests.run_gate_regressions --native-harbor-source-root <pinned native Harbor> --report-dir <new directory>
python -X utf8 -B -m pma_evidence_review.tests.test_repair_json_fence --out <new replay index>

Preparation note: the cloud baseline worktree initially lacked existing imported source directories due to sparse checkout. Those paths were restored from fixed Git objects, without code changes, before baseline 297/297 and final 304/304 verification. The supplied final child logs are unmodified; historical desktop Python 3.11 limitations remain separately preserved in the parent delivery directory.
