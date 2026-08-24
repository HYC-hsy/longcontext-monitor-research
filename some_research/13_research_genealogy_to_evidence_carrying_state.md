# 研究脉络：从动态记忆与主动提醒到证据携带的任务状态

更新时间：2026-08-16  
用途：保留论文问题形成、创新收束和关键转向的可引用脉络  
原则：区分原始灵感、公开近邻、经典理论、代码现实和本地实证，不事后把路线描述成一次性设计出来。

## 1. 原始研究愿景

最初关注的是Agent在长程任务中逐渐偏离目标。核心直觉是：若存在一种“完美知识表示”能够表达Agent未来需要记住什么，并能预测这些信息何时不再控制行为，就可以在遗忘后或使用前重新注入，从而降低偏移。

`01_bytetech_ideas_with_excerpts.md`提供了动态状态、知识更新、事件/行动/约束/结果等工程灵感；`04_conversation_evolution_and_disambiguation.md`记录了从宽泛长程偏移到“可由状态维护和提醒改善的子集”的对话收束。Karpathy的LLM Wiki进一步启发了“持续维护可修订外部知识结构”，但它不是本项目方法的新颖性来源。

初始候选因此是：

```text
旁路监察者读取日志
→ 维护动态任务状态
→ 预测Agent何时可能不再访问重要信息
→ 在关键时点主动提醒
```

这一阶段形成了`03`、`05`、`06`和`07`中的监察者、状态表示、非训练第一篇与后续学习式预测路线。

## 2. 第一次重要纠偏：从benchmark建设转向方法研究

`long_context_bench`最初容易被理解成研究目标本身，但项目真正目标是解决GenericAgent长程执行偏移；benchmark只是实验对象和证据来源。三阶段路线由此确立：

1. 第一篇先用非训练方法证明机制有效；
2. 第二篇学习哪些变量决定访问失败和干预价值；
3. 第三篇做在线自适应监督与预算治理。

这一阶段同时确立best-paper标准：方法创新必须有原始理论/经典方法依据、清楚数学对象、强实验和可证伪淘汰条件，不能只做prompt工程。

## 3. PMA撞车：原始核心创新被封锁

对`Remember When It Matters`（PMA）的深审是第一次根本转向。它已经研究behavioral state decay，使用独立Memory Agent维护status/knowledge/procedural state，并在每步决定reminder或silence。它与“动态状态＋主动提醒”的问题、机制和干预位置正面重合。

随后审计发现：

- PM-Bench覆盖future cue、取消、改期、完成和主动监测；
- MemoryArena、MAGE、MemCon、MemAct、TARL、LongHorizon-Harness覆盖execution state、行为收益、revision、外部验证与审计；
- Self-GC覆盖context-object生命周期和future-dependency pruning；
- CMI形式化行为/因果效用而非语义相关性；
- Zep、Hindsight、SodaMem、WorldDB、TME覆盖revision、invalidation和temporal graph。

关键近邻追溯表：

| 工作 | 标识 | 它封锁/启发了什么 | 本地深审入口 |
|---|---|---|---|
| Remember When It Matters / PMA | arXiv:2607.08716 | behavioral state decay、execution-state memory、reminder/silence | `exploration/pma_deep_audit_and_reproduction.md` |
| LongHorizon-Harness | arXiv:2608.01964 | verified external task state与Manage–Execute–Audit | `exploration/frontier_methods_2024_2026.md` |
| Self-GC | arXiv:2607.00692 | context-object生命周期、future-dependency pruning | `exploration/frontier_methods_2024_2026.md` |
| DeMem | arXiv:2605.10870 | decision-centered rate–distortion，封锁宽泛行为充分性首次声明 | `exploration/round3_frontier_claim_audit.md` |
| Causal Memory Intervention | arXiv:2605.17641 | causal usefulness而非semantic relevance；依赖gold/scorer | `exploration/round3_frontier_claim_audit.md` |
| AgentSpec | arXiv:2503.18666 | 动作前DSL predicate/enforcement，封锁宽泛symbolic shield | `exploration/round3_frontier_claim_audit.md` |
| Progent | arXiv:2504.11703 | 自动生成并动态更新tool policy | `exploration/round3_frontier_claim_audit.md` |
| VeriGuard | arXiv:2510.05156 | temporal/runtime monitor近邻 | `exploration/round3_frontier_claim_audit.md` |

完整论文、benchmark、代码和claim风险仍以`exploration/frontier_methods_2024_2026.md`与`exploration/round3_frontier_claim_audit.md`为准，本表只保留收束主链。

因此`09_post_audit_pivot_and_claim_lock.md`正式封锁：不能再把动态execution state、future cue、行为收益选择或reminder/silence作为宽泛首次创新。PMA成为必须正面对比的基线。

PMA代码深审同时暴露了可研究缺口：主配置每步调用monitor；每个memory step是两次强模型调用；官方成本统计遗漏这些memory calls；注入率从12.5%到90.3%，部分任务近乎always-on；自由文本bank缺少严格provenance和验收语义。这些首先是工程/证据缺口，不自动构成新方法。

## 4. 经典理论与形式化候选

为避免“撞车后换名词”，项目并行调查了经典理论：

- POMDP与决策充分状态：提供总问题形式，但本身不构成方法；
- rate–distortion与information bottleneck：启发以行为失真和状态成本衡量表示；
- Value of Information：启发干预净价值，但无gold、无分叉时一般不可识别；
- event-triggered control：启发选择性触发，但不能无条件声称稳定性；
- runtime verification、temporal logic、TMS/AGM：支持版本化义务、失效传播和条件性确定保证；
- working set/caching：提供强baseline和资源视角；
- active sensing：区分旧记忆激活与重新观察可变世界；
- CEGAR：启发由可验证反例逐步细化状态抽象，而非拍脑袋规定schema。

理论压力测试形成几个纪律：

- token不是mutual information；
- LLM自评分不能冒充VoI；
- 无gold、无规范、不可branch、无未来观测时，干预收益符号不可识别；
- symbolic kernel的保证条件于语义前端解析正确；
- 只追求预声明probe family上的restricted behavioral sufficiency，不声称全局充分状态。

## 5. 文献终审后的四个候选包

第三轮形成：

- P1：反例驱动的行为充分状态编译；
- P2：verifier-bounded保守干预；
- P3：证据携带、可修订的commitment shield；
- P4：风险触发的主动再观察。

前沿claim audit进一步限制宽泛声明：DeMem阻断宽泛decision-centered rate-distortion，CMI/Memory-R2阻断宽泛causal memory value，AgentSpec/Progent阻断宽泛动态policy shield。相对安全的方向是限定决策族、无gold局部verifier、last-effective intervention window和可审计的action-level evaluation。

到这一步，P1是理论主候选，P4较有结构差异，P2缺反事实数据，P3覆盖窄且近邻多；但仍缺本地真实频率证据。

## 6. GenericAgent代码与历史产物审计

对`GenericAgent-main`和M14产物的审计给出两个关键现实：

1. Final120没有独立campaign，而是一一映射到M14-140的成功产物；`completed`表示artifact-valid，不表示task正确；
2. 当前`llm_before`记录loop delta，发生在Session append、compress/trim和provider转换之前，不能恢复每轮actual provider context。

因此旧轨迹能用于行为分析和候选定位，却不能严格证明某事实在哪一轮从模型可访问上下文消失，也不能无API执行真实提醒反事实。未来实验必须增加`provider_request_ready`观测、干预记录和可恢复checkpoint。

少量早期案例曾支持P4和P1假设：会议协商中出现日期冲突与再观察；Omega Corp出现取证失败后提前结束。但这些只能证明候选机制存在，不能决定频率。

## 7. Final120全量普查：研究主线第二次根本转向

逐题普查得到：62证据不足、28过早完成、12规划/能力、9成功对照、8确认表示遗漏、1确认承诺违反。

三个来源内结果改变了优先级：

1. MemGym 7/10表示遗漏，证明P1对象频繁存在；
2. RoadmapBench 28/31并没有忘记目标，而是把弱代理当成完成证明；
3. T071提供自然的终止义务表示遗漏链，arxiv digest提供最终契约违反。

全量数据因此否定了“第一篇主要研究提醒时机”的优先级。真实执行中更突出的共同问题是：

> 任务状态要么遗漏未来义务，要么保留义务却没有维护足以支持完成判断的证据。

P4因没有confirmed staleness primary而降级；P2仍缺paired causal evidence；P1和改造后的P3开始能够由同一对象统一。

## 8. 当前收束：Evidence-Carrying Task State

当前方法母体不是普通memory bank，而是：

```text
obligation + status + acceptance predicate
+ evidence + provenance + strength
+ dependency + revision + freshness
```

verifier反例驱动两种细化：

- 表示细化：加入遗漏的future-required obligation；
- 验收细化：弱代理不能区分成功与失败时，加强acceptance predicate或evidence要求。

completion kernel在结束前检查未决义务、弱证据、UNKNOWN和失效依赖；恢复控制器选择continue、verify、repair、remind、reobserve或escalate。

这条路线的理论根基分别来自：

- behavioral sufficiency / restricted decision equivalence：定义状态质量；
- CEGAR：由反例细化状态和验收；
- runtime verification / TMS：提供版本化义务和条件性保证；
- selective decision / abstention：证据不足时拒绝闭合；
- VoI只作为未来学习/选择层，不在无分叉时冒充已估计因果价值。

## 9. 当前创新边界

潜在新贡献不是首次维护状态、首次主动提醒或首次运行verifier，而是以下组合是否成立：

> 面向长程Agent，将行为充分的obligation abstraction与evidence adequacy共同作为任务状态，通过可验证反例联合细化表示和完成predicate，并在严格预算下选择性阻止unsupported completion。

## 10. Stage 6C后的第二次收窄：从宽泛反例细化到版本化状态修订

ECS V0在DuckDB成功轨迹上出现了一个重要反例：早期Q5/Q7/Q8失败与最终修复后的22/22 PASS被合并在同一主体版本内，导致最终状态仍为contested。这表明“保存全部证据”本身不够；状态必须区分证据属于哪个被修改对象版本。

Stage 6C据此引入公开变更驱动的版本边界。最终实验中，旧失败被保存在version history，最终patch后的观察只更新新版本，当前正确性由V0的contested恢复为observed；而同版本PASS→FAIL→PASS仍保持contested，避免用后来的正面观察洗掉真实冲突。

同一阶段也证伪了更宽的叙事：不受约束的LLM曾从单例提出“非结构变更保持正确性”的过度泛化规则；限制为公开反例签名后，DuckDB自动前端正确地产生零个新predicate，因为原“22项全部通过”已覆盖这些反例。因此创新B不再宽泛声称动态扩展acceptance semantics，而冻结为：

> 公开变更与冲突驱动的版本化任务状态修订；acceptance-predicate扩展是默认弃权、等待真实缺失维度证据的可选扩展。

这次收窄遵循最小有效组合原则：保留真实轨迹已证明必要的版本化机制，不为论文叙事强行保留尚无独立增益的动态predicate扩展。

这仍需专门与AgentSpec、Progent、LongHorizon-Harness、TARL、PMA及runtime verification近邻做不可等价审计。若最终退化为静态checklist加结束前测试，则创新不成立。

## 10. 下一步证据链

1. 对completion verification/evidence-carrying agent state做专项近邻审计；
2. 构造15–20个原子checkpoint packets；
3. 先比较static checklist、always verify、PMA reminder与完整方法；
4. 用native verifier做paired branch；
5. 严格报告equal-token/call/dollar、false blocking和success；
6. 只有反例细化和选择性门控都显示独立收益，才锁定最终算法与论文声明。

## 11. 文档对应关系

- 初始灵感：`01`、`04`；
- 初始项目规格：`03`、`05`、`06`；
- 三阶段路线：`07`；
- best-paper探索协议：`08`；
- PMA撞车与声明封锁：`09`；
- PMA后续验证：`10`；
- 全量实证转向：`11`；
- 当前论文主规格：`12`；
- 详细调查：`exploration/`；
- 逐题证据：`exploration/full_survey/`。
