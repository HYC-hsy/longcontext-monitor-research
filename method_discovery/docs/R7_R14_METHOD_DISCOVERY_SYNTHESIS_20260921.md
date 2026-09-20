# R7–R14 Method Discovery Synthesis（2026-09-21）

## 0. 阶段裁决

- 基线：`bd1aaf4`。
- R7–R14 微观诊断阶段到此收束。
- 本轮没有模型 API、真实实验、运行代码或候选实现。
- 后续不再沿 A/B/C/D/E/F/G/H/P/RACC 逐个打补丁；它们只保留为诊断证据与失败对照。
- 当前唯一主机制设计：**Decision-Centered Epistemic Control v0（DCEC-v0）**。
- 唯一保留的比较对象：**ordinary persistent Supervisor**。不再并列保留额外方法候选。
- Resource-Aware Closure Control 只作为未来独立的 closure/resource component 归档，不进入 DCEC-v0。

本文不是效果声明。它把现有证据压缩成一个最小、可证伪、能够进入完整长程运行的机制假设。

## 1. 冻结的经验事实

等级含义：

- **strongly supported**：在多个冻结运行/审计中反复出现，或由完整轨迹和代码事实直接支持；结论范围仍限于现有开发材料。
- **suggestive**：有真实轨迹信号，但样本、任务来源或因果隔离不足。
- **not established**：目前只是解释或机制假设，不能写成既有发现。

| 经验陈述 | 等级 | 证据边界 |
|---|---|---|
| 明确、与要求直接对照且有判别力的 counterexample 被实际取得后，Supervisor 通常能理解冲突并限制完成判断 | **strongly supported** | R8 提示对照、R10 V1/V2 JSON 条件、R11 B 和 R12 G-r2 的父调查均显示模型能识别 `FromJSON` 冲突；R12 G-r2 未完成裁决，所以“理解后一定闭环”不成立。证据主要来自同一 Fyne 派生状态，跨任务泛化尚未建立。 |
| 原始 requirement 和关键实现材料通常仍然存在，当前失败不是简单 memory loss | **strongly supported** | R11 的完整 History 含 JSON/Sprintf 要求；R13 lineage 显示 requirement、tool receipt、文件身份和多数版本信息可追溯。存在不等于会被选择或消费。 |
| 当前主要失败集中在 investigation/retrieval/control：选错目标、重复旧局部、读 claim/inventory 而非判别证据、未把当前决定与取证稳定连接 | **strongly supported（对现有开发状态）** | R9 的错误批准、R11 0/6 首动作判别性、R12 G/E 失败及 R13 JSON/Sprintf lineage 一致支持。它是否是所有长程任务的主因仍需完整 method_dev 复验。 |
| AppMetadata 暴露 state revision 缺口：修复后旧 concern 没有及时退出当前 working state | **strongly supported（该对象）** | R13 发现修复前后有直接观察，但 `working.md` 在 R7–R12 检查到的副本哈希不变，继续保留早期 open issues；后续又反复选择 AppMetadata。该现象在其他任务上的频率尚未建立。 |
| provenance/source qualification 存在局部问题 | **strongly supported** | task claim 经 summary/working surface 后会弱化来源限定；范围也曾由局部/符号观察扩大到 target/whole-task。 |
| 当前证据足以支持重型 TMS/ATMS/knowledge graph 或完整 provenance state | **not established** | R13 未发现最终判断把派生重复当作多份独立支持的可靠证据；raw provenance 大多仍在，主要失败是没有选择/消费。 |
| selector、isolated verifier、structured counterfactual 等额外认知阶段在已测形式下没有稳定净收益，并带来调用、协议和控制成本 | **strongly supported（已测形式）** | 独立 C 未证明默认价值；R11 A/B 首动作无判别性且拖坏正确控制；R12 G/E 未改善错误状态并使正确控制未决。不能外推为“任何分解/独立核验永远无用”。 |
| closure/resource competition 独立存在 | **suggestive** | R12 G-r2 已取得 JSON 冲突却用尽六次而未裁决；R14 证明工具回执需要后续模型调用。只见少量轨迹，且六次是 diagnostic calibration。 |
| 固定保留最后一次调用会提高在线长程效果 | **not established** | 六次不是部署不变量；reserve 后是否作出正确判断没有实验依据。 |
| 一个 decision-centered persistent state 能解决当前主失败 | **not established** | 这是由以上证据约束出的下一机制假设，必须经最小判别与完整 method_dev 验证。 |

## 2. 统一 failure model

```text
长程任务、实现和修复持续变化
        ↓                                      [strongly supported]
持续 Supervisor 累积 requirement、claim、summary、直接观察和旧 concern
        ↓                                      [strongly supported]
当前认知没有稳定围绕“此刻要作出的决定”组织、消费并修订
        ↓                                      [suggestive causal link]
旧问题、task claim、summary、direct evidence 竞争注意力
        ↓                                      [strong association; causal weight not isolated]
调查对象漂移 / 重复已修局部 / 漏查未直接支持要求
        ↓                                      [strongly supported]
干预依据、恢复确认与 completion 判断失真
        ↓                                      [strongly supported for observed cases]
错误批准、错误未决、重复调查或闭环耗尽
```

### 已被证据支持的边

1. **任务变化 → 证据与状态版本混合**：App 修复前后版本与后续旧 working note 可直接追溯。
2. **混合材料 → 错误调查行为**：完整 History 中要求并未丢失，但首动作仍落在最新完成声明、已修 App 或目录库存。
3. **错误调查 → unsupported closure**：R9/R11 多次未读 JSON/Sprintf 而批准整体；直接 JSON 证据出现后判断改变。
4. **修订不足 → 重复旧 concern**：App 修复后仍长期占据调查焦点。

### 仍是待验证假设的边

1. 一个显式、极小的 decision-centered state 是否足以改变 target selection；
2. stale working state 相对 History 位置/显著性的独立因果贡献；
3. DCEC 是否能在不同任务上同时减少漏查与重复，而不导致普遍保守；
4. closure/resource control 是否还需独立组件。

这个 failure model 不声称 LLM 是马尔可夫系统，也不把“注意力竞争”当作已测量的内部神经机制。它描述的是可审计输入、状态和行为之间的系统级关系。

## 3. 主机制：Decision-Centered Epistemic Control v0

### 3.1 设计约束

DCEC-v0：

- 只有一个持续 Supervisor；
- 沿用同一 History、现有读写/查询工具和并发控制链；
- 不新增 selector/verifier Agent，不新增独立模型阶段或隐藏调用；
- 不依赖 checker、gold、隐藏测试；
- 不做完整 requirement checklist、PASS 表、TMS/ATMS 或知识图谱；
- 不包含 JSON、Sprintf、AppMetadata 等开发态对象；
- 在初始化、普通巡检、干预、repair tracking、wait 和 root completion 全生命周期使用，而非只在结束时启用。

DCEC-v0 只有三个逻辑组成。

## 4. A — Minimal epistemic state

不从字段数量出发，而从三个必须保留的功能出发。其承载物可是一份有界、模型维护的自然语言 `decision_state`，由现有私有文件能力保存；第一版不新增知识库或工具 schema。runtime 只负责创建空载体、原子保存并把当前有界内容放入每次正常 Supervisor 请求的 active view；它不生成语义状态。初始化由同一 Supervisor 在第一次正常 review 中完成，状态更新使用原工具循环，因此没有额外模型阶段或隐藏调用。

### A1. 当前决定锚点

功能：明确 Supervisor 此刻正在决定什么，以及什么未知会真正改变该决定。

它不是完整任务分解，只保留：

- 当前 decision scope（例如是否需要干预某个意图、某次修复是否恢复、是否允许 root completion）；
- 一个当前 focal uncertainty/premise；
- 能区分相关状态的下一类观察，而非预先写死具体文件答案。

删除后会重现：R11 读取完成声明、R11/R12 列目录、围绕最近局部而非根决定调查的 target/observation drift。

### A2. 活跃 concern 的修复生命周期

功能：区分 `open → intervened/recovering → resolved-or-reopened`，并让已经有 post-repair evidence 的 concern 从当前调查前沿退出。

这里只保存仍影响控制的少量 active/recovering concern；已解决项移到历史引用，不继续占据当前 active view。`resolved` 不是永久真值：相关代码版本变化或新冲突可使它重新进入前沿。

删除后会重现：AppMetadata 修复后 working state 不更新、后续多次重查旧 concern；也无法连续追踪纠偏是否真正 uptake。

### A3. 当前决定依据及其限制

功能：把当前判断连接到实际观察，而不是连接到无来源的“已完成”叙述。

只保留少量会改变当前决定的 evidence references：

- direct observation 的真实回执、路径、范围、hash/version；
- task-agent claim / summary 明确保留其来源身份；
- 每项材料实际支持的局部范围，以及仍缺的判别观察。

这不是全量 evidence bank，也不自动计算真假或置信度。删除后会重现：task claim/summary 被扩大成直接支持、局部修复被扩大成 whole-task completion，以及截断读取产生过强断言。

### 3.2 有界性

- 同时只允许一个 focal inquiry；
- active concern 数量由正在进行的纠偏/恢复 episode 决定，不按所有 requirements 建表；
- grounds 只保留当前决定实际使用的少量引用；完整 History、事件和旧证据仍在外部归档，按需读取；
- 已解决项只留下历史指针和适用版本，不在 active view 反复展开。

因此它是 decision working state，不是任务 checklist。

每次请求都提供当前 state 是消费契约，而不是第四个机制：若只把文件放在磁盘上、仍依赖模型偶然想起读取，就无法区别于 R13 已见的“信息存在但没有被用到”。active view 的新增 token 必须单独计量，并以固定上限约束。

## 5. B — Revision / update

### 5.1 更新顺序

同一 Supervisor 在普通工具循环内完成以下语义更新，不增加独立调用阶段：

1. **接收新事件/观察**：runtime 保存事件、工具回执、范围、文件版本和时间；
2. **关联当前决定**：模型判断该观察是否改变 focal uncertainty 或 active concern；
3. **修订而非追加**：新证据若推翻旧判断，更新当前 grounds/concern；旧记录保留在历史，但不继续作为当前有效依据；
4. **纠偏后进入 recovering**：发出 intervention 不等于修好；持续观察任务 Agent 的理解、动作和实际结果；
5. **有 post-repair evidence 才退出 active frontier**：对应 concern 标记 resolved，并将焦点释放给仍未直接支持、会改变当前决定的问题；
6. **新冲突或版本变化可 reopen**：只恢复相关 concern，不把整个历史重新变成 active。

### 5.2 runtime 与 LLM 的边界

runtime 可确定：

- source channel/type；
- message/tool/file identity；
- timestamp、turn、cursor；
- read/search 的实际范围与截断；
- workspace/checkpoint version 与文件 hash；
- `version_changed_since_observation`；
- intervention 是否送达、任务是否产生后续公开动作。

LLM 必须判断：

- 观察是否语义上支持/反驳要求；
- 某项证据是否足以解决当前 uncertainty；
- 修复是否恢复了所需语义；
- concern 应 resolved、保持 open 还是 reopened；
- 下一观察与当前决定是否有判别力。

runtime 不自动标记 `claim false`、`semantically stale`、`requirement satisfied`，也不做自动 truth propagation。

### 5.3 当前有效与历史保留

- **当前有效**：当前 scope、一个 focal inquiry、active/recovering concerns、当前 grounds/limits。
- **历史保留**：旧判断、旧版本证据、已解决 concern、intervention 与 repair lineage。
- 历史材料可按需恢复，但不会仅因存在就自动进入当前决定。

## 6. C — Decision-centered supervisory control

同一 Supervisor 使用当前 state 选择现有动作：

```text
observe public change
  → revise current state
  → if active contradiction: intervene
  → if recovering concern: inspect uptake / implementation / result
  → if decision-relevant uncertainty remains: investigate one discriminating observation
  → if no actionable residual and task continues: wait
  → if root completion is currently supported at the required scope: complete
  → otherwise preserve uncertainty and continue targeted investigation
```

### 避免随机低层 tool selection

工具动作不是从 `read/list/search` 空间直接挑选。先由当前 decision scope 与 focal uncertainty 确定“要区分什么”，再在同一个正常模型响应中调用能够观察该差异的现有工具。没有独立 selector call，也没有宿主替模型猜答案。

### 不退化成 R9 prompt reminder

R9 只是当前输入中的文字指导；DCEC 的状态跨 wake 持久、随观察和 repair 实际修订，并在后续控制选择中继续可见。是否写入、修订和消费均可由轨迹审计，不以模型口头提到 scope 算成功。

### 不恢复 A/B/G/E 前置 selector

没有 1+5 分配、wrapper 或新协议工具。decision anchor 与 concern state 属于持续父 Supervisor 自己的工作状态；调查和状态修订发生在原工具循环内。

### 避免无限核验

停止依据不是“所有要求都验证过”，而是：

- 当前 concern 已由足以改变本地控制的观察解决；
- 当前 focal inquiry 已取得区分结果，或在可用权限/资源下明确无法取得；
- 新调查不会改变当前动作时，不继续重复；
- 局部修复只释放该 concern，不自动批准整题；root completion 仍按 root scope 的当前 grounds 判断。

第一版不加入独立 RACC。资源、调用和延迟仍完整记录；若完整长程轨迹再次稳定出现“证据已足够但无法闭环”，再单独评估 closure/resource component。

## 7. 最小性审计

| 组成 | 删除后无法覆盖的真实 failure | 能否再删 |
|---|---|---|
| 当前决定锚点 | R11/R12 首动作落在完成声明、inventory 或最近显著对象；工具动作与 root decision 无稳定连接 | 否；这是 decision-centered 与普通 working note 的核心区别 |
| active concern / recovery lifecycle | AppMetadata 修复后仍留在旧 working state 并被反复选择；intervention 与真实 uptake 无法区分 | 否；否则没有 state revision，只剩调查提示 |
| current grounds + source/scope/version limits | task claim/summary、符号存在和局部修复被扩大为整体支持；截断读取造成越界结论 | 否；否则决定仍与真实观察脱节 |
| 完整 requirement checklist | 没有一条 R7–R14 failure 必须依赖它才能解释 | 删除 |
| 独立 selector/verifier | 已测形式没有稳定净收益，且引入协议/预算成本 | 删除 |
| 完整 provenance graph/TMS | R13 未证明 duplicate inflation，raw provenance 多数仍在 | 删除 |
| 自动 confidence/risk score | 现有轨迹没有证明阈值或评分可可靠生成 | 删除 |
| fixed terminal reserve | 只解释 R12 单个 closure loss，六次不是部署不变量 | 不并入 v0，未来独立评估 |
| 多 focal premises / 全局 frontier | 会重新接近 checklist，并非解释现有 failure 的必要条件 | 删除；第一版只保留一个 focal inquiry |

DCEC-v0 的最小充分假设是：**一个当前决定锚点 + 一个可修订的 concern lifecycle + 少量有来源边界的当前 grounds**。任何额外字段、阶段或 Agent 都需新的失败证据才能加入。

## 8. 理论映射与明确不采用部分

### Knowledge representation

- **borrowed idea**：表示方式会改变后续可做/易做的推理；因此把当前决定、active concern 和 grounds 放在一个可消费的有界工作状态中。
- **deliberately not adopted**：完整 ontology、requirement graph、全任务 PASS/FAIL 表或知识图谱。

### Truth maintenance / belief revision

- **borrowed idea**：新观察应修订当前判断；旧理由保留可审计，但不因历史存在继续控制当前状态；新冲突可 reopen。
- **deliberately not adopted**：ATMS 环境集、自动依赖传播、逻辑一致性保证、自动真假计算。

### Provenance

- **borrowed idea**：claim、summary、direct observation 的来源不同；范围、版本和读取边界必须保留。
- **deliberately not adopted**：完整 lineage graph、自动 source reliability score、把 provenance 当作真实性判定。

### Blackboard / shared state

- **borrowed idea**：外部持久工作区让同一 Supervisor 跨 wake 保存当前认知，并接受 runtime 与模型共同贡献。
- **deliberately not adopted**：多 Agent 黑板调度、角色竞价、独立维护 Agent 或隐藏 coordinator。

### Limited reasoning / metareasoning

- **borrowed idea**：调查有成本；当前 inquiry 应以能否改变控制决定为中心，并在无新增决策价值时停止。
- **deliberately not adopted**：已知效用函数、最优停止定理、固定第六次 reserve 或把额外调用称为免费。

## 9. 控制论映射

这只是动态系统设计启发，不继承经典线性/随机控制定理。

| 控制概念 | DCEC 对应 |
|---|---|
| 状态 | current decision、active/recovering concern、current grounds/limits |
| 观测 | public events、task claims、工具回执、文件/测试/diff 及其版本范围 |
| 控制 | investigate、intervene、track recovery、wait、complete |
| 能观测性 | 当前选择的观察能否区分会导致不同控制动作的相关状态；不是“是否看过文件” |
| 新息 | 新观察是否改变 focal uncertainty，而非重复 task claim、summary 或已恢复局部 |
| 控制约束 | 模型调用、token、工具时间、wall time、任务阻塞和 completion latency 均有限 |
| feedback | 观察 → state revision → 控制 → 后续公开反应/实现变化 → 再修订 |

LLM 任务不是已知状态空间、线性转移或高斯噪声系统；这里不声称可观测性矩阵、稳定性、最优控制或收敛保证。

## 10. 唯一最小判别实验（只设计）

### 10.1 研究问题

DCEC-v0 是否实际改变“当前 state revision + 下一步调查选择”，而不只是让最终文字更谨慎？

### 10.2 一轮、两个预注册序列

使用一个小型、领域中性的顺序任务 fixture，包含两个独立要求，不复用 JSON/Sprintf/AppMetadata：

1. **latent-defect sequence**：A 先出错 → Supervisor 纠偏 → Task Agent 修复 A → post-repair observation 支持 A → Task Agent 提议整体完成，但 B 仍存在可由普通读取发现的独立缺陷。
2. **correct-control sequence**：同样的 A 修复链，但 B 实际正确且证据充分。

条件只有两个：

- ordinary persistent Supervisor；
- DCEC-v0。

相同 Supervisor 模型、原任务、事件、工具权限、调用/token 上限和控制协议；DCEC 不获得额外 LLM 调用。DCEC 的 state 必须从序列开始自然形成，禁止研究者事后写入“B 未验证”或缺陷位置。

### 10.3 必须观察的中间行为

1. A 获得 post-repair evidence 后是否退出 active investigation frontier；
2. root decision 到来时，尚无直接支持且会改变决定的 B 是否更可能成为 focal inquiry；
3. 实际 tool action 是否能观察 B 的真假，而不是 claim/inventory；
4. 工具回执是否修订 current grounds 和最终控制；
5. 正确控制是否能及时批准，而不是因 state 机制普遍变保守。

### 10.4 通过门槛

DCEC 必须同时满足：

- 修复后的 A concern 退出当前前沿；
- latent-defect 中 B 进入调查且动作与目标一致；
- 根据真实观察拒绝/纠正错误 completion；
- correct-control 不出现明显的额外未决、错误拒绝或无限验证；
- 没有独立模型阶段/额外调用；token、工具操作和延迟完整报告。

仅输出更长、更谨慎或显式 UNKNOWN，不算通过。

### 10.5 失败规则

- 若 state 没被实际维护/消费，或仍重复 A：只允许一次**机制级**修正（修改 state/update/control 的一项契约），不进行逐案例 prompt patch。
- 修正后仍失败：停止 DCEC，不新增 R15 式微观诊断，不回到候选池排列组合。
- 通过后：直接进入完整 method_dev 长程实验。

## 11. 后续完整长程 method_dev 实验（只设计）

### 11.1 条件

只比较：

1. baseline ordinary persistent Supervisor；
2. DCEC-v0。

使用已冻结的 method_dev 任务清单和来源分层；启动前 manifest 固定任务、重复、Task Agent/Supervisor 模型、工具、并发/完成控制、最大时间与资源预算。不得根据小型诊断或早期长程结果挑题。final holdout 不运行。

### 11.2 公平性

- 同一 Task Agent、Supervisor 模型与 provider profile；
- 同一公开证据、workspace 权限和无-checker边界；
- 同一在线并发/强制纠偏/root completion 机制；
- DCEC 不增加独立模型调用；
- continuation、transport retry 和实际 provider requests 全部计量；
- 任务对/运行顺序预先冻结，保留全部成功、失败和超时。

### 11.3 主要指标

| 维度 | 指标 |
|---|---|
| 最终能力 | native post-hoc task success（评价只在结束后使用） |
| 漂移 | drift detection：已标注/审计偏移中被及时识别的比例及发现延迟 |
| 干预 | intervention correctness：真实、适用、无越界纠正；错误/冗余干预分开 |
| 恢复 | repair uptake / recovery：任务是否理解、实施、验证并稳定退出 concern；复发单列 |
| 伤害 | false blocking、无必要中断、过度监督、错误未决 |
| 完成 | completion correctness：正确批准、错误批准、正确继续、错误阻断、未完成 |
| 调用 | logical model calls 与全部真实 provider requests/attempts |
| 成本 | input/output/cache token、可得美元成本、工具操作/时间 |
| 延迟 | supervisor wall time、普通并发监察延迟、task blocking latency、completion-boundary latency |
| 机制行为 | concern exit、focal inquiry 质量、判别工具动作、grounds revision 的实际发生率 |

### 11.4 晋级判断

DCEC 只有在出现以下联合信号时才进入后续稳定性/消融：

- task success 或 completion correctness 有一致改善；
- 改善轨迹中确实出现预期的 state revision 与 decision-centered investigation；
- false blocking/错误拒绝没有明显恶化；
- 增益不能仅由更多 provider requests、token 或任务阻塞解释。

若最终分数偶然上升但 state 没有被消费，不归因于机制。若中间行为改善但任务结果未改善，保留为诊断信号，不宣布有效方法。

## 12. 候选池收束

### 当前 active

- **Main**：Decision-Centered Epistemic Control v0。
- **Comparator**：ordinary persistent Supervisor。

### 历史归档，不继续迭代

- independent verifier / C/D；
- scoped decision interface 与范围 prompt；
- A/B action selector；
- E/G structured selector，F coverage frontier；
- H2/H3/H4 与 P1/P2/P3；
- 旧 PMA 串接和其他阶段化认知候选。

这些结果仍用于解释设计取舍和论文 related-work/ablation history，但不再作为并行工程队列。

### 暂存但不进入 v0

- **Resource-Aware Closure Control**：只在完整长程轨迹重复证明“决定性证据已取得但因资源分配无法闭环”后，作为独立 closure component 重新立项；不得自动采用固定 terminal reserve。

## 13. 停止点

方法发现的微观诊断阶段已完成合成。下一步只有两个门：

1. 用户确认后实现 DCEC-v0 的最小版本并做唯一小型判别实验；
2. 若通过，直接进入 baseline vs DCEC 的完整 method_dev 长程实验。

本轮到机制规格、最小性审计和实验设计即停止。
