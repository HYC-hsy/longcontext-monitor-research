# Manager temperature matrix, 16 real tasks (2026-11-18)

Execution code: `43b43157718eeb5172888af75963d8ba0dd3e631`, based on the fixed prompt `e3e6cb42cdcfd010c4b5285108c045359adb6209`. Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.

Order: manager temperature 1, 0.8, 0.5, 0.2; at each temperature, RStan twice then ARC twice. All 16 valid runs completed native evaluation and owned-resource cleanup. The initial attempt at slot 6 was interrupted when its host runner disappeared; it had no native evaluation and is preserved separately as an unscored record. A fresh slot 6 with a new run ID completed; it did not inherit the interrupted attempt's knowledge or task environment.

Native rewards by temperature, with each pair in run order:

| Manager temperature | RStan | ARC |
| ---: | --- | --- |
| 1 | 0, 1 | 1, 1 |
| 0.8 | 1, 1 | 1, 1 |
| 0.5 | 1, 0 | 1, 0 |
| 0.2 | 0, 0 | 1, 1 |

Across completed runs, 567 logical manager calls and 569 observed manager HTTP attempts were recorded; two non-200 attempts in one ARC run were recovered by the existing client retry. All observed manager outbound requests carried their assigned temperature. This establishes request transmission and interface acceptance, **not** the server's internal sampling temperature. Manager response token usage and total USD cost were not recorded reliably and remain unknown.

The ZIP contains the full redacted visible Task and manager records, tool calls and receipts, knowledge state, outbound-parameter audit, native evaluation and cleanup evidence, plus the separate unscored interruption. It is a projection, not original HTTP bytes or a restorable private runtime. Private originals remain on the development machine. Credentials, private endpoints and profiles, provider-private thinking/signatures, hidden verifier bodies and staged source bundles are excluded. The external index maps local original hashes to public member hashes and records ZIP/member sizes.

These are two runs per task and temperature on development tasks, not evidence of a stable or causal temperature effect.
