# Locally retained checkpoint tarballs

Source root: `E:\LongContext\long_context_bench\output\cprr_real_dev_pilot_20260930\jobs`. These are the untouched local originals, not Git archive members. Hashes were computed over their on-disk bytes on 2026-09-30.

| Record | Trial suffix | Checkpoint | Bytes | SHA-256 |
|---|---|---|---:|---|
| 01 | `fyn-2.2.0-roadmap__qWp7dps` | `checkpoint-0001.tar` | 116520960 | `f21202215e6220ea5f6521667939e3c2262c30df60c18307baf4f7e73b56055f` |
| 01 | same | `checkpoint-0002.tar` | 116602880 | `d9c7c87b2b139aa4f24d384984bd050be4948ce848084aa46b92d820118f88c5` |
| 01 | same | `checkpoint-0003.tar` | 116695040 | `4cf4fff02f609cee79924d2b9b6ec85fc638777597c2298e49f8ce84eeb0acc2` |
| 02 | `fyn-2.2.0-roadmap__wBdFX9d` | `checkpoint-0001.tar` | 116264960 | `cd9ec82d19313fdf5ffa0cf81c0335ba45eb9842afba20c9820f77e94d2fc41e` |
| 02 | same | `checkpoint-0002.tar` | 116326400 | `b7b8dfda79fa1cde9666189f75c161a5c799caa9be9e060c96e67a77c22d0831` |
| 03 | `ktx-0.13.0-roadmap__XheCZfJ` | `checkpoint-0001.tar` | 17786880 | `bc7c07970fb032640249b7355abf7bed0edb8607c955222095fcd2c6fa1de49a` |
| 04 | `ktx-0.13.0-roadmap__riEiMbL` | `checkpoint-0001.tar` | 16998400 | `11a303d72f3a415abe3d6da9777afdc94fb13db4dfa4d4385c6b3a5c1003eaab` |
| 04 | same | `checkpoint-0002.tar` | 17387520 | `ef45d310feb62b61f218be7d8d2fe19280e705ba92109d38da2b67f37835a0a5` |

For each row, the full path is `<source root>/<run ID>/<trial suffix>/agent/monitor/monitor_private/audit/live_checkpoints/<checkpoint>`, where run IDs are `cprr-real-dev-pilot-20260930-01` through `-04`. Metadata from each checkpoint is published under `rN/checkpoint_metadata/`.
