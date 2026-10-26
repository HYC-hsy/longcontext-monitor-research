# PMA direct operation evidence reviewer v4

Default API and CLI audit complete original memory operations directly. No extraction
model call, claim rewriting, purpose classifier, or automatic memory revision.

**Start with [中文接收、接口与可复制测试指导](DIRECT_HANDOFF.md).**

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review build --repo . --sample sqlite --out sqlite-v4-input.json
python -m pma_evidence_review export --input sqlite-v4-input.json --out sqlite-v4-requests.json
```

`review(packet, transport, locator=locate)` returns operation report schema
`pma-operation-review-report-v2`, strategy `direct-operation-v4.1`. It preserves the
frozen packet/Phase1 interface and v3 one-based evidence protocol. `export`, `fake`
and `run-profile` use the same one-request-per-operation path. Old `--mode` and
`--extraction-response` flags are rejected. Failed/unknown operations remain visible
without model calls. Full content, deletion target and before revision are preserved.

The original claim workflow remains explicitly named `legacy_review` for comparison;
its tests and historical notes are retained. [HANDOFF.md](HANDOFF.md) describes that
historical workflow, not current default CLI instructions.

No real model execution was performed for this version. Fake tests establish engineering
behavior, not semantic accuracy. Commands/code and observations remain visible with
source roles; identity and quotation binding do not prove entailment or deletion validity.

See [REUSE.md](REUSE.md) for pinned upstream functions/contracts and MIT attribution;
[TEST_RECORD.md](TEST_RECORD.md) and `test-records-v4/` for actual offline validation.
