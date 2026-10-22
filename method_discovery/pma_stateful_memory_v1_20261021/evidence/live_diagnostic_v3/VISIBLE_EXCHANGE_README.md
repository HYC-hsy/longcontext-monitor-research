# Real diagnostic `pma-0ec81bdaac544d8f`: visible exchange

The original `AUDIT.txt` was only a summary and hash index. This supplement
contains the four complete **model-visible generation request bodies** (system,
messages, model and generation settings) and four complete **visible response
texts**, in chronological order. It also contains the exact re-audit
`required_coverage` and returned `coverage` arrays, extracted without changing
their entries. See `visible_exchange/INDEX.json` for call binding, private
source hashes and separate public-file hashes.

The request JSON files are reserialized public projections, **not identical
HTTP-payload byte copies**. The visible response `.txt` files retain the
provider-parsed text bytes, including Markdown fences; their hashes match the
private response hashes. Each `parsed_user_view.json` additionally renders the
request's JSON user message as readable fields; it is a derived view, not a
second model request. Private endpoint, headers, profile, user metadata,
transport logs and hidden thinking are not exported. No Task request occurred.
The private originals remain in the original run directory. The exporter
checks matched calls and roles, refuses changed existing outputs, and fails
on credential, authorization-header or URL-like strings in the public files.

The mechanical comparison is precise: the re-audit requested 15 direct
`{kind,id,revision?}` coverage refs. The returned array names the same 15
targets but wraps every target as `{snapshot,target,field_path}` with
`field_path="$root"`; therefore the validator rejected it as
`coverage_mismatch`. The first audit's coverage used the required direct-ref
shape. Matching target identities does **not** establish that the repaired
candidate, the first audit issues, or the re-audit's `clean` conclusion was
semantically correct. The complete visible inputs and responses are supplied
for independent review; no expected semantic label is substituted for them.

No model request, Task episode or evaluator was run to produce this supplement.
