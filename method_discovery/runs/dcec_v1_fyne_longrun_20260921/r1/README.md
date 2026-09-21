# DCEC-v1 real Fyne long-run R1 archive

Run ID: `clean-monitor-fyn-2.2.0-roadmap-dcec-v1-longrun-20260921-r1`

This directory contains the safely publishable raw record of the single authorized
`fyn-2.2.0-roadmap` DCEC-v1 long run. No ordinary control, repeat, synthetic fixture, or
post-run mechanism change was used.

## Included

- `proof/`: final proof manifest and complete OTel raw trace.
- `trial/`: Harbor trial result and trial log.
- `agent/`: Task Agent protocol output, research events, and recorded identities.
- `monitor/`: persistent Supervisor dialogue, provider history, usage, request attempts,
  reviews, DCEC `working.md`, public task evidence, runtime receipts, and delivery receipts.
- `verifier/`: native seven-phase evaluation output.
- `checkpoint_metadata/`: completion checkpoint request, identities, and full file/hash
  manifest, extracted without the large workspace payload.

## Deliberate exclusions

- Gateway configuration, credentials, CA material, and isolated private bundle were never
  copied into this public archive.
- The large checkpoint tar and duplicated full Fyne workspace remain in the immutable local
  run archive. Their metadata and content hashes are included in `checkpoint_metadata/`.
- No research-side answer, hidden evaluator material, or post-hoc mechanism interpretation
  was inserted into the model trajectory.

The archive was scanned for credential and authorization markers before publication.
