# M3 人工监察差距递增弥补计划

Date: 2026-08-29
Status: M3.1--M3.5 engineering-complete; persistent M3.3 rejected; cumulative real-task validation not yet run

## 强制证据门禁

每个实现或验证步骤开始前，必须带着该步目标重新读取真实人工监察轨迹、当时可见上下文与
实际决策。先记录人工确实看了什么、何时查看、如何继续调查或保持静默，再进行修改；不得
凭对人工行为的印象设计机制。

当前主要证据锚点：

- `STAGE6D_HUMAN_TEST_GATE_FBR243_REPORT_20260821.md`；
- `STAGE6D_REAL_HUMAN_CONTROL_LOOP_EXPERIENCE_REPORT_20260821.md`；
- `M0_HUMAN_MONITOR_POLICY_AND_LEAKAGE_SPEC_20260822.md`；
- `M2_FBR_HUMAN_AUTOMATED_CONVERGENCE_AUDIT_20260827.md`；
- FBR 人工 decisions/interventions/snapshots 与原始 Agent `output.txt`；
- 后续阶段对应的 TPL、SPC、RAT、KTX 与 Grammar-fuzz 人工轨迹。

## 递增阶段

1. **M3.1 基础感知**：把合并后的新公开增量作为低摩擦 first-look；深层历史、文件、测试和
   diff 仍由同一监察者自主检索。
2. **M3.2 自适应观察节奏**：合并普通边界，正常推进时稀疏观察，测试/失败/阶段切换/完成与
   repair episode 时提高关注；强调用不随边界线性增长。
3. **M3.3 连续语义片段必要性审计（已完成并否决持久实现）**：确认目标、意图、证据、
   修订、根任务联系和下次关注点已分别由 M1/M2、repair episode、root audit 与 M3.2 承载；
   不再维护第二份持久 narrative。若以后需要整体态势，只允许作为按需 active view 候选消融。
4. **M3.4 能力审计与异步干预协议重构**：自主工具循环和纠偏后持续跟踪已由早期实现覆盖；
   删除串行时期遗留的 HOLD/SILENT/RELEASE 普通动作，将发言与注意力正交化。
5. **M3.5 跨轮次连续认知**：保留当前根任务、关注目标、证据索引、疑点、repair episode、
   uptake、释放和重开条件。

每项必须保护 M1-C、M2-C、异步并发、无在线 checker、完整公开归档和可关闭消融路径；
每项完成后停止汇报。根据用户 2026-08-29 裁决，M3.1--M3.5 中间不运行完整真实任务；单项
只能标记为 engineering-complete，不能据此接受机制或声称效果。M3.5 累计完成后再统一申请
一次完整真实任务启动门禁，并利用保留的独立开关追溯各增量。

## M3.1 证据与实现边界

人工 FBR 的第一次正式判断覆盖 turns 1--47，随后一次观察窗口覆盖约 turns 49--180；人工先
读取连续工作窗口，再在测试生成、实现意图和完成声明处聚焦。r4 则在 34 次 monitor 调用中
产生 0 次 inspection：它把没有语义内容的 wake 误当作没有任务行为。

M3.1 因此只加入确定性 first-look sensor：任务侧仍只写 append-only archive；监察进程将自上次
观察以来的 intent/result 边界按 turn 合并，在第一次强审议中呈现公开行为但不判断正确性。
完整轨迹、原始任务、测试、diff 与工作区仍由监察者按需检索。该改动不处理自适应调度、语义
episode 或开放工具循环，它们分别属于 M3.2--M3.4。

工程验证：定向 85 passed；GenericAgent 全量 258 passed；Harbor/运行器相关 60 passed。
M3.1 尚未获得完整真实任务证据，不能声明已弥补差距或改善任务效果。

## M3.2 证据与实现边界

人工 FBR、SPC-v2/v3 与 Grammar-fuzz 轨迹显示的不是固定频率轮询：普通推进可形成较宽的
连续观察窗；测试创建/修改、公开执行反馈、语义阶段切换和完成声明提高关注价值；第一次
纠偏后则持续跟踪 Agent 的理解、意图和行动，直到 uptake 或重新纠偏。人工同时不会因为
源码文本含有 `error` 等词就把它当作失败证据，也不会让廉价调度器预判语义正确性。

M3.2 因此加入可关闭的语义巡视调度层。所有公开边界仍被廉价、完整地归档；普通阶段不再由
测试路径、测试命令、失败关键词或完成语言等固定事件形状分类器决定观察。每次审议后，同一
监察者在 `observation_plan` 中亲自估计未来多少个公开任务 turn 后再次查看，并以开放自然语言
保存 `focus`、`expected_progress` 和 `reason`。无模型外层只倒计数、保存便签并在到期时将其
原样交还，不解释这些语义内容。监察者若醒早可拉长下次距离，若发现醒晚或即将进入脆弱阶段
可缩短距离；缺省20 turn和最多100 turn只作为异常恢复及最长静默上限，不是任务分类规则。
持久 review cursor 保证进程重启后不会遗失未审议边界或反复重放已审议窗口。

attention-regime 转换现已显式化：普通 `patrol` 阶段不审查每个公开意图；监察者发送非空
`intervention_message` 后进入 `focused`，每个后续 `post_model_pre_tool` 意图边界和
`post_tool_pre_next_llm` 结果边界都会触发同一监察者审议。修复方向正确时消息为空但仍保持
`focused`；只有监察者把自身注意力切回 `patrol` 才恢复普通稀疏节奏。由于任务与监察异步并发，
当前原子工具调用不会被中途撤销；意图级纠偏在下一次安全推理边界注入，作用是阻止错误方向
继续扩张。根 completion proposal 继续使用框架已有的明确完成边界强制审议，不依赖普通巡视
倒计数。潜在不可逆动作是否值得形成额外保底加速器不在当前实现中预设，留待独立证据裁决。

工程验证：GenericAgent 全量 263 passed；Harbor、LHTB、运行器和 M3 gate 相关 95 passed。
配置链覆盖 GA、Harbor 两种适配器、运行脚本与 manifest，M3.2 必须建立在累计 M3-B 父版本
之上。依照用户裁决未运行真实任务；因此观察频率、成本变化、错误阻断和效果增益均待 M3.5
后的累计真实检验。
## M3.3 必要性审计与回退（2026-08-29）

重新读取最早的人工作为监察者的 FBR 原始轨迹并对照现有实现后，裁决原 M3.3 持久
`semantic_work_segment` 与已有能力重复：M1 已保存 local intent、causal hypothesis、public
evidence、open question、repair episode、root links 和 source anchors；M2-C 已提供 scoped
revision；根任务由 root audit 保持；M3.2 已保存下一次观察距离、focus、expected progress 和
reason。再增加 narrative、root connection、next transition 和 anchors 会制造第二份需要同步的
摘要状态，增加注意负担、语义冲突和版本漂移风险，却没有独立证据支持。

因此撤回 M3.3 的运行时状态、prompt/schema、checkpoint、配置传播、真实任务 condition 与测试，
恢复 M3.2 为当前累计父版本。该负结果保留在文档中；若后续真实轨迹证明监察者冷启动重建成本
过高，可将整体态势作为从既有权威状态按需生成的 active view 候选，而不得默认恢复第二份持久
记忆。此次回退不改变 M1-C、M2-C、M3.1、M3.2、异步并发、主动检索工具或无 checker 边界。

## M3.4 能力审计与异步干预协议重构（2026-08-29）

审计确认自主工具循环、非阻塞观察、user-like 下一轮注入以及纠偏后的连续 intent/result 跟踪
均已由早期实现覆盖；真正残留的是串行时期将“是否发言”和“观察强度”耦合为
HOLD/SILENT/RELEASE 的动作协议。当前实现已彻底切换为两个正交输出：可为空的
`intervention_message` 与监察者自身的 `attention.mode=patrol|focused`。空消息不进入任务上下文；
非空消息原样成为下一安全推理边界的 user 内容并要求 focused；focused 可在不发言时持续查看，
监察者确认 uptake 后自行返回 patrol。repair episode 只记录纠偏和残差，不再暗示任务暂停。

根 completion 已从普通协议拆分，只允许 `termination_decision=allow_complete|continue_task`；
`continue_task` 必须附带非空 user intervention，`allow_complete` 必须为空。普通工具执行永不等待
监察者，只有不可逆的根终止转换保留有界同步审议。checkpoint 升级为 v2，并只读迁移 v1 的
SHADOW/DELIBERATE；新 decision archive 为 `m0-monitor-decision/2`，旧动作输出会被协议拒绝。

工程验证：GenericAgent 全量 268 passed；Harbor、
LHTB、runner 与 M3 gate 相关 95 passed。跨仓库全量曾得到 593 passed、3 failed；三项失败均为
未被本轮修改的 Benchmark M14 冻结数据与 base task 52/manifest hash 已有不一致，不属于控制协议
回归。本阶段未运行真实任务，不能据此声明效果或成本改进。

协议收口审计补充：`authoritative_state.json` 因根完成依据字段从
`root_task_release_basis` 更名为 `root_completion_basis`，同步升级为
`m0-authoritative-state/2`，避免不同结构复用同一 schema。异步 worker 错误、队列满或有界
completion 等待超时时，M0 适配层统一返回带最小恢复指令的 `CONTINUE`，不得把监察故障作为
根任务完成依据；普通异步监察故障仍不阻塞任务 Agent。

## M3.5 真实轨迹反馈后的认知续接修订（2026-08-29）

累计真实运行 `m3-m35_continuity-fyn-2.2.0-roadmap-r2` 暴露了一个此前确定性检查无法证明的
缺口：双层状态能够让监察者正确识别并持续追踪 Hyperlink 行为契约和测试 oracle 问题，但普通
异步审议仍明显落后于任务 Agent。首次有效判断从其证据窗口到注入约相差 14 个 task turn；决策
内容正确，却要在每次无隐式 history 的 active-reconstruction 调用中重新恢复较宽的认知现场。
原始产物保存在
`long_context_bench/output/m3_real_tasks/human_gap_increments/m35_continuity/fyn-2.2.0-roadmap/`
下。该运行被人工停止，只构成机制诊断证据，不构成任务效果结论。

这项证据不支持恢复被 M3.3 否决的第二份全局任务摘要。修订仅在现有全局语义状态与公开事件
增量之间加入可关闭的 `m35_cognitive_checkpoint`：同一次监察决策用开放自然语言留下
`continuation_note` 和少量 `source_anchors`；运行时附加已审议 turn/archive cursor、attention
mode、repair episode 是否开放及 decision index。该断点只保存“当前在监督什么、工作判断与公开
依据、Agent 相关意图、未决问题、下一证据/释放条件”，不得复制完整 obligation ledger 或隐藏
推理。它不增加模型调用。

调用协议分为两条路径：初始化、状态失配恢复和根 completion 使用 `wide_reconstruction`；存在
断点的普通唤醒使用 `checkpoint_plus_delta`，直接返回认知断点、当前 repair episode、游标后公开
增量和全局状态目录。完整 root audit、原始任务、语义对象、轨迹、测试和 diff 仍由持久状态与主动
工具保留为按需兜底；普通快路径不再自动重发完整 root audit。监察者未输出新断点时不阻断任务，
旧断点会显式标记 `carried_forward`，避免伪装成已吸收本轮变化。

工程验证：监察核心 77 passed；异步运行时/任务循环 37 passed；GenericAgent 全量 275 passed；
M3 gate、Harbor 和运行器配置链 72 passed。新增确定性检查覆盖断点生成、下一轮增量续接、重启
恢复及根完成强制宽重建。以上只证明实现与回归成立；响应延迟、判断质量、token 成本和任务效果
仍须在下一次经用户单独确认的完整真实任务中验证。
