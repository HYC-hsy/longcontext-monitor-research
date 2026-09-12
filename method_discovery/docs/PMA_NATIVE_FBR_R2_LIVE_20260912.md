# 原生 PMA FBR R2 后台运行

## 启动与范围

- 用户本轮明确批准启动；2026-09-12 19:07:28（北京时间）controller 启动。
- 任务：`roadmapbench:fbr-2.43.0-roadmap`，method_dev。
- 条件：原生作者 Terminus2 + PMA，Docker / CC-VIBE 适配；不是 GA 严格配对，也不是原论文 TB2.0 效果复现。
- 源码冻结点：`7c02a7b`。本次未新增方法改动。
- 任务模型 Sonnet 4.5；记忆模型 Opus 4.6；温度 0.7 / 0.3；50 turn、Agent 7200 秒、事后 verifier 1800 秒。
- 相对 R1 仅使用保留 login-shell PATH 的 r2 依赖镜像，并在事后隐藏评价前归档 `/app`。修复依据见 `PMA_NATIVE_PATH_ARCHIVE_REPAIR_20260912.md`。

## 身份与入口

- 运行包：`bench_runtime/pma_linux_controller/native_fbr_20260912_r2/`。
- manifest：上述目录 `run_manifest.json`。它是启动前不可变 prepared 快照；本文件记录实际启动事实。
- controller：`pma-native-fbr-20260912-r2`。
- task：`pma-native-49acaec7cf17-main-1`。
- Compose project：`pma-native-fbr-r2`。
- task image：`sha256:a6fa79e2dd6cf93c27ebae40cf35852b7aca0e61c3305600c1b41dfa75a24de0`。
- controller image：`longcontext-pma-native:20260912-r1`，新运行包挂载修复后的 runtime 快照。
- 启动前 Docker 29.6.1，E 盘剩余约 48.69 GiB。未删除旧 R1 产物或容器。

## 启动证据与后续

controller 与 task 均已运行，gateway healthy。`work/trial/model_calls.jsonl` 已有 memory 返回记录：首条耗时约 21.82 秒。日志中出现已知 Pydantic serializer warning；尚不能把警告视为任务失败或效果结论。

按用户要求，确认启动后停止轮询，让任务后台执行。后续先检查 `work/trial/native_result.json`、controller 状态，再审计 `model_calls.jsonl`、agent 轨迹、`workspace.before-verifier.tar.gz` 与 verifier 结果。成功启动不是任务成功；当前无最终成绩。实际费用以返回 usage 与服务账单为准。

正常结束后任务容器由运行器清理，绑定日志和归档保留；controller/gateway 可留待审计后定向清理。归档失败时运行器跳过评分并停止保留任务容器，不静默丢失工作区。
