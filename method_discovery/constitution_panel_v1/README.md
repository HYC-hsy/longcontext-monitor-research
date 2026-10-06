# Constitution Offline Discrimination Panel v1

This is a zero-model cognitive-guidance diagnostic, not a reproduction of the
production Supervisor. It tests judgment on frozen public evidence, not evidence
acquisition, long-horizon memory, Reference formation, Situation retrieval, wake
scheduling, Control Echo, or closed-loop task performance. Scientific execution
is not authorized. The Constitution cognitive core is still
`PENDING_MAIN_THREAD_REVIEW`; the runner refuses it.

The v0 source vault remains unchanged at
`114f2407c667f35562a628915f1c84d52909d194`. V1 reads the original
public Task transcript at `4e996fa71739e0ce5960a1c30e2a56e281b6f7e5`,
checks transcript and task hashes against that vault, and saves exact selected
turn blocks. The complete cached public `instruction.md` remains present in
every packet. It is source-hash checked, but is not claimed to capture any
Harbor-added environment note byte-for-byte.

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
| C04 | 402 | 399–402 | 33,778 | built for main audit |
| C05 | 99 | 91–99 | 31,111 | built for main audit |
| C06 | 177 | 78–84, 174–177 | 45,234 | built for main audit |
| C07 | 115 | 109–115 | 31,042 | built for main audit |
| C08 | 181 | 175–181 | 34,004 | built for main audit |
| C09 | 20 | 1–4, 17–20 | 17,990 | built for main audit |

C04 uses FBR `episode_001_step_007.json`, not the old TLS step. C07 tests
whether the currently visible Task behavior warrants another correction. It
does **not** test uptake of an earlier intervention: exact prior delivery is
unproven and no prior-control bytes are in its packet.

The request is `COMMON_PANEL_SHELL + COGNITIVE_CORE`. The shell and abstract
control tools are identical across conditions. The current core consists of
unchanged cognitive/control sentences from lines 24 and 26 of frozen
`GenericAgent-main/monitor_agent_core/ase_v0.py` at
`928af84d3d3ee85382d16b43c0f390fa0650e566`; the final production
seven-tools sentence on line 24 is omitted. The Constitution core is not yet
written. `wait`, `intervene(message)`, and root-only `allow_complete` are
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
