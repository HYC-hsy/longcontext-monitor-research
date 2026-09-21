# DCEC-v0 real Fyne long-run R2 archive

Run ID: `clean-monitor-fyn-2.2.0-roadmap-dcec-v0-longrun-20260921-r2-tls-recovery`

This directory contains the safely publishable raw record of the single authorized
`fyn-2.2.0-roadmap` DCEC-v0 long-run replacement batch. R1 remains separately archived as
infrastructure-invalid; no R2 retry or ordinary control was run.

## Included

- `proof/`: final proof manifest and complete OTel raw trace.
- `trial/`: Harbor trial result and trial log.
- `agent/`: Task Agent protocol output, research events and recorded identities.
- `monitor/`: persistent Supervisor dialogue, provider history, usage, request attempts,
  reviews, DCEC `working.md`, public task evidence and delivery receipts.
- `verifier/`: native 7-target evaluation output.
- `checkpoint_metadata/`: completion checkpoint request, identities and full file/hash
  manifest, extracted without the large workspace payload.

## Deliberate exclusions

- Gateway configuration, credentials, CA material and isolated private bundle were never
  copied into this public archive.
- The 116 MB checkpoint tar and duplicated full Fyne workspace remain in the immutable
  local run archive because they exceed ordinary GitHub file limits. Their metadata and
  content hashes are included in `checkpoint_metadata/`.
- No research-side post-hoc answer or hidden evaluator material was inserted into the
  model trajectory.

The archive was scanned for API-key and authorization markers before publication.
