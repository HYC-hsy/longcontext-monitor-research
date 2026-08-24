# 第一篇论文的更新主线、研究问题与候选方法

更新时间：2026-08-16  
状态：全量普查后的当前主规格；方法尚需小规模判别实验  
替代范围：替代旧文档中将“动态任务状态＋主动提醒”视为第一篇核心创新的部分

## 1. 一句话论文主线

> 研究长程Agent的任务状态何时不再足以支持正确行动和完成判断，并提出一种反例驱动、携带验收证据的任务状态，使Agent只在未来义务被充分支持时闭合任务，在状态或证据不足时选择继续、验证、修复、提醒或升级。

## 2. 具体研究问题

### RQ1：行为充分性

什么信息必须进入紧凑任务状态，才能在未来关键决策点保持与完整历史/参考状态一致的行为？

研究对象包括目标、约束、终止义务、依赖、状态修订和未来使用条件；评价标准不是文本重构，而是行动与局部verifier结果。

### RQ2：证据充分性

当Agent声称某项义务已完成时，什么证据足以支持该声明？如何区分import、文件存在、自写测试等弱代理与真正的行为验收？

### RQ3：安全闭合

当存在未决义务、UNKNOWN状态、弱证据或失效依赖时，系统怎样阻止过早完成，同时避免无限检查和不必要干预？

### RQ4：选择性恢复

在固定token、调用、延迟或美元预算下，应选择继续执行、局部验证、修复表示、提醒、重新观察、升级还是静默？

第一篇优先回答RQ1–RQ3，并以非训练的保守控制器回答RQ4。学习干预价值留到第二阶段。

## 3. 问题形式化

令长程历史为`H_t`，紧凑任务状态为：

\[
S_t=\{(o_i,z_i,a_i,e_i,d_i,v_i)\}_{i=1}^{n_t}
\]

- `o_i`：obligation，未来必须满足的事实、动作、约束或终止条件；
- `z_i`：`UNKNOWN/ACTIVE/PROVISIONAL/SATISFIED/INVALIDATED`；
- `a_i`：acceptance predicate，满足该义务需要什么可观测条件；
- `e_i`：当前支持证据及provenance；
- `d_i`：依赖关系；
- `v_i`：版本、新鲜度和最后检查时点。

完成条件为：

\[
\mathrm{Complete}(S_t)=1
\iff
\forall o_i\in O_{terminal},
z_i=\mathrm{SATISFIED}
\land e_i\succeq\tau_i
\land\mathrm{DepsValid}(o_i).
\]

`e_i \succeq \tau_i`表示证据达到义务特定的最低验收强度。证据不必压成一个全局标量，可以是task-specific偏序。

行为充分性只针对预声明probe/action family `Q`：

\[
D_Q(S_t,H_t)=
\mathbb{E}_{q\sim Q}
L(\pi(q,S_t),\pi(q,H_t)).
\]

不声称`S_t`是环境的全局POMDP充分状态，只声称它在限定决策族上具有可测的低行为失真。

## 4. 核心创新候选

### 创新A：Evidence-Carrying Task State

普通summary、RAG或PMA memory bank主要保存内容；本方法把“义务”和“支持义务状态的证据”作为一等对象。`completed`不是自由文本结论，而是需要provenance、acceptance predicate和证据强度支持的状态。

预期贡献：统一表示“忘了未来义务”和“仍记得义务但错误认为已经完成”两类失败。

### 创新B：Counterexample-Guided Versioned State Revision

不让LLM凭语义重要性任意重写状态。公开可见的对象变更与冲突建立版本边界：旧版本证据进入不可变历史，新版本回到UNKNOWN并只接受新版本观察；同版本PASS/FAIL冲突保持contested，Agent声明和普通`code_run`不能洗掉负面证据。

Stage 6C已在DuckDB成功对照上验证该机制：V0把旧失败与修复后的22/22 PASS混为contested；版本化修订将当前正确性恢复为observed，同时完整保留旧失败来源。该结果支持“版本化状态修订”为创新B的核心。

由反例动态增加acceptance predicate仍保留为**可弃权扩展**：只有公开反例暴露原predicate未覆盖的验收维度时才能增加；已有predicate覆盖反例时必须不扩展。当前真实任务尚未证明其独立增益，因此不得把predicate expansion写成已成立的核心贡献。

### 创新C：Evidence-Gated Completion Kernel

在`no_tool`、最终回答、提交和`completed`转换前运行条件性确定的kernel：检查未决义务、弱证据、UNKNOWN、失效依赖和未完成终止动作。kernel只对结构化状态和可机械检查的predicate提供保证，保证条件于语义前端抽取正确。

### 创新D：Typed Recovery Actions

恢复动作不只有reminder/silence：

| 缺口 | 动作 |
|---|---|
| obligation未进入状态 | REPAIR |
| 状态存在但未控制行动 | REMIND |
| 完成证据太弱 | VERIFY |
| 工作尚未执行 | CONTINUE |
| 环境证据过期 | REOBSERVE |
| 无可靠判定 | ABSTAIN/ESCALATE |
| 状态充分 | SILENT/ALLOW_COMPLETE |

第一篇使用规则/保守控制器；第二篇再学习选择策略。

## 5. 当前首选方法组合

### 主组合：P1 + 改造后的P3 + 轻量P2

1. **Obligation Compiler**：从任务、观察和工具结果编译目标、约束、终止义务、依赖和acceptance predicate；
2. **Evidence Ledger**：维护证据、来源、强度、版本、新鲜度和依赖；
3. **Versioned State Reviser**：由公开变更/冲突推进版本、重开UNKNOWN并保存不可变证据历史；predicate expansion默认弃权，仅在公开反例暴露缺失验收维度时启用；
4. **Completion Kernel**：完成前拒绝unsupported closure；
5. **Selective Recovery Controller**：以非训练规则选择continue/verify/repair/remind/reobserve/escalate/silent。

P4不作为V0核心，只在明确动态环境任务中由freshness风险触发。

## 6. 第一轮必须竞争的替代方案

- 原始GenericAgent；
- 普通滚动summary；
- RAG；
- always-visible完整任务描述或完整state；
- PMA式reminder/silence；
- 静态obligation checklist；
- always verify；
- evidence ledger但无completion gate；
- completion gate但无反例细化；
- 完整候选方法；
- native-verifier oracle上界。

最关键竞争不是与“无memory”相比，而是：

> 反例细化是否超过静态checklist，选择性验证是否超过always verify，证据门控是否超过结束前简单提醒一次。

## 7. 最小实验包

首批15–20个可分叉checkpoint：

- Roadmap near-miss 8–10个：`spc-3.4`、`fbr-2.43`、`glz-6.1`、`glz-7.0`、`vbt-1.1`等；
- MemGym omission 5–7个；
- T071和arxiv digest；
- 2–3个成功正对照。

每个packet冻结：obligation、required-at、当前state、evidence、baseline action、workspace/env、local/native verifier和替代解释。

指标：native success、obligation coverage、unsupported completion rate、恢复的near-miss、false blocking、额外tokens/calls/latency/USD，以及equal-budget结果。

## 8. 淘汰条件

- 静态checklist与完整方法相当：反例细化不能作为核心创新；
- always verify同预算更好：选择性控制没有贡献；
- completion gate只增加时长而不提升success：问题主要是能力而非闭合控制；
- 补回MemGym遗漏事实不改变最终答案：note recall不能代理行为充分性；
- 优势只来自额外强模型调用：不能声称算法优势；
- P4重新观察不改变动作：继续维持扩展地位。

## 9. 可声明与不可声明

若实验成立，可以声明：

- 识别并操作化completion-evidence drift；
- 提出反例驱动、携带证据的任务状态；
- 提出证据约束的completion kernel和typed recovery；
- 在严格等预算下减少unsupported completion并提升native success。

当前不可声明：

- 首次发现behavioral state decay；
- 首次维护动态execution state或主动提醒；
- 已经证明28/31可由本方法挽救；
- 旧轨迹足以估计干预因果价值；
- 这是全局充分状态或有POMDP最优性保证。

## 10. 三阶段论文路线

1. 第一篇：非训练的evidence-carrying state、反例细化和completion control，证明方向与机制有效；
2. 第二篇：利用分叉数据学习access risk、evidence adequacy、干预价值和恢复动作；
3. 第三篇：在线适应不同Agent、任务、环境变化和监督预算，形成长期自适应治理。
