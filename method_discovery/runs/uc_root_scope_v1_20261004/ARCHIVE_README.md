# root_scope_v1 four-trial raw archive

This archive preserves the frozen, serial exploratory batch. The implementation
commit is `0a5f42561066ee7fa00a86d446fdb448ddd643d1`; the frozen plan is
`PLAN.json` (SHA-256 `d7fa6ff6b0d2963d27e788ae84791302decc111df907ad23422b7ffd976c5c86`).
The host progress records report all four slots `completed` in the planned
order. They are trial-integrity statuses, not semantic judgments.

| Position | Task | Root mode | Run ID | Task requests | Monitor requests / attempts | Reviews / root reviews | Native phases | Elapsed seconds |
|---|---|---|---|---:|---:|---:|---:|---:|
| 01 | Fyne | RETAIN | `03e00464ee004340a5650955` | 72 | 41 / 41 | 11 / 1 | 1 / 7 | 1073.0 |
| 02 | Fyne | ISOLATE | `0698860f6d0944248574a88d` | 77 | 47 / 48 | 11 / 1 | 2 / 7 | 1116.7 |
| 03 | Kitex | ISOLATE | `408fc195fcdd4c809a625975` | 180 | 112 / 112 | 26 / 3 | 4 / 6 | 2623.6 |
| 04 | Kitex | RETAIN | `c7e72f8420c14e99bbc02c82` | 180 | 75 / 75 | 32 / 2 | 3 / 6 | 1916.2 |

Each `records/<position>_<run_id>/` contains `MECHANICAL_SUMMARY.json`,
`RAW_FILE_MANIFEST.json`, `EVENT_LOCATORS.json`, `ROOT_FRAME_INDEX.json`, and
`ROOT_FOLLOW_LOCATORS.json`, plus the original Task, Monitor, bridge, gateway,
checkpoint, and terminal-verifier files under their respective subdirectories.
`ROOT_FRAME_INDEX.json` points to each first-root provider-ready request and
the frame events; `ROOT_FOLLOW_LOCATORS.json` points to control calls and
subsequent public events. No Carry/Reopen or correctness classification is
encoded in these locators.

The first root provider-ready request used the same root system text and seven
tools in all four records. The observed initial root message counts were 78,
2, 2, and 87 respectively; later root requests within Kitex used the same
per-arm inheritance policy. This is an input-assembly fact, not evidence of
mechanism effectiveness.

Large terminal `/app` capture tar files remain at the original local paths,
with byte sizes and SHA-256 recorded in each `RAW_FILE_MANIFEST.json`; they are
not uploaded here. The raw native result in each record is segregated under
`verifier/` and was not returned to the online Task Agent or Supervisor.
The historical Kitex response-byte limitation is documented separately in
`KITEX_RAW_RESPONSE_AUDIT.md`; no Task execution-chain change was made.
