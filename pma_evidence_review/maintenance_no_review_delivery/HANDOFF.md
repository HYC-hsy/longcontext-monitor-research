# 给开发线程：只执行一次新候选 SQLite

本交付仅实现并离线测试；未启动真实模型、Task 或原生评价。真实启动仍由用户的开发线程在获得本次授权后执行，不重跑旧组。

1. 在独立工作树读取本分支最终固定提交，保持 `core.autocrlf=false`，核对 SOURCE_SHA256.json。不要用分支名代替最终 SHA 固定源码。旧基线 `e52908b1ca68b62e35ba8bec67ff106434503f4a` 和旧实跑 `pma-17ded442e35c47f5` 只作既有参考。
2. 私下复制上轮已经批准的运行配置，沿用 Task、PMA 模型、运行预算、镜像、网络、原生评价协议、原题与 profile 路径。保留私有配置在本机；不要把 profile、端点、凭据、隐藏正文或原生测试正文提交到 GitHub。
3. 仅将方法配置调整为下面的候选。删除 `citation_review_gate`、`citation_review_strategy` 和旧 gate 证书/哈希字段；不要设为 v4、不要同时开启影子审核。保留已有 `runtime_policy`，不要为了本候选重跑旧 A/B 原生证书。使用现有 experiment_runner frontend 的 committed_runtime_identity 流程，prepare 会生成新的无 gate 源码清单。

```json
{
  "method": "pma-gap-evidence",
  "memory_maintenance_policy": "maintain-scoped-latest-no-review-v1",
  "slots": [{"task": "sqlite-with-gcov", "occurrence": 1}]
}
```

这是对原私有配置的覆盖字段，不是可直接运行的完整配置。新的 result/output 目录必须空且唯一；使用新 run_id，不能复用旧 run 的目录或授权。

已确认的 frontend CLI（先 plan/prepare，不代表已获真实启动授权）：

```bash
python -B -m experiment_runner plan --config /private/new-candidate.json --output /new/candidate-plan.json --task sqlite-with-gcov
python -B -m experiment_runner prepare --config /private/new-candidate.json --output /new/candidate-run --task sqlite-with-gcov
```

在获得这一次真实启动的明确授权后，才执行：

```bash
python -B -m experiment_runner run --config /private/new-candidate.json --output /new/candidate-run --task sqlite-with-gcov
```

不要在本交付开发线程执行上述真实 run。若沿用的私有 pipeline 直接调用 construct_upstream，则必须传入 `research_candidate='pma_gap_evidence_v1'` 与 `memory_maintenance_policy='maintain-scoped-latest-no-review-v1'`，并保持 frontend/manifest/worker 身份链；不要只把 gate 改成 None。构造后的实际类应为 MaintenanceNoReviewAgent，且 MRO 不含 CitationGateMemoryAgent。

启动前核对：plan/config/worker_ready 都是同一维护策略；无 citation_review_gate/strategy；`maintenance_source_sha256` 与 committed_runtime_identity 的源码字节一致；P2 仍为标签原文选择，原别名/版本/交付协议不变。候选未证明语义更准确，13 个专项假客户端测试不能替代这次真实效果判断。

本次只跑这一条新候选完整 episode。报告原生逐项结果与 reward、Task 完成声明和实际可观察范围、P1 状态/GAP/经验变更、P2 选择与实际提醒送达、请求数/token/延迟、失败及清理。维护周期只允许 maintenance 和 selection：split/review/repair 应为 **0**；任何意外审核调用或旧自由合成提醒路径都算接线异常，不能当新候选效果。未知、解析失败、静默和有效干预分别报告。

评价输出只能在任务结束后用于效果评价，不可注入同一次 Task/PMA 输入。源码和归档身份必须分别绑定。不要把这次组合效果单独归因于提示优化或审核关闭，也不要因成功一次就称泛化成立。
