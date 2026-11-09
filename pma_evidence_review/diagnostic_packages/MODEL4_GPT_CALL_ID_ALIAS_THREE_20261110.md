# GPT remaining three slots: public diagnostic archive

Execution code: `ef441618a0be740eccc15755940c5450597796dd` (`experiment/pma-gpt-call-id-alias-20261109`). Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`; Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.

Only the three GPT slots lacking a native result were newly run, strictly serially, with fresh run IDs. Earlier interrupted attempts were preserved separately; no Claude or completed GPT slot was rerun. The task model remained Claude Opus 4.8 and the PMA request/returned model was `gpt-6-sol` in each recorded response. Task time and turns were uncapped, native verifier times official.

| Task | New run ID | Native reward | Tests passed/failed | P1/P2 logical responses | Cross-response call-ID aliases | Owned resource cleanup |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| rstan-to-pystan | `pma-bbadc5acf0714d4e` | 0 | 2/4 | 4/4 | 2 | confirmed |
| largest-eigenval | `pma-8597c7a1268b484a` | 1 | 3/0 | 3/3 | 0 | confirmed |
| filter-js-from-html | `pma-fa38d04c176442cc` | 0 | 0/2 | 1/1 | 0 | confirmed |

The previous new-group rstan attempt stopped at `GAHistoryIntegrityError`: two different P1 responses reused the provider call ID `sg_call_1`. The execution fix gives a later cross-response duplicate a local unique history ID, logs provider-to-history mapping, and still rejects a duplicate inside one response. Fourteen targeted zero-model transport checks passed before launch. This batch passed the earlier integrity boundary; it does not establish broader model or method reliability.

The ZIP is a **public visible projection**, not raw HTTP bytes or a restorable private runtime. It includes the three complete selected visible Task/PMA records, run identity, task/verification/cleanup records and source-to-projection file hashes. Private originals stay local. Full profiles, credentials, private endpoints, provider thinking/signatures, hidden verifier contents, execution source bundles and unrelated task files are excluded. The associated index lists every included file, its source hash and public hash. It also identifies intentional omissions; an omitted private field must not be interpreted as absent from the actual request.

Archive: `MODEL4_GPT_CALL_ID_ALIAS_THREE_20261110.zip`
Index: `MODEL4_GPT_CALL_ID_ALIAS_THREE_20261110.index.json`

ZIP SHA-256: `a8bce3bcbec19f5d1e161408ac683ca9d6692c98e0976e4622d8dcaf15ca2f60`; 1,127,078 bytes; 140 members. Local CRC and member SHA-256 checks passed. Remote readback status is recorded in the final delivery response, not inferred from this file.
