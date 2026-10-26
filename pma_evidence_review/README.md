# Submitted-citation sufficiency reviewer v1

Current independent entry: `python -m pma_evidence_review.citation_cli --help`.
Read [中文接收与真实实验指导](CITATION_HANDOFF.md). Only submitted, uniquely exact
quotes enter this mode. Existing whole/focus entry below is unchanged and is not a fallback.

# Whole A + verbatim focus reviewer v5

Start with [中文接收、接口、工程 ZIP 和未来真实诊断上传指导](FOCUS_HANDOFF.md).
Explicit `--review-mode whole-focus` adds isolated verbatim focus calls. Default `whole`
uses fixed A (77f0f91d); the former prompt candidate is not active. All packet/source
contracts remain unchanged. Whole and local verdicts are diagnostic, never aggregated.

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review export --review-mode whole-focus --input input.json --out plan.json
python -m pma_evidence_review fake --review-mode whole-focus --input input.json --responses responses.json --out new-run
```

Existing whole API: `review.review`. New explicit API: `focus_review.focus_plan` and
`focus_review.review(packet, transport, locator=locate)`. Current engineering tests do
not establish semantic effectiveness. Historical v4 and prompt A/B handoffs remain in
Git history/docs; their strategy descriptions are not the current default.
