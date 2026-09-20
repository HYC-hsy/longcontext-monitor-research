# R10 之后的候选池：调查策略而非最终字段

审计基线：`70536ba`。本文件是研究侧候选登记，不是模型输入，也不授权自动启动真实调用。

## 当前证据边界

R10 V1 的直接 JSON 证据条件 2/2 拒绝、局部支持条件 1/2 拒绝、正确合成控制 2/2 批准，但方向性 `material_condition` 曾进入模型输入。因此先完成去标签校准，不能直接把 V1 当作证据内容的独立效果。

当前工作假设是优先改善“怎样取得能够改变当前决定的观察”。R9 范围提示、R8 复杂最终接口、三轮串行选题和独立核验 C 均不自动恢复。

## 第一批：已完成首次真实筛选（当前形态淘汰）

### A. 完整父上下文上的单步调查动作

- 目标失败：根完成时仍有要求未被有效检查，但局部修复后直接结束监督。
- 动作：一次同模型调用在完整父 History、原要求和当前决策范围上直接选择一个现有 `file_read`、`file_list` 或 `text_search` 调用；不先生成自由文本问题，不输出真假标签。
- 执行：真实工具回执作为“当前新增观察”交回从同一 H0/S0 恢复的父 Supervisor；父模型最多再用五次调用调查和裁决。
- 预算：选择一次与父调用合计最多六次；非法、多动作或失败选择不重试、不返还预算。
- 对照：普通六次自由调查。若有效，后续仍需相同 1+5 分配的一般单步选择控制。
- 停止条件：没有改善决定性实现的自主读取和真实反例发现，或只增加未完成。

### B. 要求侧短视图上的单步调查动作

- 目标失败：选取位置持续被父 History 和任务方完成叙述锚定。
- 动作：与 A 使用相同的一次选择、相同工具和 1+5 预算，但选择器只看原要求、当前决策范围及客观查询范围/版本索引；不看完成总结和全局完成措辞。
- 父状态：真实回执仍返回保留完整父 History 的 Supervisor；B 不是独立判决 Agent，也不是 C。
- 必要对照：与 A 独立比较，不能先叠加；报告短视图长度和信息差异。
- 停止条件：选中目标和有效证据没有改善，或只重复同一浅检查。

当前代码入口：`method_discovery/investigation_action_candidates.py`。首次真实筛选使用普通 O、A、B 三个独立条件，在 R7 错误整体状态各运行两次、正确小型控制各运行一次，共九份。结果见 `R11_INVESTIGATION_ACTION_SCREEN_RESULT_20260921.md`。

### A 的筛选状态

- 两次 R7 首动作都读取任务 Agent 的根完成声明，没有取得独立、可区分完成真假的观察；父 Supervisor 随后均错误批准。
- 正确控制首动作只是列出 workspace，之后错误声称原任务不在可访问范围并给出未决；普通 O 能正确批准。
- 当前结论：`screened out for current form`。保留代码和轨迹，不进入在线验证，不继续润色选择器。

### B 的筛选状态

- 两次 R7 首动作都检查已修复的 AppMetadata，而非未覆盖要求。一次仍错误批准；另一次父 Supervisor 在后续搜索中发现 JSON 签名冲突并正确拒绝，但该反例不是首动作取得的，且结论又错误声称其他目标看来完整。
- 正确控制首动作只是列出 workspace，随后六次预算耗尽而未裁决；普通 O 能正确批准。
- 当前结论：`screened out for current form`。只有一次不稳定的后续调查信号，不能支持“要求侧短视图改善了动作选择”。保留候选及具体失败轨迹，不晋级。

六次 A/B 选择动作都成功执行，但零次首动作本身取得能区分根完成判断的证据。首次运行中两个重复轮次曾因私有目录身份缺失在零模型调用时失败；原失败被保留，只对这两份做了定点工程恢复。有效的预算未完成记录没有重跑。

失效解剖见 `R11_SELECTOR_FAILURE_ANATOMY_20260921.md`。后续候选必须分别说明：选择哪个目标、设计什么观察、怎样分配控制预算。

## 第二批：由 R11 失效机制生成，R12 已完成首次筛选

### E. Decision-Discriminating Frontier

- 失效来源：A/B 没有先选择会改变 root completion 的前提；六次首动作均无判别力。
- 最小机制：单次调用同时输出具体 premise、支持/阻止完成的两类 discriminating outcomes，以及一个立即执行的现有 read/list/search 动作。
- 预算：仍为 1+5，不增加三轮问题阶段。
- 机制边界：结构与真实回执由接口保存，工程不判断 premise 或 outcomes 的语义正确性。
- 最小对照：O 的 6 次普通调查 vs E 的 1+5；错误根状态与正确控制都必须保留。
- 直接淘汰：仍选择已修目标、任务声明或库存，两个结果不能改变决定，或正确控制继续退化。
- 竞争解释：结构化输出本身、额外推理或单纯保守化可能解释变化。
- R12 结果：`screened out for current form`。R7 两次中 selector 分别直接调用旧 `code_run` / `file_read`，没有提交结构化 premise/outcomes/action；一次父调查仍错误批准，一次预算耗尽。正确控制虽成功提交 premise，却以 `file_list` 尝试验证函数签名、行为与测试，最终把完整任务判为未决。没有观察到 E 相对 G 或 O 的增益。

### F. Coverage-Gap Frontier

- 失效来源：B 删除完整 History 后不知道 AppMetadata 已修复，连续两次选择 Target 1。
- 最小机制：只保存少量根相关薄弱前提，标明当前支持是 claim/summary-only 还是 direct observation，并保留来源/版本；不自动 PASS，不列全量 checklist。
- 预算：状态维护不增加独立 selector 之外的调用；实际 token/维护成本必须另报。
- 最小对照：同一短视图与 1+5 下，无 frontier vs 盲化生成的 frontier。
- 直接淘汰：仍选择已直接覆盖前提、漏掉决定性薄弱点，或只有研究者注入已知缺陷才有效。
- 竞争解释：顺序变化、泄漏或 disguised checklist 可能带来假收益。
- 当前状态：保持关闭。R12 的 R7 selector 在形成目标之前即发生协议失败，不能证明它在知道 coverage 的情况下再次选择已覆盖目标；正确控制的库存式动作属于 observation design/control allocation 失败，也不足以触发 F。

### G. Counterfactual Observation Selection

- 失效来源：完成声明、符号存在和目录库存都“有信息”却不能区分正确/错误。
- 最小机制：一次响应内先写出要求正确/错误时应出现的不同观察，再绑定一个真实工具动作；没有独立问答阶段。
- 预算：仍为 1+5。
- 最小对照：保持可见上下文不变，只比较旧动作接口与 counterfactual-bound action 接口。
- 直接淘汰：输出泛化反事实后仍读 claim/list，或只增加未决而不增加有效证据。
- 竞争解释：更长推理而非反事实结构可能解释收益；G 也无法单独修复 coverage 缺失。
- R12 结果：`screened out for current form`。R7 两次 selector 都直接调用旧 `file_read` 而未提交反事实结构，父调查均耗尽；其中一次父调查随后找到真实 JSON 签名冲突，但没有剩余调用提交裁决，属于控制预算损失，不能归因于 G。正确控制中的反事实文字彼此不同，但实际 `file_list` 只能观察库存，不能观察其声称的签名与行为差异，最终错误保留未决。

R12 预注册比较结果为：O 在错误根状态 0/2、正确控制 1/1；G 为 0/2、0/1；E 为 0/2、0/1。G/E 都没有改善错误状态，并明显拖坏正确控制。当前停止结构化 selector 路线，不继续增加字段；F/C/D仍关闭。完整逐记录审计见 `R12_DISCRIMINATING_SELECTOR_SCREEN_RESULT_20260921.md`。

## 第三批：调查与闭环资源候选（仅设计）

R10--R12 对照审计见 `R12_PARENT_INVESTIGATION_AND_BUDGET_AUDIT_20260921.md`。父 Supervisor 曾使用原有 `file_read` / `text_search` 自主取得 JSON/Sprintf 反例；R12 G-r2 也在接近预算边界时取得 JSON 证据，却把剩余唯一调用继续用于调查而没有裁决。R14 进一步限定：这只直接证明当前六次诊断丢失 closure opportunity，不能证明固定 reserve 会产生正确决定。下一批不再增加独立 selector，并把 investigation/retrieval 与 closure/resource 分开研究：

1. **Resource-Aware Closure Control（原 H1 的上位候选）**：研究有限监督资源下怎样保留形成有效控制决定的机会。固定 terminal-call reserve 只是尚未实现的一个实例；另有 adaptive stopping/reserve 与 investigation/closure 分账。R14 已确认六次只是诊断 calibration、不是在线部署不变量，因此不再把候选写成“强制保留第六次”。
2. **H3 Evidence-Type Active View**：按可确定的来源类型组织已有证据，不生成要求PASS表，不判断真实性。
3. **H4 Evidence-Linked Tool Affordance**：在现有 read/list/search 上可选携带当前核验对象，并让回执明确操作实际支持的证据类型与范围；不增加wrapper或调用。
4. **H2 In-band Decision-Relevant Investigation**：在现有父循环和私有状态中维护一个可修订的当前决策前提；不设独立选题阶段或最终结构化裁决表。

R13 lineage 审计后，原 `H1 > H3 > H4 > H2` 只保留为 R12 时点的历史排序，不再作为当前实现顺序。四者仍均未实现、未调用模型。R14 已冻结 H1 的历史预算审计，并把它改写为上位的 Resource-Aware Closure Control；没有选定任何实例。R13 显示 raw History/tool receipts 中来源、范围和版本大多仍可追溯，JSON/Sprintf 的主要失败是未选择或未消费已有直接证据，而不是缺少 provenance 数据；没有证据证明派生 claim 被最终判断当作多份独立支持。因此 H3 不晋级实现，P2/P3 推迟。只保留 P1 provenance tags 作为需另行确认的低成本 instrumentation/消融候选；它不能替代调查选择。F/C/D继续关闭。

### R13：轻量 provenance-aware epistemic state 审计

完整审计见 `R13_EVIDENCE_LINEAGE_AND_PROVENANCE_AUDIT_20260921.md`，机器可读谱系见 `../runs/r13_evidence_lineage/evidence_lineage.json`。

- **AppMetadata**：有完整的 direct inspection → intervention → repair → post-repair reads；但 `working.md` 没有随修复更新，R7--R12 检查到的副本 hash 全相同。重复关注更符合 stale private state 与显著性/控制失败。
- **JSON**：task claim/compaction 会弱化来源限定；多数错误批准未读实现。一旦读取实际 API 并回看原要求，模型能识别冲突。主因是 retrieval/control，伴随派生表面的 source/scope loss。
- **Sprintf**：原要求一直保留，任务 summary 甚至明确写 `Set() is no-op`，但仍很少进入调查。该反例不支持“缺少 provenance 才无法判断”，反而支持 target selection/consumption failure。
- **duplicate inflation**：未证实。claim、summary、root claim 重复存在，但没有轨迹证明最终裁决将其当作相互独立的支持计权。
- **version**：pre/post App 修复变化可由 runtime 确定；JSON/Sprintf 及 post-repair App 在 R7--R12 冻结材料中未变化。runtime 只能标 `version_changed_since_observation`，不能自动标 `semantically_stale`。

当前表示候选状态：

1. **P1 Provenance tags only**：`deferred instrumentation candidate`。只为当前已显示材料附确定性的 source/version/read-range 标签，0 新调用、不建 KB、不列 requirement checklist。只有另行批准并在等预算对照中减少无资格 claim 消费时才可晋级。
2. **P2 Bounded evidence view**：`not justified`。它必然混入“哪些材料相关”的 retrieval policy，当前不能把收益归因于 representation。
3. **P3 Minimal lineage state**：`do not implement`。没有 duplicate inflation 证据，且语义派生关系不能由 runtime 可靠自动生成。

Resource-Aware Closure Control 与这些候选保持独立：前者是 closure/resource control，P1--P3 是 epistemic representation；当前没有组合实验依据。R13 的 investigation/retrieval 主线也必须与 closure 分开：后者只能处理“已经或接近取得足够证据后怎样完成闭环”，不能解释为何没有读取 JSON/Sprintf 或为何重复 AppMetadata。详见 `R14_CLOSURE_BUDGET_SEMANTICS_AUDIT_20260921.md`。

### theoretical_inspiration（设计依据，不是效果证明）

能观测性/观测设计、新息、主动诊断/实验设计、Value of Computation 与真值/理由维护分别帮助描述“能否区分状态、是否只是重复、有限预算如何查、查询能否改变决定、支持来源是否被混同”。当前 Agent 系统不满足经典理论的数学前提，不继承其最优性、稳定性或可观测性保证。

## 后备：当前明确不开发

### C. 证据来源去重与认识依赖维护

只有在真实轨迹证明“同一来源经摘要、笔记和续接被当成多份独立支持”后才开发。候选会保留来源和派生关系，但当前没有足够离线因果链证据。主要风险是维护成本、错误谱系和仅增加字段。

### D. 有区分力的行为探针与反例确认

只有在监察者已经能选中正确要求、但浅层阅读仍无法区分正确与空实现时才开发。优先复用读代码/搜索；执行探针若扩大权限，必须单列协议和安全验收。当前不开放无约束 `code_run`。

## 共同规则

- 理论启发、诊断信号、候选初筛、独立复验和在线效果分别报告。
- A/B 共享底层工具、预算和评价方式，但保持独立条件。
- 工程只执行动作并保存范围、版本和失败；“调用过工具”不等于语义核验成立。
- 所有调用均计入预算；未完成、未知、错误拒绝和正确拒绝分开。
- 当前 Fyne 派生状态已参与设计，不再是留出集；有效候选仍须在未参与设计的状态上复验。
- 本文件、`AGENTS.md`、审计报告、评价标签与已知缺陷不得进入 Supervisor 或选择器输入。
