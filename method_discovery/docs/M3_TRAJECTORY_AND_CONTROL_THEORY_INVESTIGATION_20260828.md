# M3 人工轨迹与经典控制理论调查（2026-08-28）

## 1. 调查目的与边界

本报告为 M3 `decision-centered epistemic control` 提供轨迹依据和理论基石。它不预先冻结
具体算法，也不把控制论术语硬套到 LLM Agent。调查只使用公开任务、Agent 轨迹、工具结果、
工作区和已保存的监察决策；native verifier 仅用于运行结束后的结果描述。

M3 必须服务于既定研究问题：representation omission 与 unsupported closure。它不能退化为
在线 checker、固定频率 critic、单纯提醒时机模块或重新发明 M2 状态表示。

## 2. 复核的轨迹

### 2.1 人工监察

- FBR 2.43：7 次关键纠偏，最终公开全仓测试通过，事后 native verifier 7/7。
- SPC 3.4 v3：拒绝“实现存在即完成”，要求六组行为证据和局部修复后的全局复验。
- RAT 0.22：在意图阶段阻止弱测试、测试驱动公共 API 漂移、oracle washing 和高风险资产丢失。
- KTX 0.13：阻止常见组合语义覆盖明确数值契约、自写测试与实现共错、替代命名空间和根契约遗失。
- Grammar-fuzz：公开环境已经提供直接、忠实、连续的覆盖率反馈时，人工监察保持静默。

### 2.2 自动监察

- FBR v5：发现的问题多数真实，但 7/8 个 HOLD 集中在同一 Proxy/test episode，局部调查不收敛。
- FBR v6：最终 7/7，但后期继续阻断不影响任务行为的总结描述，释放过迟。
- M1 sparse FBR：历史可检索却未主动取回 CORS 关键增量，发生观察/导航遗漏。
- M2-C Fyne：semantic impact 能表达公开变化对 obligation 的具体作用且不产生 A 式版本污染。
- M2-D Fyne：101 次决策中新增直接依赖失效通道触发 0 次；Target 4 在刷新探针与夹具上超时。

## 3. 人工监察的真实元策略

人工行为不是“更频繁检查”，而是以下闭环：

1. **保持根契约**：局部目标、当前实现和常见领域知识不能替代明确公开要求。
2. **等待高信息事件**：意图、因果诊断、新增/修改测试、危险工具动作、证据提升和完成声明。
3. **先识别当前决策**：下一生产修改、是否接受测试 oracle、是否释放 repair、是否允许根完成。
4. **最大限度保留自主性**：安全、可逆且会自然产生信息的动作通常保持静默。
5. **明确偏移就尽早纠正**：错误意图一旦公开且会驱动实质动作，不等错误代码落成。
6. **因果不明就要求判别观察**：不是要求“更多测试”，而是要求能区分竞争解释的最小证据。
7. **提醒后不离开**：检查 Agent 的理解、下一意图、实际动作和证据；口头接受不是 uptake。
8. **局部满足就释放**：不追求与当前决定无关的证明完备性。
9. **根完成时恢复全局覆盖**：局部成功不能合成根完成，先前支持可能被新变化失效。
10. **无法证明就保留 UNKNOWN**：未观察到不等于未发生，也不等于已完成。

因此人工的“一头一尾”不是两个独立 gate：头部意图控制和尾部证据控制由同一个当前决策、
同一个 repair episode 和同一个根契约连接。

## 4. 当前自动方法的统一缺口

当前 M2-C 已有根任务、可修订证据、语义影响、repair episode、主动查看工具和持续身份。缺口
不是“没有长期记忆”或“不会发现错误”，而是缺少稳定的元控制策略来回答：

- 哪一段历史现在值得重建；
- 当前 UNKNOWN 是否影响一个即将发生的实质决策；
- 哪个观察能够区分剩余解释；
- 继续调查的边际决策价值是否仍高于 token、时间和任务延迟；
- 何时退出局部 episode、保留 UNKNOWN 并恢复根任务；
- 哪些未决问题在根完成时是物质性的，哪些只是非阻断残余。

这个缺口产生三个方向相反但同源的失败：

1. **观察不足**：关键历史存在，但监察者不知道取回它。
2. **局部调查惯性**：每一步调查都合理，却不再改变下一行动。
3. **释放过迟**：行为已足够，仍把非物质瑕疵升级为根任务阻断项。

## 5. 经典理论映射

### 5.1 人类 supervisory control：职责而非逐步接管

Sheridan 将监督分解为规划、编程、监视、诊断、必要时干预和从经验学习。它支持本项目把
监察者建模为任务 Agent 与公开环境之间的持续监督层，而不是替代任务 Agent 执行。

轨迹映射：人工 FBR/RAT 会监视测试与意图、诊断问题、最小干预并观察 uptake；Grammar-fuzz
已有忠实反馈时保持静默。

适用限制：human supervisory control 是职责框架，不直接给出可执行的最优策略。

### 5.2 Ramadge--Wonham 监督控制：最大许可而非全面约束

离散事件监督控制中，plant 自主产生事件；supervisor 只能禁用部分可控事件，并在满足规范的
前提下追求 maximally permissive/minimally restrictive 行为。

对 M3 的启示：

- Task Agent 是自主 plant，监察者不是每轮发号施令的 forcing controller；
- 只有一个即将发生且可阻止的实质 transition 有公开证据显示会越出合法任务行为时才 HOLD；
- 普通探索、可逆失败和安全实验属于应保留的许可行为；
- SILENT 是主动的最大许可控制动作，而不是未工作。

适用限制：自然语言任务没有完备 legal language，也无法精确合成 supremal controllable
sublanguage。论文只能借鉴最大许可原则，不能声称实现了经典 SCDES 的形式保证。

### 5.3 事件触发控制：control by exception

Åström 与 Bernhardsson 对比周期采样和越阈事件采样，强调只有测量越过相关边界时才执行
控制；同等平均采样率下，事件采样在其一阶随机系统中取得更低方差。

对 M3 的启示：深审议应由“会影响重要决策的语义事件”触发，而不是固定每 N 轮检查。意图、
测试 oracle、证据提升、危险动作、repair 响应和完成声明是候选事件；事件只触发注意，不自动
证明应当 HOLD。

适用限制：不能把语义 materiality 当作连续误差阈值，也不能把论文的一阶系统性能结果转移为
Agent 稳定性保证。

### 5.4 POMDP 与 dual control：行动既推进任务也获取信息

POMDP 用 belief state 汇总部分观察历史，并统一处理改变环境的动作与只改变信息状态的动作。
dual control 进一步指出控制动作可能同时具有 directing 与 probing 作用。

对 M3 的启示：

- 监察者只能维护基于公开证据的 epistemic state，而非真实任务状态；
- `run test`、查看 diff、比较 legacy、执行 bounded probe 都是 information actions；
- 一个 probe 的价值不是“产生了更多日志”，而是它能否改变下一控制或任务动作；
- 有时让 Task Agent 继续执行一个安全步骤，比立即 HOLD 更能获取信息。

适用限制：没有已知转移概率、观察模型和奖励函数，精确 POMDP/dual-control 求解不可行。belief
应保持结构化、可审计和非伪概率化。

### 5.5 Russell--Wefald 理性元推理：计算价值来自改变外部行动

理性元推理将读取、分析和计算视为 meta-level actions；计算效用来自它改善 Agent 下一外部
行动的能力，并必须扣除计算成本。这与 M3 最直接对应。

令：

- `d_t`：当前待裁决的实质决策；
- `b_t`：M2-C 提供的公开证据/UNKNOWN/CONTESTED 状态；
- `q`：读取测试、检查 diff、回看轨迹或执行 probe 等信息动作；
- `A(d_t)`：SILENT、HOLD、RELEASE、REOPEN、ABSTAIN 等候选控制动作。

理想化的调查净价值可写为：

`VOC(q | d_t, b_t) = E_q[max_a U(a | b_t, observation_q)] - max_a U(a | b_t) - Cost(q)`。

首篇非训练方法不应让 LLM 伪造精确概率或效用值。可实现的是可审计的定性近似：

1. `q` 的可能结果是什么；
2. 哪些结果会改变下一动作；
3. 涉及的任务损害是否物质；
4. 动作是否可逆；
5. 调查的 token、时间、资产污染和任务延迟成本；
6. 什么有限条件结束调查。

若没有任何合理结果会改变下一动作，则继续调查的近似 VOC 不为正，应停止该分支。

### 5.6 MPC/receding horizon：只承诺下一控制步并重新观察

模型预测控制按有限时域规划，只执行当前第一步，然后用新观察重新求解。M3 可借鉴其滚动
而非固定 repair plan：一次只要求一个最有判别力的下一动作；观察 Agent uptake 和工具结果后
重建局部决策，而不是在首次提醒中规定完整修复脚本。

适用限制：Agent 没有可信动力学模型、终端集或稳定性证明，因此不能照搬 MPC 数值优化与
稳定性定理。

### 5.7 序贯试验与最优停止：证据边来边决定

Wald/Chernoff 的序贯思想允许根据已有观察选择下一试验，并在证据足够时停止。它支持 M3
不预先固定检查次数，而是根据每次观察是否减少决策不确定性来继续、换路或停止。

适用限制：Agent 语义假设通常没有可校准似然比，不能伪装成严格 SPRT。可借鉴的是
`continue / decide / abstain` 结构和自适应实验选择。

### 5.8 三值 runtime verification 与 assurance case

有限轨迹经常只能得到 true、false、inconclusive；claim--argument--evidence 则要求证据通过
明确论证支持具体 claim。两者共同支持：

- 测试通过只支持它实际判别的 claim；
- 未决未来行为保持 UNKNOWN；
- completion 需要 root claim 的公开 evidence argument，而不是绿色计数；
- 新证据或 defeater 可以重开先前支持，这由 M2-C 承担。

适用限制：公开自然语言义务不一定可编译为 LTL，assurance case 也不能自动保证论证正确。

## 6. 不采用的生硬理论套用

- **PID/连续反馈误差**：没有稳定数值 setpoint、线性误差或已知 plant dynamics，不作为主模型。
- **完整有限状态机**：状态机可描述 lifecycle，但封闭状态枚举不足以表达开放语义任务。
- **精确 POMDP/贝叶斯 belief**：缺少概率模型，伪概率会制造学术外观而非可靠控制。
- **固定调查次数**：次数不是信息价值，可能同时导致漏检和无限验证。
- **把所有 UNKNOWN 作为故障**：违反无 checker 边界和三值未决语义。

## 7. M3 共享控制不变量

所有候选必须共享以下不变量，否则不是同一研究目标下的公平候选：

1. 单一持续监察者，M2-C 为唯一父版本。
2. 最大许可默认：无足够物质风险时 SILENT。
3. 头部意图边界与尾部证据/完成边界都可激活，但 activation 不等于 HOLD。
4. 明确错误意图可在落成前纠正；因果不明则优先最小判别观察。
5. 一次干预开启持续 repair，正确下一步通常静默观察。
6. 局部 RELEASE 不关闭根任务；根完成时重建全局证据。
7. UNKNOWN 可持续存在，停止调查不得把它改写成 supported/complete。
8. 监察者判断本身可被新公开证据推翻。

## 8. M3 候选控制律

### M3-A：Human-loop activation baseline

目标：把已成功的人类元策略激活为轻量、可审计的控制提示，但不加入显式调查价值结构。

最小新增状态：

- 当前 consequential decision；
- threatened transition；
- materiality/reversibility；
- 当前选择 SILENT/HOLD/RELEASE 的自然语言依据；
- repair exit condition。

预期收益：恢复“一头一尾 + 提醒后不离开 + 局部释放”的人工行为，保持最大自主性。

可证伪风险：仍会像 FBR v5/Fyne D 一样，每一步理由正确但总体调查不停止。

### M3-B：Decision-value gate

在 A 上加入定性 value-of-computation gate。每次主动调查前必须声明：

- 当前决策；
- 可区分的结果；
- 每个结果是否会改变动作；
- 预期任务影响和调查成本；
- exit/switch condition。

若没有结果会改变动作，则不调查；若 UNKNOWN 不阻碍下一安全可逆步骤，则保持 watch 并恢复任务；
若 UNKNOWN 位于高影响不可逆或完成边界且存在有界判别动作，则调查或 HOLD。

预期收益：直接抑制局部调查惯性和非物质完成阻断。

可证伪风险：自报告的价值判断可能只是合理化；过强 gate 会加剧 sparse FBR 的漏检。

### M3-C：Receding-horizon discriminative control

在 A 上只对因果不明的困难 episode 激活轻量竞争解释：最多保留当前真正可行的少量解释，选择
一个能区分它们的下一 observation/probe，只执行这一步，然后用新证据重算。

它不是固定 hypothesis graph，也不要求每个事件列举解释。明确契约冲突可直接 REPAIR；只有
不同解释会导向不同生产动作时才进入该模式。

预期收益：减少“错误测试驱动错误生产修改”，同时避免首次提醒写成僵硬完整修复脚本。

可证伪风险：显式解释维护增加 token，或在简单冲突上诱发不必要的怀疑和探针。

### M3-D：B+C 条件组合

仅当 B 证明能改善停止但漏掉因果调查，且 C 证明能改善因果诊断但仍释放过迟时，才组合为：

`event activation -> decision formulation -> one-step discriminative probe -> value re-evaluation ->
intervene/silent/release/abstain`。

D 不是叙事上最完整就默认晋级；若 A、B 或 C 已达到相同效果，应接受更简单候选。

## 9. 首轮真实任务判别指标

同类候选必须在同一道完整真实任务、相同模型、预算、在线边界和 turn/time 上限下比较。M3
具体共同任务需在实施前预注册，不能沿用 Fyne 只因为它已暴露失败而造成单题过拟合。

至少记录：

- 明确错误意图形成到首次有效纠偏的延迟；
- 合理可逆探索被错误 HOLD 的次数；
- 信息动作中真正改变下一控制/任务动作的比例；
- 单 repair episode 的观察、HOLD、token 和 wall time；
- 重复检查但不改变决策的次数；
- 行为证据成立到局部 RELEASE 的延迟；
- 局部 episode 后是否恢复根 obligation；
- 根完成后因非物质问题增加的 HOLD；
- representation omission、unsupported closure、错误 warrant 和错误放行；
- Task Agent/monitor 调用、input/output/cache tokens、延迟和可得美元成本；
- 最终 native verifier（仅事后评价）。

## 10. 当前推荐但未冻结的顺序

1. M2-C control：历史对照。
2. M3-A：验证人工元策略激活是否本身足够。
3. 若 A 仍局部不收敛，比较 A+B；若主要是因果误诊，比较 A+C。
4. 只有 B/C 形成互补证据才实现 D。
5. 暂定胜者换其他 `method_dev` 真实任务检查泛化；`final_holdout` 保持禁止。

## 11. 论文级形式化方向

可以将最终 M3 描述为 **partially observable, event-triggered, maximally permissive supervisory
metacontrol**：M2-C 提供可修订 epistemic state，M3 在 consequential decision 上选择信息动作
和控制动作，并以近似 decision value 决定继续调查或停止。

这一形式化的真正创新不在于声称求解 POMDP 或实现经典 SCDES，而在于把长程 Agent 的：

- obligation omission；
- unsupported evidence promotion；
- 意图级偏移；
- test-oracle co-adaptation；
- repair uptake；
- 局部/全局释放；

统一为可审计的在线元控制问题，并通过真实长程任务证明它比 state-only、一次提醒和无界深审议
更有效且更克制。

## 12. 关键证据与来源

本地轨迹：

- `STAGE6D_REAL_HUMAN_CONTROL_LOOP_EXPERIENCE_REPORT_20260821.md`
- `STAGE6D_HUMAN_TEST_GATE_FBR243_REPORT_20260821.md`
- `STAGE6D_HUMAN_MONITOR_EXPERIENCE_RAT022_20260821.md`
- `M2_FBR_HUMAN_AUTOMATED_CONVERGENCE_AUDIT_20260827.md`
- `M2_STAGE_CLOSE_AND_M3_ENTRY_20260828.md`

经典来源：

- Sheridan, *Telerobotics, Automation, and Human Supervisory Control* (MIT Press, 1992)；以及公开的 automation/supervisory-control 论文。
- Ramadge & Wonham, *Supervisory Control of a Class of Discrete Event Processes* (1987)；Wonham, Cai & Rudie (2018) 历史综述。
- Åström & Bernhardsson, *Comparison of Periodic and Event Based Sampling for First-Order Stochastic Systems* (1999)。
- Cassandra, Kaelbling & Littman, *Acting Optimally in Partially Observable Stochastic Domains* (AAAI 1994)；Kaelbling, Littman & Cassandra (AIJ 1998)。
- Russell & Wefald, *Principles of Metareasoning* (Artificial Intelligence, 1991)。
- Rawlings, Mayne & Diehl, *Model Predictive Control: Theory, Computation, and Design*。
- Chernoff, *Sequential Design of Experiments* (1959)；Wald 的 sequential analysis/SPRT。
- Bauer, Leucker & Schallhart, *Runtime Verification for LTL and TLTL* (TOSEM, 2011)。
- Kelly & Weaver, *The Goal Structuring Notation--A Safety Argument Notation* (2004)。

公开入口和本地文件索引见：
`some_research/research_library/08_classic_theory/M3_CONTROL_THEORY_READING_INDEX_20260828.md`。
