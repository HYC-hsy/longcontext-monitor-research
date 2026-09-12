# FBR 原生 PMA 试跑 R1

用户已明确批准本次启动。2026-09-12 16:07:03 +08:00 控制器启动，16:07:05任务容器启动。

- Task：roadmapbench:fbr-2.43.0-roadmap，method_dev。
- Condition：native-pma-original-models-docker-ccvibe。
- 模型：Sonnet4.5 task / Opus4.6 memory，temperature0.7/0.3，50turn，7200秒Agent、1800秒事后Verifier。
- 目的：完整原生运行和机制行为/成本检查；不是与旧GA的严格配对，也不是原TB2.0论文成绩复现。
- 执行代码父版本：1131bc5；本轮仅新增任务材料准备脚本，PMA/GA策略不改。
- 控制器：pma-native-fbr-20260912-r1；任务容器：pma-native-74966d521880-main-1；compose project：pma-native-fbr-r1。
- 产物根：bench_runtime/pma_linux_controller/native_fbr_20260912_r1。
- 任务材料、镜像身份、脚本哈希：根目录run_manifest.json / identity.json；不公开private/gateway.json。
- 运行日志：work/trial/model_calls.jsonl、agent/、最终native_result.json及memory.json/trajectory_memory.json。

实际 inspect 确认 controller/task 均 network=none。task只挂载本次空白agent/verifier输出目录，无Docker socket、无旧轨迹和完整任务材料目录；controller持有Docker socket作为可信编排器，不提供给模型工具执行。隐藏tests只由控制器结束后上传。

16:07 首次memory真实调用返回：4992input/707output token，21.09秒。该条仅证明启动进入原生记忆更新，不作为效果证据。保持原算法，不进行人工提示或基于隐藏评价的在线修补。

运行状态以Docker及原始结果文件为准；run_manifest的prepared_not_executed是准备时快照，不会作为已启动后的运行状态真值。最终结论另行追加。

16:13左右用户要求改为后台运行，不再持续盯日志，完成后再审计。任务已由Docker detached controller独立执行，不依赖本会话工具连接。此时尚无最终结果；不再承诺10分钟轮询或主动完成通知。下一次恢复先读取work/trial/native_result.json；若不存在，查询controller状态和model_calls.jsonl。结束后检查退出码、评分、memory/trajectory归档并清理本project专用controller/gateway/socket卷，不删除镜像及证据。最后一次观察约16:12：task9次返回、memory20次返回、无调用失败，episode-9响应尚待生成。
