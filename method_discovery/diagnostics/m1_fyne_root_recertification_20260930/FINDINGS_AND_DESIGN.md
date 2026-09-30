# M1 Fyne：事实结论与暂态 root recertification 草案

状态：**研究侧草案；建议收窄后再议，不授权实现或实验。** 唯一方法参照为 `746a695adac4325d6440941d384d543d1364fef9` 的完整 M1/DCEC-v1。证据逐项导航见 [COVERAGE_MATRIX.md](COVERAGE_MATRIX.md)。四条归档不同历史条件，不能形成同条件四次重复的成功率。分类不是自动评分器，也不进入 Agent 输入。

## 事实判断：先分缺口

1. **A（覆盖遗漏/状态丢失）有局部可能，但没有证成“七个目标标题反复遗忘”。** 四条均能读取公开七目标；失败链甚至显式列出全部七项。X 的 root note 自承“5/7 fully + T6 partial”，随后仍放行 [X D525–531](../../runs/m1_746a695_fyne_repro_20260930/r1/monitor/audit/dialogue.jsonl#L525)：这是子义务的支持状态被压平/推断过宽，不是 T6 从表示中消失。S1 将 T6 记为完全验证，然而先前工具结果已有错误 `NewAllStrings(valid []string)` 签名 [S1 D305,330,386](../../runs/m1_746a695_fyne_stability_20260930/r1/monitor/audit/dialogue.jsonl#L305)。S2 同样列出七项，却缺少 Entry 默认高度的对应证据 [S2 D274,295](../../runs/m1_746a695_fyne_stability_20260930/r2/monitor/audit/dialogue.jsonl#L274)。因此“保留独立支持状况”值得试验性论证，不能把简单的七行列表宣称为解法。
2. **B（义务在场但支持不足/不适用）反复可见。** X 明知 T6 只部分验证，却用 build + 修复响应模式补足整体完成 [X D525–531](../../runs/m1_746a695_fyne_repro_20260930/r1/monitor/audit/dialogue.jsonl#L525)；S2 在 NewAllStrings 局部修复后，将 T6 五项整体标为 verified，Entry 的高度/default 行为没有等价观察 [S2 D269–295](../../runs/m1_746a695_fyne_stability_20260930/r2/monitor/audit/dialogue.jsonl#L269)。S1 的末轮 nil-safe Add 观察只证明该局部，但问题不在“末轮仅看局部”本身，而在此前 `NewAllStrings` 错签名已经可见仍被旧的“全部验证”覆盖 [S1 D302–305,368–386](../../runs/m1_746a695_fyne_stability_20260930/r1/monitor/audit/dialogue.jsonl#L302)。旧证据若条件未变且范围适合可继续用；不能机械要求重新读全题。
3. **C（证据解释错误）有强于纯 A 的直接证据。** S1 看到了错误参数类型却没有把它与公开签名对上 [S1 D305](../../runs/m1_746a695_fyne_stability_20260930/r1/monitor/audit/dialogue.jsonl#L305)；S2 在类似情况下读完整 `validators.go`，说明它是 substring checker，干预并验证修成 validator combinator [S2 D233–273](../../runs/m1_746a695_fyne_stability_20260930/r2/monitor/audit/dialogue.jsonl#L233)。X 修复后确实读了 JSON/binding 源码，却把局部实现与 build 当作全面行为支持 [X D375–403](../../runs/m1_746a695_fyne_repro_20260930/r1/monitor/audit/dialogue.jsonl#L375)。S2 完成前也重新读取 `desktop.App`；哈希未变仅证明字节未变，不认证接口是否只具原题所需方法 [S2 D290–295](../../runs/m1_746a695_fyne_stability_20260930/r2/monitor/audit/dialogue.jsonl#L290)。不应把这些写成“没有去看”。
4. **D（正确控制/Task/运行与原件边界）须同时保留。** H 在 [D333](../../runs/dcec_v1_fyne_longrun_20260921/r1/monitor/audit/dialogue.jsonl#L333) 曾过宽称依据足够；首个 completion handoff 却再对原题和实现发现 NewAllStrings 名称/签名违背，拒绝旧提议、送达修复、等 Task 改动、复读实现并再审根决定 [H D340–422](../../runs/dcec_v1_fyne_longrun_20260921/r1/monitor/audit/dialogue.jsonl#L340)，native 7/7。这是实质的**旧判断可被挑战 → Task 改动 → 观察更新 → root 放行**，并非只多写了状态。X、S1、S2 也各有有效纠偏；后续分数低不抹掉这些能力。另一方面，X/S1 多阶段共享 `Metadata()` 新接口造成的 verifier 编译阻断，不能当作多个独立在线可知的行为失败 [X V1–6](../../runs/m1_746a695_fyne_repro_20260930/r1/verifier/test-stdout.txt#L1)、[S1 V1–12](../../runs/m1_746a695_fyne_stability_20260930/r1/verifier/test-stdout.txt#L1)。S2 的 T2/T7 亦有编译阻断；T3–T5 则通过 [S2 V13–121](../../runs/m1_746a695_fyne_stability_20260930/r2/verifier/test-stdout.txt#L13)。这些 verifier 结果只作事后范围校核。

**总体：纯覆盖遗漏不是目前最强的单因解释；“保留了要求，但 witness 范围/前提不足”与“读到证据却误释”至少同等重要。** 暂态覆盖表示最多直接改善 B 的跨焦点保留和 root 聚合；若 C 主导，它可能只把错误的 `verified` 写得更整齐。它也不代替 Task 修复、项目行为测量、完成提议身份控制或环境限制处理。若后来只是从一句 `All verified` 变成七行 `verified` 而控制不变，增量未成立。

## 历史执行字节：有限核对

H [proof/manifest.json:33,89,111](../../runs/dcec_v1_fyne_longrun_20260921/r1/proof/manifest.json#L33) 记录完整 GenericAgent runtime-source 指纹 `cdd78ef4ebdb0446b8b52bc125faaaa28b6ea517058293799c012316d3b85a6b` 和 isolated snapshot `f3781e432c67052d876d7c71d5c0386e427936ccfc3982f46d917e1b3a2461b9`；X [proof/manifest.json:33,89](../../runs/m1_746a695_fyne_repro_20260930/r1/proof/manifest.json#L33) 的同名 runtime-source 指纹为 `762e7ae7b73a9b19fe1af458745407f76287b53a2529dfaba546008e0c3cb656`。H [README](../../runs/dcec_v1_fyne_longrun_20260921/r1/README.md) 明确 public archive 不含 isolated private bundle；已知 local job 目录中可定位 trial/agent/artifacts 元数据，但没有可直接与近期 bundle 做逐文件比较的完整历史 isolated source。未拿不同 hash scope 做直接字节相等比较，未搜索未知备份或重建环境。故 **历史完整运行字节等价性未确认**，不能按 7/7 与 1/7 差距倒推污染；也不能凭两份初始 M1 指导与工具表相近就宣称整体执行等价。已归档的 task-tree/revision、Fyne image 身份相同，但外层打包/配置及私有服务路由仍可能不同；本轮不做模型差异测试。

## 唯一待论证增量：Transient Root Recertification

目的不是新增 root 阶段：M1 已有 root scope、单焦点、局部解决返回 root、充分证据后 relax。候选只在**既有 root completion 决定期间**，于唯一 `monitor/working.md` 的有界当前状态中暂时保留公开任务中彼此不能由同一局部结论替代的外部完成义务及各自当前支持边界，使局部修复后返回同一个覆盖状态。它不是第二记忆、长期要求图、机器生命周期、checker、额外模型阶段或固定检查清单；一次仍只调查一个可改变控制的焦点。

### 拟修改的准确合同位置（不在本轮应用）

冻结工作树 `E:\longcontext-m1-746a695\GenericAgent-main\monitor_agent_core\agent.py:180–185` 的原文为（不能以当前研究分支同名文件替代）：

> Use monitor/working.md as your only current cognitive state, not as an evidence archive, task checklist, concern list or second memory. Keep one current consequential decision and its scope, one focal unresolved premise whose answer could change your control action, and only the current grounds and limits needed for that decision. Grounds must say what was actually observed, the scope it supports, and what it does not establish here. Keep claims and summaries source-qualified. Revise or replace superseded grounds; do not accumulate repeated claims, summaries or notes as independent support.

拟**替换该段**（不是并列追加一条相冲突的 checklist 指令）：

> Use monitor/working.md as your only current cognitive state, not as an evidence archive, task checklist, concern list or second memory. Keep one current consequential decision and one focal unresolved premise. Only while that decision is whole-task completion, keep a bounded, temporary root coverage view of materially independent external completion obligations from the public task. For each, retain the current conclusion, the observation that supports it, the supported scope and limiting or changed premise, or mark support unresolved. This is a decision aid, not a requirement history or proof that the task is complete. Outside a root completion decision, preserve only the grounds needed for the active focal decision. Revise or replace superseded grounds; do not count repeated summaries as independent support.

同一冻结文件 `agent.py:196–202` 原文为：

> At a root handoff, set the decision scope to whole-task completion and re-qualify existing grounds at that scope. After investigating and resolving or reopening one focal uncertainty, return to the same root decision anchor and re-evaluate. If current grounds reveal another plausible completion-blocking alternative whose answer could change the completion action, replace the resolved focal uncertainty with that one and continue; resolving one uncertainty never by itself authorizes allow_complete. Allow completion only when the current whole-task grounds are adequate and you can identify neither a current decision-relevant unresolved alternative nor an unfinished control dependency. This is bounded re-evaluation, not exhaustive enumeration or proof.

拟**替换该段**：

> At a root handoff, set the decision scope to whole-task completion and re-qualify the temporary root coverage view against current public requirements and observations. After one focal uncertainty is resolved or reopened, return to that same root view; update only the affected obligation and any other obligation whose support depends on the changed premise. An observed local repair supports only the scope it actually covers. For every retained external obligation, ask whether its current witness still supports the conclusion under its stated limits; reuse adequate unchanged evidence, and mark a remaining material gap unresolved rather than inferring success from progress elsewhere. Choose at most one decision-relevant unresolved gap for the next ordinary observation or control action. If no material gap remains and grounds are adequate, allow completion; withdraw a gap that no longer affects the decision, and do not create permanent doubt or demand re-testing without cause. This remains bounded re-evaluation, not exhaustive enumeration or proof.

冻结文件 `agent.py:187–194` 关于 unfinished observation、单依赖和非正面证据，以及 `agent.py:204–210` 关于 tighten/relax、普通工具与无每醒必写，**均保持**。如日后实现，须使同一冻结工作树中的 `working_context.py:53–69` active view 与 `agent.py:212–223` continuation 的同一状态读取/压缩职责一致；不能让维护调用自行作 root 控制动作。此处未授权具体代码改动或新 schema。

### 形成、压缩与 witness

- 覆盖项从原题的**独立外部完成义务**形成，不预载 Fyne 七个标题。标题只作导航：T6 的 Entry 默认高度与 NewAllStrings 组合语义不可用一个“widget 已完成”见证互换。若同一观察真正覆盖多义务可共享该 witness，但不能因为路径、函数名或测试数目相邻而传播结论。
- 一项 witness 必须记录“观察到了什么 → 在何条件下支持何结论 → 用到当前 root 决定还需什么前提”；至少说明来源/版本或可回溯 receipt、支持范围、关键限制。路径/哈希/函数存在/`completed` 标签都不是语义认证。“没发现反例”不等于“已获得充分支持”。同一错误解释仍可能污染所有项，所以本候选不能单独解决 C。
- working view 有界。只保留当前 root 的必要独立项与最短支持/限制；相同支持条件可合并，但语义不等价项不可为省字静默删除。容量不足时，把未能压缩而仍可能影响决定的范围显式标为未决、选一个焦点调查或请求原文件，不宣称已经覆盖全题；不能无限膨胀为持久 requirement graph。
- wait/干预/修复/新 completion proposal 之间保持这份**暂态 root 状态**的必要连续性，更新受修复影响的 witness；原生“旧 proposal 经 intervene 后失效”的控制边界不变。离开 root 判断后不把覆盖项常驻活跃工作态；原始 audit/history 保留，不删除。充分旧证据可复用，无需每次重复工具。自己先前的解释或测试前提错了就撤回该项要求；首选测量 unavailable 时选择同一决策区分力的替代观察，或有界未决，不把不可用当成功也不永久卡死。

### 可区分预测与否定条件

若此增量有效，最直接应减少 X 型“自承部分支持仍批准”或 S2 型“NewAllStrings 局部修复被扩成整个 T6”，同时保留 H 型先前过宽判断可被推翻、修复后能放行；它**不**预言会自动识别 S1 已见错签名、X 已读错行为这类 C。研究评价要看实际观察、witness 范围修订和最终控制，而不是状态项数量。若仅把 `All verified` 改为多行 `verified`；若读到矛盾证据仍误释；若新增重复认证、虚假义务、误阻塞、状态维护摩擦或成本，却不改善 root 控制，则否定或收窄此方向。一次 Fyne 7/7 不是门槛，也不是充分证据。

**建议：收窄后再议。** B 的直接证据足以让临时 root 覆盖成为可检验假设，但 C 型可见证据误判与 H 型 M1 自行推翻过宽状态说明它不能被宣布为既定修复。主线程应先审本矩阵与拟议合同是否真有增量，再决定是否实现及在固定开发集上比较；本轮不冻结面板、不启动候选。
