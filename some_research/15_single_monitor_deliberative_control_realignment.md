# 单一持续监察者与审议式控制：方法架构补充裁决

更新日期：2026-08-21  
状态：经用户确认的暂行架构约束；补充 `12_updated_paper_thesis_and_method_candidates.md` 与 `14_no_checker_realignment_and_method_convergence.md`，不替代其研究问题和无 checker 边界。

## 1. 裁决

当前方法默认采用**一个具有持续身份和持久任务状态的监察者**，不把“小模型日常维护、强模型关键判断”的双模型交接作为默认架构。

原因：

1. 两个模型之间需要压缩和传递状态，会引入额外的信息损失、责任边界和一致性问题；
2. 长程监督依赖对 obligation、证据来源、历史 challenge 和 residual 的连续认知，频繁交接可能破坏这种连续性；
3. 日常状态维护主要是增量事件归档、索引和局部修订，其 token 成本未必足以抵消双模型交接成本；
4. 论文首先需要证明机制有效，不能让模型能力差异成为主要混杂因素。

小模型仍可在后续作为成本消融或部署优化比较，但其结果不得成为第一篇论文方法成立的前提。

## 2. “同一监察者”不等于“每轮完整重读并深度推理”

持续认知由外部可审计状态承载，而不是假设模型在调用之间保有不可见的永久心智。默认控制方式是：

```text
公开事件流
  → 确定性归档、索引和 delta 计算
  → 同一监察者更新持久双层状态
  → 无关键变化时保持静默
  → 关键事件出现时，同一监察者读取 query-conditioned active view
  → 进行较深诊断或进入 repair loop
```

因此节省成本的主要手段是：

- 增量更新，而不是反复重建全部状态；
- 只传递变化和相关证据索引，而不是完整历史；
- 事件触发较深审议，而不是固定每轮长推理；
- 复用同一持久 ledger、版本历史和 challenge/residual；
- 静默也是显式动作，低风险阶段不生成冗长提醒。

## 3. 连续认知的表示

监察者的连续性至少由以下对象保证：

- declarative task state：obligation、constraint、acceptance semantics、status、evidence、dependency 和 version；
- procedural control state：intent、planned/observed action、artifact、test oracle、risk、challenge、response 和 residual；
- immutable event/evidence archive：完整公开事件与产物索引；
- active view：针对当前决策点，从归档和双层状态构造的有限视图。

模型调用可以间歇发生，但这些对象必须持续存在、可审计、可修订。不能把“同一模型”误写成“依赖模型隐式记忆完整历史”。

## 4. 成本假设必须实验验证

用户提出“平时维护更新可能花不了多少 token”是合理假设，但当前不能直接当作事实。方法发现阶段需要测量：

- 每次增量维护的输入/输出 token；
- 无关键事件时的静默比例；
- active view 相对完整历史的压缩率；
- 状态更新和深度审议各自的调用次数、延迟和成本；
- 单一监察者相对双模型交接的信息保持率与最终效果。

默认主比较应控制模型能力：同一监察者的每步完整审议、事件触发审议、completion-only 审议和固定频率审议。小模型 shadow maintainer 只作为附加消融。

## 5. 与创新 A–D 的关系

- 创新 A 的双层 Evidence-Carrying State 是同一监察者的持久认知载体；
- 创新 B 的 versioned challenge/residual 保证跨轮纠偏连续性；
- 创新 C 的 decision boundaries 决定何时不能静默或放行；
- 创新 D 的预算化控制主要选择审议时机、active view 和恢复动作，而不是默认选择另一个模型。

这一裁决保留监察者的开放式诊断能力，同时把结构约束放在状态、证据和交互接口上，不把监察者退化成固定规则 checker。

## 6. 可证伪条件

如果实验发现：

- 单一监察者的日常维护成本接近每步完整审议；
- 持久状态不能缓解上下文膨胀；
- 小模型交接在等预算下没有明显信息损失且效果更好；

则双模型分层可以重新成为部署候选。但这属于实验后选择，不预先写入核心算法。

