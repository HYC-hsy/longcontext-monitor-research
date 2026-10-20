# v6 execution identity and formal certification

The v6 synthetic episode `pos-264631de99a64a8f` ran code bound to
`52f85a34db52b748f246d6cfd85a4aa686a1d7c5`. Its private original is
`E:\LongContext\pos_pma_shared_view_offline_20261020_v6`; the public
`raw_repair_v6` is a derived review export, not a native-SHARED certification.

The original `execution_identity.json` records the runtime SHA-256 of
`GenericAgent-main/agentmain.py` as
`517665d6a5431c1144177686922431ead234fabde209c851d9ba15511f4eaa3a`.
Both retained copies, `runs/pos-264631de99a64a8f/bundle/source/agentmain.py`
and `runs/pos-264631de99a64a8f/control/ga_stage/agentmain.py`, are 41,965
bytes and have exactly that hash. The bound Git blob is 41,271 bytes with
SHA-256 `85104e0f8af9c67afb07c59f85c16f2e6d1d52ec5be7c1d2c91901e8336aeecd`.
Replacing CRLF with LF in comparison copies yields that blob byte-for-byte;
there is no content difference. The same comparison passed for `agent_loop.py`,
`ga.py`, `llmcore.py`, and `research_runtime.py`; their raw runtime and Git
blob hashes remain distinct in the unmodified execution identity.

Between `52f85a3` and the later review commit `eda638a`, the changes were
the synthetic evidence exporter, a test, `.gitattributes`, and review/test/raw
documents. None changed the frozen runtime source files. This statement does
not rebind the historical v6 episode to the later commit.

`certification_v6/` is newly exported from the retained private v6 original
using the existing `collect_native_shared` collector. Its
`FILE_HASHES.json` uses `pos-ga-native-shared-evidence-v1`, listing public
byte hashes separately from private source byte hashes. The fixture used
finite fake model replies and a synthetic deterministic sentinel, not a real
provider or official evaluator. This directory must be checked with
`verify_evidence(..., require_committed=True,
research_candidate='pos_pma_shared_view_v1')` after it is committed; review
exports or this note cannot substitute for that mechanical check.
