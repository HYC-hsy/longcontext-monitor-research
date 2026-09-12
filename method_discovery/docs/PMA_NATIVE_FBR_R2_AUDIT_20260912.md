# 原生 PMA FBR R2 事后审计

## 结论

本次正常完成，非超时或工程异常终止。7 个原生评分阶段通过 6 个；Phase 2 权重为 2，其余权重为 1，故加权 reward 为 7/8 = 0.875，不是 6/7 的小数。失败仅在 Phase 4 CORS 的两个 wildcard 测试，其余六阶段通过。

这是原生作者 Terminus2 + PMA 在 Docker/CC-VIBE 和 FBR 上的完整运行，不是作者 TB2.0 成绩复现，不是与旧 GA 严格配对。无无-PMA 同配置对照，不能估计提醒的净贡献，也不能把 R1→R2 涨分全部归因于 PATH 修复（两次均为新采样）。

## 运行与工程验收

- controller 开始 2026-09-12 19:07:28，结束 19:50:11，北京时间；总 wall time 42 分 43 秒，包括 setup 与事后评价。
- 48 次任务逻辑调用，94 次 memory 逻辑调用；47 次 PMA 触发，11 次提醒，36 次不注入；75 次记忆操作，操作错误 0。
- 11/11 提醒在对应 task episode 的 `debug.json` 最后一条 user message 中精确匹配。`prompt.txt` 是注入前视图，不可用于宣称提醒丢失。
- 所有已记录逻辑调用 returned、usage 齐全；不能据此排除底层内部重试。controller 有 Pydantic serializer 警告和两条 LiteLLM 通用 debug 提示，现有输出无明确致命异常或可归因服务错误，进程 exit 0。
- episode 44 执行 `go build -v ./...`，工具真实报 MIME 遮蔽；episode 45 修复后再次 build，episode 46 prompt 可见编译成功输出。因此 R1 的工具 PATH 阻塞在本次不再出现。
- 事后评价前 `/app` 归档 25,588,335 bytes；SHA-256 实算与结果一致：`be0f6f7d292a45d2a12c0d616938008c177508b3fa34f39a54a42fc7fba23328`。tar 内不存在本题 `test_01_query_parsers_test.go`、`test_04_cors_wildcard_test.go` 隐藏评价文件。启动时 task/controller network none；未给在线模型反馈事后 verifier。
- 任务容器正常清理，归档和日志保留；controller/gateway 未清理。此次审计未改运行代码、未调用模型、未重跑任务。

## 行为证据：有效纠错和错误记忆并存

### 有价值的局部提醒

PMA Step 9 指出 Query 方法插入产生重复 return/括号；Step 17 指出切换目录后的相对路径错误；Step 23 指出 TLS 插入点搜索范围不足；Step 44 指出 Python enumerate 循环内修改 i 不能跳过后续迭代；Step 46 准确指出局部 mime 变量遮蔽导入包。相应 task 轨迹有继续修复行为。

最清楚的一条：Step 46 提醒送达 episode 45，Agent 将 mime 改成 mimeType 后重新 build，公开输出成功，最终 MIME 阶段通过。这是提醒内容正确、送达、后续动作一致的证据；Agent 自己也看见编译错误，故不证明没有 PMA 就不会修复。

### 核心失败：原要求仍在，却被错误解释取代

1. 原任务 Target 4 要求包含 wildcard 时返回字面 `*`，不附 credentials 例外。PMA 首轮保存的 knowledge 完整保留这一要点，最终 memory.json 仍在。
2. PMA Step 28 的 phase1/phase2 输入都包含原 knowledge。但其提醒写成只在 NOT AllowCredentials 时返回 `*`，称 wildcard+credentials 的回显分支是正确的。
3. 该提醒精确送达 episode 27；Agent 公开计划也明确加入 “unless AllowCredentials is true”，并据此修改。不能确定例外最初由哪一模型产生，但可以确定 PMA 没纠正而是主动强化了它。
4. Step 29 仍写需要 gofmt 和 test；Step 30 仅在格式化/代码查看后就写 Target 4 COMPLETE。后续 procedural memory 把带例外的实现记成 successful approach。
5. 最终归档 `app/middleware/cors/cors.go:115–120` 确实保留 credentials 回显分支。episode 47 完成总结也保留该例外。隐藏评价的两个 wildcard 测试期望 `*`，实际为 localhost 与 http://example.com。

因此这是“要求保留但不再支配判断 + 不等价完成证据”的清楚案例，而非单纯遗忘、提醒未送达或工具不通。不能从可见轨迹确定潜在认知根因，只能说它与沿用现有分支/常见领域假设一致。

### 其他值得保留的负面细节

- Step 8 的同轮 status 已写 Target 1 COMPLETE，提醒却说有 critical duplicate 问题；Step 9 才改回 IN PROGRESS。两个阶段输出存在短暂状态不一致。
- Step 14–18 将语法错误解释为 Go 不允许空格缩进，并把解释保存、复用。这个诊断不成立；Go 并不要求以 tab 才能通过语法解析。不要把后来修好代码视为该诊断正确。
- 显式任务 response 中未发现 `go test`，只有 gofmt 与两次 go build。格式化不能证明行为，整体编译通过也不能证明所有语义要求。此次没有 history summarization，不能拿它证明跨压缩长期持久性。

## 用量

| 角色 | 逻辑调用 | 输入 token（含缓存） | 输出 token | 缓存输入 | 返回用量估算美元 |
|---|---:|---:|---:|---:|---:|
| Task Sonnet 4.5 | 48 | 1,974,774 | 35,455 | 1,833,679 | 1.604 |
| Memory Opus 4.6 | 94 | 1,387,932 | 8,631 | 41,266 | 8.637 |

合计估算约 10.241 美元，非中转实际账单；内部重试可能不完整。task 累计调用耗时 1118.32 秒，memory 1371.73 秒；原版同步架构下 memory 是主要时间/成本部分，不能据此直接估计改并发后的净收益。

## 对下一阶段的意义

原生 PMA 的工程 smoke 已有完整结果，足够结束重复修启动环境这一局部阶段。它展示了有用的局部恢复，也留下与本研究主问题吻合的缺口：不是只把要求存住，而是让原要求持续约束解释和完成判断。

建议下一步先准备同题、同模型与预算的作者 Terminus2 无 PMA 对照，隔离 PMA 的真实增益与额外计算；启动须单独确认。不得给 PMA 加 CORS 特判或根据隐藏测试修改 baseline。我们的机制候选随后应针对通用的判断依据修订，而非单题补丁。

## 原始材料

运行根：`bench_runtime/pma_linux_controller/native_fbr_20260912_r2/work/trial/`。
核心材料：native_result.json、model_calls.jsonl、trajectory_memory.json、memory.json、agent/episode-27/response.txt、episode-45/response.txt、episode-46/prompt.txt、episode-47/response.txt、各 debug.json、verifier/test-stdout.txt、workspace.before-verifier.tar.gz。
计数/送达/hash 由既有离线 `audit_pma_native_run.py` 生成 `PMA_NATIVE_FBR_R2_AUDIT_DATA_20260912.json`；脚本不判因果，以上语义结论另行逐条回看原件。
