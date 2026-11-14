# Portable GA input: two real tasks

Execution commit: `6575d8497e7b0e4da31804c2860f34405852588a`.
Dataset: `2fd12b88aafdd04a52c298e3940bcb189f9766d6`.
Harbor: `459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc`.

One new episode each, in `rstan-to-pystan` then `reshard-c4-data` order, using
the unified runner, four-step manager wake period, uncapped Task agent and
official per-task verifier limits. Both completed native evaluation and
owned-resource cleanup. No retry or method change was made.

The ZIP contains the available full visible Task and manager records, tool
calls and receipts, memory, reminders and delivery evidence, run identity,
runtime policy, native evaluation metadata, and cleanup records. It is a
redacted visible projection, not raw HTTP bytes or a restorable private
runtime. Private originals remain local. Excluded from this public copy:
credentials, private profiles/endpoints, provider-private thinking and
signatures, hidden verifier bodies, and runtime source bundles. The external
index maps every included source file's hash to its public projection hash.

The host initially rejected a Docker check in the sandboxed preparation
attempt. A fresh preparation in the authorized host environment succeeded;
this did not start or repeat a model call. Docker and both fixed task images
were available before the real run. Targeted offline checks: 38 passed.

See `PMA_PORTABLE_GA_TWO_REAL_20261115.zip` and its `.index.json`.
