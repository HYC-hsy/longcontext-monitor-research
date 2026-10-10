# C02 H/R native-boundary static run2 — mechanical delivery record

This record contains no diagnosis-quality or H/R winner judgment. The Task Agent,
native evaluator, training, and scoring models were not run. Task control was
record-only and was not delivered to a real Task Agent.

## Identity and bounded change

- Run1 source/archive baseline: `392155cb23f89775d2a7ca75607be6ae2c891237`.
- Run2 research implementation commit: `7b1e6ee27bed173a0a5ddc92f520a612bc24513b`.
- Production files changed: 0.
- Frozen H_full canonical request SHA-256:
  `d4a866f07c8376fd990745dda4d207b87299e7d690117c7584dcf2b28f1fa77b`.
- Frozen R_full canonical request SHA-256:
  `58ad93e929c086c78ef5e7094d715481c584bf69f86f1af415c4ebb91b330e56`.
- Run2 freeze raw SHA-256:
  `a3edf45d7ba441fb79b0c3675485c2d9b1a0c8fa20eebf1bfb5bef74c32638e2`.
- Research transport: connect timeout 120 seconds, read timeout 300 seconds,
  direct session, TLS verification on, max retries 0, recovery deadline absent.
- Original Task tree, history projection, frozen first requests, model, tools,
  generation parameters, and 418-line dialogue prefix were unchanged.
- Docker task image: `sha256:b0da1cb31d367df38d05b81f98e68a94b0f7114efd3c82537633d1d92325efe1`.

## Zero-model checks

Command executed before run2 freeze and all model calls:

```text
python -m unittest method_discovery.curator_supervisor_convergence_v0.diagnostic_boundary_bridge_v1_20261010.test_native_runtime method_discovery.curator_supervisor_convergence_v0.diagnostic_boundary_bridge_v1_20261010.test_bootstrap
```

Exit code 0; stdout/stderr result: `Ran 21 tests in 383.105s — OK`.
The tests used fake provider responses and the certified zero-model Docker tool
port. They covered frozen first requests, ordinary bad arguments, malformed and
overlapping SSE, single-attempt handshake timeout classification, historical
receipt/observation handling, RER branch transitions, native control ordering,
and archive construction. `git diff --check` passed for the implementation
before commit. Raw generated text contains source-preserved trailing whitespace;
the archive was not rewritten to satisfy code whitespace conventions.

## Batch and archive

- Run1: 12 planned, 3 started, 2 simulated interventions, 1 infrastructure/
  protocol failure, 9 unstarted. Run1 was not resumed or modified.
- Run2: 12 planned, 12 started, 12 simulated root interventions, 0 unstarted,
  0 infrastructure/protocol failures.
- Run2 total outer model cycles: 227. Total provider requests: 227. Complete
  accepted provider responses: 227.
- Per-slot terminal, first control proposal, provider usage, lifecycle events,
  and wall time: `MECHANICAL_SUMMARY.json` inside `RAW_TRAJECTORIES.zip`.
- Raw local root: `E:\c02_hr_native_boundary_static_20261010_run2`.
- Archived file index: 1525 source files. The export required 0 secret-byte
  replacements. Original local raw logs were not edited.
- `RAW_TRACE_INDEX.json` SHA-256:
  `d673c5bac99f255e6fa817364d3ae7b6601c99df9a6913b417d4eb161b7f2900`.
- `RAW_TRAJECTORIES.zip` SHA-256:
  `72461dbd33fbf48ba8f1eacf9e0ce507782bd48c8a515c36195a8541e2e3845b`.
- Full redacted TXT packet SHA-256:
  `cbb3f5ea50f16072b4faf16a5d035c07203dd23146c99cd6575fde35a416f483`.
- ZIP CRC and all archived member sizes/SHA-256 were verified by the archive
  builder after writing.

The ZIP contains selected raw provider requests/SSE, provider responses,
dialogue, Task Book and cutoff-visible evidence, per-slot RER branch snapshots,
tool scripts/results, identity and result files, and the mechanical summary.
It is not a whole-host image: disposable Task-code copies and per-slot HOME/TMP/
build caches are excluded as described in `RAW_TRACE_INDEX.json`.

No A/B/C/D/E diagnostic-quality labels were assigned by the development thread.
