# Existing root checkpoint scope

The frozen v0c `monitor_agent_core/checkpoint.py` captures a pending completion handoff before provider transport. It records `identity.json` (including review/request ID, `archive_sequence` cursor, task turn and handoff), a complete provider-ready `request.json` (system, messages, tools, model parameters), public event/synopsis prefix, copied task workspace and private current state. `manifest.json` hashes copied files; `complete.json` seals the manifest. The implementation checks the same handoff before and after capture and checks that public events end exactly at the handoff cursor. Copying a live workspace tree is not, by itself, proof of an atomic filesystem snapshot under concurrent Task writes.

| Run | Checkpoint | Cursor | Task turn | Request sequence | Published metadata | Full snapshot |
| --- | --- | ---: | ---: | ---: | --- | --- |
| r1 | checkpoint-0001 | 213 | 107 | 65 | `r1/checkpoint_metadata/checkpoint-0001/` | local `.tar`, 116,664,320 bytes |
| r1 | checkpoint-0002 | 225 | 113 | 77 | `r1/checkpoint_metadata/checkpoint-0002/` | local `.tar`, 116,766,720 bytes |
| r2 | checkpoint-0001 | 361 | 182 | 95 | `r2/checkpoint_metadata/checkpoint-0001/` | local `.tar`, 17,664,000 bytes |

All relative paths in the table are under `method_discovery/runs/dynamic_observer_v0c_adoption_20261001/` at source archive commit `9c01b60...`. The exact local tar paths, sizes and SHA-256 values are in `RAW_ARTIFACT_HASHES.json`; the large tars are not copied into this audit commit.

These captures are **root completion requests**, after prior task evolution. They do not hold a chosen earlier ground plus the immediately preceding workspace state. `request.json` is provider-ready for that root request; it is not an arbitrary mid-review resume image. The manifest describes only the captured workspace, not an earlier path-state sequence. Therefore a root checkpoint can support root-request audit without proving `E_t + X_t` availability at the T2/T5/Hyperlink transition boundary.
