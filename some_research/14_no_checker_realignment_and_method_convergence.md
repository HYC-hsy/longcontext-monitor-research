# 无 Checker 约束修订：保持 Evidence-Carrying Task State 主线

更新时间：2026-08-18  
状态：这是对 `12_updated_paper_thesis_and_method_candidates.md` 的约束修订，不替代其研究问题和创新 A–D。

## 1. 当前权威关系

- 论文主规格：`12_updated_paper_thesis_and_method_candidates.md`。
- 形成脉络与实证依据：`11_final120_empirical_pivot.md`、`13_research_genealogy_to_evidence_carrying_state.md`。
- 本文只修正一个错误实现假设：核心方法不得依赖可靠在线 checker、gold answer、隐藏测试或 native verifier。

Final120 得到的 completion-evidence drift 发现继续有效；Evidence-Carrying Task State、Counterexample-Guided Versioned State Revision、Completion Kernel 和 Typed Recovery Actions 继续是第一篇论文的创新候选。

## 2. 保持不变的研究问题

> 长程 Agent 的任务状态会发生两类关键失真：未来仍需使用的义务可能从表示中遗漏；义务也可能仍被保留，但 Agent 使用不足或不等价的证据将其错误标记为完成。如何维护能够同时避免表示遗漏和错误闭合的可修订任务状态，并在偏移发生时采取合适的恢复动作？

两类失真分别是：

```text
obligation missing from state
    → representation omission

obligation present, but weak/non-equivalent evidence closes it
    → unsupported closure / completion-evidence drift
```

“动态状态＋主动提醒”本身已被 PMA 等工作覆盖，不能作为宽泛首次创新；但这不意味着论文应退回为 PMA 的 memory selection 升级。

## 3. 保持不变的创新候选

### A. Evidence-Carrying Task State

联合维护 obligation、status、acceptance predicate、evidence/provenance/strength、dependency、version 和 freshness。它统一表达表示遗漏与错误闭合，而不是普通自由文本 memory bank。

### B. Counterexample-Guided Versioned State Revision

公开可见的对象变更与冲突驱动版本推进和状态重开：旧版本证据保留为不可变历史，新版本回到UNKNOWN；同版本冲突保持contested，Agent声明或普通命令成功不能洗掉负面证据。Stage 6C已在真实DuckDB轨迹上验证该核心。acceptance-predicate扩展只保留为可弃权扩展：仅当公开反例揭示原predicate未覆盖的验收维度时才允许增加；目前没有真实任务证据支持其独立贡献。

### C. Evidence-Gated Completion Kernel

在结束、提交或完成声明前，检查未决义务、当前支持关系、冲突、失效依赖与 UNKNOWN。Kernel 检查的是“当前可观察证据是否足以支持该状态转换”，不是调用完美 checker 判定任务真伪。

### D. Typed Recovery Actions

根据偏移类型选择 REPAIR、REMIND、VERIFY、CONTINUE、REOBSERVE、ABSTAIN/ESCALATE 或 SILENT，而不是只有 reminder/silence。

当前主组合仍是 P1 + 改造后的 P3 + 轻量 P2；P4 是动态环境扩展，是否进入最终方法由实验决定。

## 4. “证据”不等于“可靠 Checker”

核心方法可使用的在线输入只有：

- 公开任务要求；
- Agent 动作和完成声明；
- 工具调用与工具返回；
- 文件、进程、服务和环境的普通可观察结果；
- 状态对象之间的来源、版本、依赖和冲突关系。

这些输入只能产生分级认识状态：

```text
claimed → observed → supported
             ↘ contested / unknown / superseded
```

- Agent 自述只能支持 claimed；
- 文件存在或命令成功是 observed，不能自动证明完整语义；
- 多项相关观察可以形成 supported，但仍只针对声明的局部 predicate；
- 出现矛盾时进入 contested 或 reopened；
- 无法判断时保留 UNKNOWN，不能虚构完成。

可靠 checker、hidden tests 和 native verifier 只能用于：

1. 任务结束后的最终效果评价；
2. oracle upper-bound 分支；
3. 研究阶段定位表示或验收规则的反例；
4. 仅在环境天然公开提供时，作为一种可选证据源，而非方法成立前提。

## 5. 对 Stage 5 的准确处置

Stage 5 包含两部分：

- 可重用核心 substrate：obligation ID、predicate、版本、provenance、provisional/reopened、完成边界与 telemetry；
- 错误收窄部分：只有独立 checker envelope 才能推进 closure。

前一部分保留并扩展；后一部分保留为 `oracle_evidence_gate` 条件，不代表最终核心算法。下一版核心状态必须能摄取分级的普通在线观察，并明确保存 claimed/observed/supported/contested/unknown，而不是把“无 checker”退化为“无状态”。

## 6. 近邻代码带来的边界

PMA 维护自由文本 status/knowledge/procedural bank，并近似每步用 LLM 决定 reminder/silence，不依赖 checker。我们的不可等价目标是：

1. 状态对象联合携带 obligation、支持关系、来源、认识状态和版本；
2. 公开变更/冲突驱动版本化状态修订；acceptance semantics扩展仅在反例暴露缺失维度时可选启用；
3. completion kernel 对 unsupported transition 做保守控制，但允许 UNKNOWN；
4. typed recovery 根据失败类型采取不同动作；
5. 在相同 token/call/dollar 下超过 PMA、summary、RAG、always-visible state 和 static checklist；
6. 用下一关键动作和最终 native outcome 证明机制，而不是用监察者自评分。

`use_now`、`access_risk` 和 budgeted active view 仍有价值，但属于创新 D 的选择层，不替代 A–C 的论文主问题。

## 7. 修正后的方法发现阶段

### 已完成且保留

- Stage 1–3：观测、OTel/Research JSONL 统一、provider/action linkage、checkpoint/branch 基础设施。
- Stage 4：original、always-visible、static checklist baseline；证明更多可见信息和更多 turns 不充分。
- Stage 4.5：离线发现 obligation access 与 correct obligation state 可以分离。
- Stage 5 的状态机 substrate 与完成边界接口。

### 需要返工

- Stage 5 的“checker 才能推进状态”不能作为核心 condition；需要增加 ordinary observation → epistemic evidence 的分级更新。
- 原 Stage 6A checker-dependent treatment 暂停，不能直接运行。

### 后续顺序

```text
Stage 6B  无 checker Evidence-Carrying State V0
          - 公开任务/轨迹增量编译
          - claimed/observed/supported/contested/unknown
          - 不进行主动干预，先测状态质量

Stage 6C  Counterexample-Guided Versioned Revision（已完成）
          - 公开变更推进版本，在线可见冲突触发 contested/reopen
          - 旧证据不可变保存；predicate扩展默认弃权

Stage 6D  Completion Kernel
          - 对 unsupported closure 做 CONTINUE/VERIFY/ABSTAIN
          - 与静态 checklist、结束前固定提醒、oracle gate 消融

Stage 6E  Typed Recovery Controller
          - REPAIR/REMIND/VERIFY/CONTINUE/REOBSERVE/SILENT
          - 比较固定、周期、PMA-style 和风险选择

Stage 6F  最小有效组合与多来源冻结实验
```

每层必须能独立关闭。若简单组件与复杂组件等效，删除复杂组件；若状态质量不提升行为预测或后续动作，不能继续堆叠控制器。

## 8. 三阶段论文路线

1. 第一篇：非训练的 Evidence-Carrying Task State、反例细化、completion control 与 typed recovery，证明机制和真实效果。
2. 第二篇：学习 representation omission、access risk、evidence adequacy、干预价值和 last-effective window。
3. 第三篇：在线适应模型、任务、环境变化与监察预算。

本次修订只消除在线 checker 依赖，不改变这条三阶段路线。
