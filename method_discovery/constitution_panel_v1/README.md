# Constitution Offline Discrimination Panel v1

This is a **retrospectively curated offline discrimination diagnostic panel**,
not a reproduction of the production Supervisor or a blind/random sample of
tasks. It tests judgment on frozen public evidence, not evidence
acquisition, long-horizon memory, Reference formation, Situation retrieval, wake
scheduling, Control Echo, or closed-loop task performance. Scientific execution
is not authorized. The Constitution cognitive core is still
`PENDING_MAIN_THREAD_REVIEW`; the runner refuses it.
Future nine-case results may support prompt screening, failure-mode diagnosis,
and a decision to try closed-loop experiments. They cannot estimate general
task accuracy, unbiased benchmark performance, or closed-loop effectiveness.

The v0 source vault remains unchanged at
`114f2407c667f35562a628915f1c84d52909d194`. V1 reads the original
public Task transcript at `4e996fa71739e0ce5960a1c30e2a56e281b6f7e5`,
checks transcript and task hashes against that vault, and saves exact selected
turn blocks. The complete cached public `instruction.md` remains present in
every packet. It is source-hash checked. Each case records
`instruction_md_exact_recovered=true`,
`complete_online_public_context_proven=false`, and unknown Harbor-added note
byte identity. The cached instruction is not claimed to restore that full
online context byte-for-byte.

For each sealed `observed_turns` number `t`, the builder includes `[t-3,t+3]`
clamped to `1..cutoff`; it also includes `[cutoff-3,cutoff]`. The union is
ordered by Task turn. Decision prose, diagnosis, release condition, and gold
are never used to choose evidence. No turn is summarized or semantically
selected. Included turns, omitted ranges, source line locators, and hashes are
in each `provenance.json`.

| Case | Cutoff | Included turns | Packet characters | Status |
| --- | ---: | --- | ---: | --- |
| C01 | 38 | 32–38 | 34,954 | built for main audit |
| C02 | 181 | 175–181 | 29,984 | built for main audit |
| C03 | 77 | 74–77 | 30,693 | built for main audit |
| C04 | 324 | 315–324 | 24,540 | built for main audit |
| C05 | 99 | 91–99 | 31,111 | built for main audit |
| C06 | 177 | 91–97, 106–112, 170–177 | 71,122 | built for main audit |
| C07 | 115 | 109–115 | 31,042 | built for main audit |
| C08 | 181 | 175–181 | 34,004 | built for main audit |
| C09 | 20 | 1–4, 17–20 | 17,990 | built for main audit |

C04 is the public TLS measurement snapshot at cutoff 324, with main-thread
audited anchors `[318,324]`; no Turn 325 or later material is included. C06
uses audited anchors `[94,109,173,177]`, preserving the public 4/6 → 5/6 →
focused repair → completion sequence without later reassessment. These anchor
numbers are recorded as `main_thread_fixture_audit`, not attributed to sealed
decision metadata. Historical decision files are locators only for C04/C06.
C07 tests whether the currently visible Task behavior warrants another
correction. Its packet is byte-identical to the prior v1 commit. Its gold was
rederived by the main thread from the packet, not from the historical decision;
it does **not** test uptake of an earlier intervention. Exact prior delivery is
unproven, and no prior-control bytes are in the packet.

The request is `COMMON_PANEL_SHELL + COGNITIVE_CORE`. The shell and abstract
control tools are identical across conditions. The current core consists of
unchanged cognitive/control sentences from lines 24 and 26 of frozen
`GenericAgent-main/monitor_agent_core/ase_v0.py` at
`928af84d3d3ee85382d16b43c0f390fa0650e566`; the final production
seven-tools sentence on line 24 is omitted. The Constitution core is not yet
written. The manifest has no frozen Constitution SHA, so the runner refuses it
even if the placeholder file were edited. Every cognitive core must match an
explicit frozen manifest SHA before request assembly. `wait`,
`intervene(message)`, and root-only `allow_complete` are
panel action classes, **not** the production tool schema. This stage permits
no inspection tools. `sealed/gold.json` is never loaded by the runner.

Build and test locally without a model:

```powershell
D:\python\python.exe method_discovery\constitution_panel_v1\build_panel.py --repo E:\longcontext-cqs-v0-20261005 --task-assets E:\LongContext\long_context_bench --destination E:\longcontext-cqs-v0-20261005\method_discovery\constitution_panel_v1
D:\python\python.exe -m pytest method_discovery\constitution_panel_v1\test_panel.py -q
D:\python\python.exe method_discovery\constitution_panel_v1\preview_runner.py --prompt current --case C09 --output method_discovery\constitution_panel_v1\previews\C09_current.json
```

The preview command only writes local request bytes and their SHA-256. It has
no provider transport. Before any future prompt comparison, the main thread
must audit the exact task sources, window contents, and sealed separation.
