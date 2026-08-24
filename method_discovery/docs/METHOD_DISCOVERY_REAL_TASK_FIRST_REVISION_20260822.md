# 方法发现规划修订：Real-Task-First Incremental Monitor Discovery

日期：2026-08-22  
状态：经用户确认的当前阶段权威规划  
覆盖范围：覆盖 `METHOD_DISCOVERY_REDESIGN_PROPOSAL_20260821.md` 与 `METHOD_DISCOVERY_INTERACTION_AWARE_SELECTION_REVISION_20260822.md` 中冲突的 R1–R7 执行顺序、候选晋级门禁和离线实验权限；不改变论文研究问题、创新 A–D、无 checker 边界和 Final120 冻结划分。

## 1. 修订原因

此前虽要求候选最终通过真实 GenericAgent 分支，但仍允许离线压缩事件、静态 JSON、连续重放和 LLM judge 先决定候选晋级。这造成了实际偏移：已经由研究者提炼出问题的短 packet，被用于替代真实长任务中的发现、审议、干预和修复过程。

从本修订起，方法发现的选择权属于完整真实任务运行。离线事件与单元测试没有方法晋级权，也没有核心机制淘汰权。

## 2. 证据等级

### E0：工程正确性

- 单元测试、schema validation、确定性 fixture、接口测试；
- 只能证明实现按规格运行；
- 不能证明研究机制有效。

### E1：诊断与候选生成

- 压缩偏移事件、静态状态比较、轨迹重放、LLM judge、人工案例分析；
- 可用于发现失败模式、构造候选、解释真实运行；
- 不得单独晋级、淘汰或冻结论文方法。

### E2：方法发现证据

- `method_dev` 上的完整真实 GenericAgent 运行；
- treatment 在线只能看到公开任务、Agent 行为/声明、工具结果、普通环境观察和持久状态；
- native verifier 仅在终止后评价；
- 机制选择、保留和组合必须主要依据 E2。

### E3：阶段验证与正式证据

- `stage_validation` 用于方法冻结前的未见任务门禁；
- `final_holdout` 仅在方法冻结后运行；
- 不得根据 final holdout 修改方法。

## 3. 共同真实任务基线

所有机制从同一个朴素基线递增：

| 条件 | 含义 |
|---|---|
| B0 | 原始 GenericAgent；无监察者、无提醒、无外部研究状态、无在线 checker |
| B1 | 单一持续直接监察者；自由审议与自然语言工作档案，无强制语义 schema |
| B2 | B1 + 最小外部 Evidence-Carrying 语义锚点 |
| B3 | B2 + 只在证据范围模糊处触发的 sparse warrant/open diagnosis |
| B4 | B3 + challenge–response–verify 有界修复闭环 |
| B5 | B4 + 公开变更驱动的 append-only revision；决策边界作为独立开关消融 |

这是一条实验骨架，不预先宣称 B5 最好。每增加一项都必须可关闭；简单条件与复杂条件效果相当时保留简单条件。

## 4. 统一真实运行原则

1. **完整任务**：方法发现必须运行真实任务 Agent、真实工具、真实 workspace/Docker、真实终止与事后 native evaluator；不得用压缩 packet 代替主实验。
2. **同源比较**：同一批任务、模型、turn cap、工具、环境和基础 prompt；除目标机制外尽量一致。
3. **无 checker**：监察者不能读取 hidden tests、gold、reward 或 native verifier；verifier 结果不回流同次运行。
4. **自然基线**：B0 不注入额外 summary、状态字段、提醒或 research prompt。
5. **持续监察者**：B1–B5 默认同一个监察者模型与持续外部档案，不默认拆成小模型维护和强模型判断。
6. **真实行为优先**：Agent 口头接受不算修复；必须观察后续工具动作、测试、diff、产物或明确 UNKNOWN。
7. **对照与成本**：同时报告 task outcome、过程错误、false intervention、调用、token、延迟和美元成本。
8. **串行磁盘纪律**：大镜像任务串行运行；一道完成并保存产物后删除其临时镜像，再准备下一道。

## 5. 修订后的阶段

### R0：冻结数据与真实运行协议（已完成，协议本次修订）

保留 Final120 的 `method_dev / stage_validation / final_holdout` 和两个 pilot panel。偏移事件集降级为 E1 诊断资产，不是组件淘汰集。

### R1-Real-A：B0/B1 直接监察者可行性

服务创新：建立 A–D 的行为上界与最小 Agent 机制母体。  
核心问题：一个不受复杂 schema 约束、具有工具和持续自然语言档案的直接监察者，能否在真实长任务中自行发现偏移并改善 Agent 行为？

实施顺序：

1. B0 原始 GA smoke，确认环境、遥测和 post-hoc evaluator；
2. B1 监察接口 smoke，确认可沉默、可查看公开状态、可干预且不改变 B0 默认行为；
3. 在预先冻结的 4 个 `dev_pilot` 任务、至少 3 个来源上做 B0/B1 配对；
4. 逐轨迹审计发现、误报、干预、Agent uptake、二次纠偏和最终结果。

主指标：post-hoc native outcome、任务成功/部分成功、representation omission、unsupported closure、有效纠偏 episode、false intervention、token/call/latency。  
门禁：第一批 B0/B1 真实结果必须停下展示。B1 若无行为信号，不得通过静态 packet 分数强行进入复杂表示；若 B1 有效，其真实失败决定 R2–R5 的机制优先级。

### R2-Real-B：最小外部 Evidence-Carrying 语义锚点

服务创新：A，并以独立开关验证 B 的 append-only history substrate。  
比较 B1 与 B2，不先固定 T1、dual-layer 或 Semantic Cell 为唯一表示。

最小强制锚点仅包括：不可变原始契约引用、全局开放 obligation、当前局部工作、关键公开证据索引、未解决问题、最近干预与实际行为响应、旧判断的修订引用。字段内容允许自然语言；额外结构只在真实失败证明必要时加入。

门禁：必须在真实任务中减少监察者自身的 obligation 丢失、局部隧道或错误闭合，且不能仅因更多 token 得益。静态表示有效率只能作为工程指标。

### R3-Real-C：Sparse Warrant 与开放诊断

服务创新：A、B。  
比较 B2 与 B3。warrant 只在完成声明、局部证据提升为全局结论、自写测试/实现共适应、UNKNOWN 被当作否定、新旧证据冲突等真实事件触发。

监察者可自主查阅公开 diff、测试、历史实现和日志；不能把 evidence citation 当作全文蕴含。必须区分“未观察到”与“没有发生”，允许 UNKNOWN。

门禁：相对 B2 改善真实 evidence-scope 判断或减少 unsupported closure；同时测量错误 warrant、过度推断、false blocking 和成本。不得要求每个 claim 每轮生成完整 argument graph。

### R4-Real-D：Challenge–Response–Verify 有界修复闭环

服务创新：B、D。  
比较无干预、一次性提醒和 B4 闭环。干预 episode 必须包含 challenge、Agent response、后续行为、residual 和 release/escalate；口头接受不能闭合。

门禁：在多个完整任务上比最佳一次性干预提高真实 behavioral uptake/repair，并在等调用或等 token 比较后仍有优势。

### R5-Real-E：Append-Only Revision 与决策边界独立消融

服务创新：B、C。  
先单独比较有/无公开变更驱动 revision，再分别消融 global completion、local/global、test-oracle 和可选 high-risk transition boundary。不得把 revision、dependency graph 和所有 gate 一次堆叠。

门禁：revision 必须在连续真实运行中改善冲突重开/旧证据保留；每个 gate 必须减少对应 unsupported transition，且不能产生严重 false blocking。

### R6：预算化 Active View 与交互感知筛选

服务创新：D。  
只对 R1–R5 已获得 E2 信号的候选做等 visible-token/call/cost 比较。必须比较 static truncation、完整 ledger/history、PMA-style reminder、always-visible state、等频随机选择和 query/use-site-conditioned active view。

交互救援候选必须有真实轨迹支持的互补机制假设和一次预注册机会；不得用离线分数或叙事完整性无限保留。

### R7：真实任务最小组合、未见任务与方法冻结

在 `dev_pilot` 完成重复、组件关闭、主效应与关键二阶交互；随后使用 `validation_gate` 做未见任务和等预算门禁。最终方法按真实效果支持的最小组合冻结。

### Stage 7：正式多来源实验

只有 R7 冻结后才运行 final holdout treatment。正式报告多来源、多模型、成本、失败类型、false blocking、消融和统计不确定性。

## 6. 候选选择与停止规则

- E0/E1 可以发现实现错误、提出新候选和解释反例，但不能单独晋级或淘汰核心机制。
- 第一批真实 B0 baseline、B0/B1 对照、任何机制首次真实增益/退化、成本异常、native evaluator 与过程判断不一致时必须停止汇报。
- 候选束每类最多保留：simple baseline、E2 Pareto candidate、一个有真实互补证据的 interaction rescue。
- 同一任务逐例调出的规则不得直接推广；候选必须跨任务、跨来源验证。
- 若 B1 已达到复杂方法效果，优先保留 B1；若 B0 已足够，接受无监察收益或条件性收益结论。

## 7. 现有静态实验的重新分类

- `r0_event_corpus`：E1 故障 taxonomy、回归 fixture 与案例索引；
- R1 v1/v2、T1、Semantic Cell C1–C3：E0/E1 工程/机制诊断；
- LLM judge：E1 辅助阅读，不是方法评价器；
- 人工监察体验：E1 formative mechanism reference，不是可部署方法结果；
- 任何由上述静态实验产生的“淘汰/晋级”裁决，自本修订起都只作为候选优先级建议，必须由 E2 真实任务重新裁决。

## 8. 当前停止点

当前尚未开始 R1-Real-A 实现。下一阶段必须先复核 B0 默认路径、B1 持续监察接口、4-task 配对 panel 和运行成本；经阶段授权后再开发与运行。
