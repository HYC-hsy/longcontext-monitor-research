# Tag-and-ID phase-2 selection integration

Production parent: `af4a26e1ec91656a5fe1c333f9c12ca0e5fde897`.
Prototype: `834c9861bb79bb4ef79896a4cd7228a0d1f728ab` (nine files matched its manifest).

The gated v4 path keeps phase 1, reviewer, splitter, evidence handling, repair and
memory publication unchanged. Phase 2 now presents read-only `TASK` and `M1...`
aliases for the visible committed revisions and accepts only one complete
`<intervene>...</intervene>` or `<no_intervention/>` decision. One complete
unlabelled, `xml` or `text` Markdown fence is normalized. Other text and the
old JSON protocol are rejected. The host logs raw output and normalization,
binds the response to its captured snapshot, checks selected active revisions
and content before delivery, and assembles exact original text. Errors are
recorded separately from deliberate silence.

This adapter uses the existing serial episode lock for parse, validation and
enqueue. It does not add a new concurrency system or change the existing
visible-window/prefilter behavior. The old JSON prototype remains historical
material, not the running parser.

Local offline checks: fixed prototype 14/14; affected host tests 12/12;
source-identity checks 2/2. The real-client smoke used the existing PMA profile
and made two phase-2 calls only: the needed-reminder case returned an accepted
intervention selecting `TASK,M1`, and the quiet case returned `no_intervention`.
The prepared Task request was decoded and matched the frozen catalogue text
exactly. No Task request was sent in the smoke. Its first raw-substring check
was false because the JSON wire escapes newlines; a read-only decode check
confirmed the actual decoded content without another model call.

The previous 17 JSON-fence `selection_error` results remain unchanged. The
smoke is protocol evidence, not a task-effect result or a semantic benchmark.

Run the affected checks from the repository root with the existing Python:

```text
python -X utf8 -B -m unittest pma_evidence_review.tests.test_verbatim_selection_integration pma_evidence_review.tests.test_tag_selection_integration -v
```
