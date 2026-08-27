# M2 收束与 M3 入口裁决（2026-08-28）

## 裁决

M2 保留 **M2-C scoped semantic-impact revision**，以提交 `edddba9`、标签
`m2-c-structural-gate` 作为 M3 的唯一工程父版本。M2-D 不进入累计方法：其新增的直接依赖
失效通道在共同真实任务的 101 个监察边界内没有触发，也未提供相对 C 的独立收益；D 的
未提交实现已回退。

本裁决只完成 M2 候选收束，不声称 C 已获得正式论文级充分验证，也不授权运行
`final_holdout`。

## 共同任务和在线边界

- 任务：`roadmapbench:fyn-2.2.0-roadmap`（Fyne 2.2）。
- Task Agent：Claude Opus 4.6。
- Monitor：GPT-5.6-sol high。
- Agent turn 上限：500；Harbor agent timeout：10,000 秒。
- 在线信息仅包括公开任务、Agent 轨迹、工具结果、工作区和持久状态；没有在线 checker、
  hidden test 或 native verifier 泄漏。
- native verifier 只在异常终止后运行，不能反向作为本次监察决策证据。

## M2-C 保留依据

M2-C 在共同任务 R2 中证明了结构机制可以：

1. 将公开变化记录为 `cause public_evidence -> target obligation -> effect`；
2. 保留可审计的影响历史和 pending 状态；
3. 避免 M2-A 对 anchor-only 变化进行机械版本推进所造成的状态污染；
4. 在真实 repair/release 循环中保持监察者的语义判断，而不把 schema 变成在线 checker；
5. 允许 UNKNOWN、contested 和 revalidation，不凭状态条目自动建立完成结论。

已有证据仍是方法发现证据，而不是最终效果结论。C 的首次运行没有自然完成整题，故不能
用其局部成功冒充 native-verifier 胜率。

## M2-D 真实运行结果

### R1

R1 因 provider `403 SUBSCRIPTION_NOT_FOUND` 在方法开始前失效，只保留为工程异常，不参与
候选比较。

### R2

R2 成功进入真实任务并持续运行，最终触发 Harbor `AgentTimeoutError`：agent execution 在
10,000 秒上限结束，GA return code 为 143，未完成协议轮次。超时后的 verifier 得到
`1/7 phases`、reward `0.181818...`，但该数值不属于有效 D 方法成绩。

运行事实：

- 监察决策：101 次，其中 `SILENT=92`、`HOLD=8`、`RELEASE=1`；
- C 语义影响通道：history 19、终止时 pending 3；
- D 新增直接依赖失效通道：history 0、pending 0；
- Task Agent provider usage：102 次调用；
- Monitor provider usage：155 次调用；
- Monitor 可见 input tokens：3,359,289；output tokens：352,417；
- D 没有重现 A 式 anchor-only revision pollution，但也没有显示新增通道价值。

轨迹中有真实有效的监察行为：阻止无行为效果的表面 API、阻止非判别性测试、发现 Go
跨包可见性错误，并持续保留未证实的刷新 obligation。与此同时，Target 4 在构造刷新
探针、修复夹具和追查观测路径上长期不收敛。该现象不能归因于在线 checker，也不能证明
D 优于 C；它直接形成 M3 的失败驱动证据。

## 候选裁决

- M2-A：不保留。自动版本推进产生明显 anchor-only pollution。
- M2-B：不保留为单独母体。覆盖面不足，真实变化不一定表现为已建直接证据对象的显式撤销。
- M2-C：保留。当前结构收益最清楚、污染较少，并维持语义判断自由。
- M2-D：不保留。组合中的 B 通道在共同任务未激活，只有 C 通道工作，却增加实现与叙事复杂度。

按照“最小有效组合”原则，当前证据支持 C，而不是为了机制完整性保留 D。

## M3 入口问题

M3 不再重复发明 M2 状态表示，而是在 C 的可修订证据状态之上解决：

1. 当前未知或冲突是否值得立即调查；
2. 下一次观察预计能改变哪个决策；
3. 何时应让 Agent 自然推进，何时应在意图阶段 HOLD；
4. 连续调查何时已边际价值不足，应换证据路径、暂存 UNKNOWN 或恢复根任务；
5. 如何防止局部 repair/probe episode 吞噬根任务和预算；
6. 如何在停止调查时不把“未观察到”错误改写成“未发生”或“已经完成”。

M3 的增量必须可以单独关闭，并在完整真实任务中同时检查调查收敛收益、错误阻断、M0/M1
能力退化和成本。不得通过固定某个 Fyne 探针规则解决本次个例。

## 原始证据

- C 轨迹报告：`method_discovery/docs/M2_C_FYN220_R2_SEMANTIC_IMPACT_GATE_20260827.md`
- D 预注册：`method_discovery/docs/M2_D_HYBRID_REVISION_PREREGISTRATION_20260827.md`
- D R2 run：`long_context_bench/output/m2_real_tasks/m2a_first_gate/m2d_hybrid_revision/fyn-2.2.0-roadmap/runs/m2-m2d_hybrid_revision-fyn-2.2.0-roadmap-r2/`
- D R2 trial：`long_context_bench/output/m2_real_tasks/m2a_first_gate/m2d_hybrid_revision/fyn-2.2.0-roadmap/jobs/m2-m2d_hybrid_revision-fyn-2.2.0-roadmap-r2/fyn-2.2.0-roadmap__RWT4aAD/`
- 异常：上述 trial 的 `exception.txt`
- 状态：上述 trial 的 `agent/m0_monitor/m1_workspace.json`
- 决策：上述 trial 的 `agent/m0_monitor/decision_0001.json` 至 `decision_0101.json`
- 成本事件：上述 trial 的 `agent/research_events.jsonl`

## 工程冻结状态

- 接受父版本：`edddba9` (`m2-c-structural-gate`)。
- D 外部开关 `GA_M2_HYBRID_REVISION_ENABLED` 及其组合实现、转发和测试已从工作树移除。
- M3 必须从 C 的单一语义影响通道递增，不得重新带回 D、rejected sparse wake、
  bounded-UNKNOWN 或在线 checker。
