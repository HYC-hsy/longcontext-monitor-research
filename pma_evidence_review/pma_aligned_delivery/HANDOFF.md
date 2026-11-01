# 开发线程：PMA 对齐组合候选，只跑一次 SQLite

此交付只完成提示修改和离线工程验收。真实模型、Task、原生 episode 与评价均未在本开发任务启动。用户已指定下一次只运行一个新候选；不要重跑旧组、额外真实冒烟，或自动重试失败 episode。

## 1. 干净检出和离线定向复验

旧 `59fc8830e16bb64e6d0b4ea4244931c958f30754` 仅保留历史，不能作为本次最终交付。
用新组合候选最终回复中的固定 SHA 设置 `P2_DELIVERY_SHA`；不要用可移动分支名代替源码身份。新工作树不能覆盖其他线程。

```bash
git -c core.autocrlf=false fetch origin "$P2_DELIVERY_SHA"
git -c core.autocrlf=false worktree add --detach /new/p2-worktree "$P2_DELIVERY_SHA"
```

在该工作树核对 `git rev-parse HEAD`、干净状态及 MANIFEST.json 的全部源码/交付 SHA，以及 SYSTEMS.json 的完整实际 system。只设置仓库本地 autocrlf，不改全局设置。旧基线为 `d28d0ed75741f3a627721766a29745ab3ae2da9d`，含既有 worker PYTHONPATH 修复。

复用已有 worker Python 的真实依赖，运行：

```bash
python -B pma_evidence_review/tools/run_p2_selection_checks.py --report /new/local/p2-checks.json
```

这是定向假客户端工程复验，不是语义评分或真实 Task。缺依赖应明确报告，不能静默替换依赖。若需核对完整开发回归：

```bash
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tests/run_gate_regressions.py --native-harbor-source-root /path/to/native-harbor-459ff6ec --report-dir /new/local/full-report
```

完整套件保留一个已复现的旧 U/A 预检 fixture 错误，见 TEST_RESULTS.json；不能把这一项说成通过或顺手扩大生产改动修复它。

## 2. 重新准备源码身份，沿用私有配置

私下复制最新成功运行的既有配置，保持 Task/profile/model、镜像、任务与评价协议、网络、评价共享缓存和已批准 runtime_policy。实际未设上限的预算如实记录为 uncapped；已有 official 或显式上限也须保留，不补出隐含 turn/time 限额，不更换模型或评价方法。配置不得发布。

仅保留一条 slot，使用现有无审核候选字段：

```json
{
  "method": "pma-gap-evidence",
  "memory_maintenance_policy": "maintain-scoped-latest-no-review-v1",
  "slots": [{"task": "sqlite-with-gcov", "occurrence": 1}]
}
```

这是对原私有完整配置的覆盖字段，不是独立完整配置。不要携带 citation_review_gate 或 citation_review_strategy，不启用影子审核。所有 output/result/run 目录和 run_id 都必须是新的。

重新 plan/prepare，以最终提交重新生成 committed_runtime_identity、maintenance_source_sha256 和 manifest/config 哈希；不能复用旧运行的这些身份或授权文件。MANIFEST.json 同时列出了 launcher 使用的身份生成源码路径。不能只替换 prompt 文件而沿用旧摘要。

```bash
python -B -m experiment_runner plan --config /private/p2-candidate.json --output /new/p2-plan.json --task sqlite-with-gcov
python -B -m experiment_runner prepare --config /private/p2-candidate.json --output /new/p2-run --task sqlite-with-gcov
```

启动前确认 factory 为 MaintenanceNoReviewAgent，P1/P2 实际 system 均与 SYSTEMS.json 的完整文本、长度和哈希匹配；无 gate/strategy、split/review/repair。验证源码与 worker_ready 策略绑定，不启动额外 episode 作冒烟。

## 3. 只启动一次新候选

开发线程按这一次真实运行的既有授权流程执行一次：

```bash
python -B -m experiment_runner run --config /private/p2-candidate.json --output /new/p2-run --task sqlite-with-gcov
```

失败、环境阻塞或评价异常应归档并停下，不自动另起 episode。保留既有评价共享缓存机制；评价内部既有重试协议不等于授权重跑 Task。不得把评价结果注入同一次在线输入。

## 4. 收集、判断和交付

保留全部 P2 实际 system/user 输入、raw 输出、解析/归一化结果、TASK/M 候选原文与修订身份、选择、待投递校验、实际送达回执和 Task 后续行为。raw intervene、有效选择、实际送达及有用提醒分别报告。对每次选择审查该不该提醒，也检查沉默时是否有明确遗漏；提醒次数增多本身不是收益。记录调用/token/延迟、状态/GAP 局限及原生逐项结果/reward，不单凭 reward 归因。这次同时修改 P1/P2，是一次组合候选；不能把结果分别归因于其中一阶段。

任务结束后依既有原生评价和清理流程收尾，记录所属容器、sidecar、卷与进程清理完成/失败状态。只打包白名单可见字段：移除深层隐藏思考、签名、profile、凭据、端点和隐藏测试正文；私有原件保持本机。审查脱敏包后上传独立归档，远端回读验证 ZIP 字节/SHA-256、CRC、逐文件清单和哈希。

报告新 run_id、固定源码 SHA、实际配置/预算与缓存身份、P1/P2 请求数、选择/送达/帮助性、原生结果、成本、异常和清理。基线沿用既有轨迹，不重跑旧组。成功一轮不能证明泛化、提示语义效果或无审核机制的独立贡献。
