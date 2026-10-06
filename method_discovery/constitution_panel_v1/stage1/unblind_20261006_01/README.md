# Stage 1 unblinding and offline mechanical scoring

This archive maps the already-frozen blind judgments to conditions. It does not revise any scientific response or blind judgment, make a new qualitative assessment, or run a model.

- Frozen blind-review package: `054cb4d357c7e7f0b1a997b9f1cf6c1defccf049`.
- Frozen blind-judgment commit: `2f05296fa0eb790ff44ee1493cbedf536be61d0e`.
- Active Git-external blind-map SHA-256, verified before unblinding: `18e3fc8f2c92f9e36c7281cde9cbf62923d850381b6ae1c86f58523876608652`.
- Frozen PLAN SHA-256: `fec8752d61e526e2b8114cdc3c8fa9408feb398809579661958b1fad2bed61f4`.
- Existing offline scorer source SHA-256: `03be145d4cf3d2cb47ea8eaed4392b2fed3286d2012638453b02e88711447963`; it alone read sealed gold.
- Frozen `BLIND_JUDGMENTS.md` SHA-256: `a63ee7b9f854dda4a5f42d0d45110b782edc352c137afd47eee38f551b31960d`.
- Sealed raw archive manifest commitment SHA-256: `101a398ef5fadc934ed1e8d1126a2f30e067ff8c096ad7f79295435046be796a`. The 54 condition-labeled raw records remain outside Git.

`UNBLIND_MAP.json` was mechanically formed from the SHA-verified active map and frozen PLAN, then checked against all 54 archived trial IDs and the prior sealed export. `EXACT_ACTION_SCORE.json` is the unchanged scorer's output. `UNBLIND_MECHANICAL_SUMMARY.json` aggregates that output and maps only the ten clear A/B preferences already fixed in the blind-judgment commit. `invalid` remains invalid; natural-language intent was not used to repair actions. Exact-action matches are not a clean measure of supervisory cognition because the blind review identified action-channel compliance confounding.
