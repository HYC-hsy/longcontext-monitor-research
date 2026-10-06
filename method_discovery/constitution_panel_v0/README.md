# Supervisor Constitution Offline Discrimination Panel v0

This is a zero-model, pre-audit fixture package, not a prompt-effect result or
authorization to call a provider. It fixes nine proposed decision moments from
the historical public online Task transcripts at archive commit
`4e996fa71739e0ce5960a1c30e2a56e281b6f7e5`. The packet contains the
complete archived Task turn blocks from the beginning of that transcript epoch
through the specified cutoff. No turns were semantically selected, reordered,
summarized, or trimmed to make a decision easier. This choice makes packets
large. The public task is the exact cached `instruction.md`, with its SHA-256
checked against the frozen task catalog (or, for Grammar Fuzz, an exact tracked
Git blob). The catalog/public instruction is not claimed to be a byte-for-byte
capture of any Harbor-added environment note. The main thread should audit
this source distinction before any future model use.

| Case | Status | Cutoff Task turn | `packet.json` characters | Full public source instruction |
| --- | --- | ---: | ---: | --- |
| C01 | built for main audit | 38 | 117,077 | yes |
| C02 | built for main audit | 181 | 377,645 | yes |
| C03 | built for main audit | 77 | 234,721 | yes |
| C04 | built for main audit | 324 | 506,461 | yes |
| C05 | built for main audit | 99 | 197,740 | yes |
| C06 | built for main audit | 177 | 269,314 | yes |
| C07 | **UNBUILDABLE** | 115 | — | yes |
| C08 | built for main audit | 181 | 274,989 | yes |
| C09 | built for main audit | 20 | 66,292 | yes |

C04 has no `observed_turns` field in its sealed decision file. The cutoff is
the public Turn 324, immediately before Turn 325's acknowledgement of a control
input; its provenance states this explicitly. C07's archived intervention text
is available, but the published public stream does not establish that those
exact bytes were actually delivered before the selected moment. Its packet is
therefore absent and the preview runner refuses it. No delivery was inferred
from the Task's later wording.

Each built case has `packet.json`, per-segment `provenance.json`, and exact
source extracts. The decision/diagnosis files appear only in `sealed/gold.json`;
`preview_runner.py` neither reads that directory nor imports a provider or
network transport. A local frame has only `wait` and `intervene(message)`;
a root frame additionally has `allow_complete`. No inspection tools are present
in this first-stage snapshot panel. `prompts/current.txt` is the mechanically
copied frozen ASE system guidance; the Constitution candidate remains an
unusable placeholder pending main-thread text.

Rebuild on this machine, without a model:

```powershell
D:\python\python.exe method_discovery\constitution_panel_v0\build_panel.py --repo E:\longcontext-cqs-v0-20261005 --task-assets E:\LongContext\long_context_bench --destination E:\longcontext-cqs-v0-20261005\method_discovery\constitution_panel_v0
D:\python\python.exe -m pytest method_discovery\constitution_panel_v0\test_panel.py -q
D:\python\python.exe method_discovery\constitution_panel_v0\preview_runner.py --prompt current --case C09 --output method_discovery\constitution_panel_v0\previews\C09_current.json
```

The preview command writes bytes and their SHA-256; it cannot send a model
request. Neither offline checks nor a preview establish decision quality.
