# R13 Evidence Lineage 与 Provenance 审计（2026-09-21）

## 1. 边界与结论

- 基线：`31f7958`
- 模型 API 调用：0
- 新真实实验：0
- 未实现 H1/H2/H3/H4、P1/P2/P3；未修改或重跑 R10--R12。
- 主要材料：R7 真实根交接检查点及其派生局部修复状态，R7--R12 完整父 History、私有状态、public events、synopsis/compaction、tool receipts、冻结 workspace 与既有结果。
- 机器可读谱系：`method_discovery/runs/r13_evidence_lineage/evidence_lineage.json`。

**核心结论：当前证据不支持优先实现 H3 或更重的 provenance knowledge state。** 三个对象的原要求、工具来源、文件身份和版本大多仍存在于冻结 History/回执中；主要失败发生在 Supervisor 没有选择、读取或消费这些材料。确有两类较窄的表示问题：

1. task summary/compaction 与部分最终结论会把 `Task Agent claims X complete` 弱化成无来源限定的 `X complete`，并把文件存在/局部修复扩大成目标或整题完成；
2. `monitor/state/working.md` 在 AppMetadata 修复后没有修订，R7--R12 所有检查到的副本哈希完全相同，持续保留早期 open issues。

但这些不足尚不能解释 JSON/Sprintf 的主要失败：两者的原要求和相关代码始终可读；Sprintf 的任务摘要甚至明确写出 `Set() is no-op`，Supervisor 仍很少调查它。一旦 JSON/Sprintf 的 direct observation 被实际取得，模型通常能够推翻旧完成判断。因此，本批更支持 **retrieval/control failure 为主，派生表面上的 source/scope loss 为辅**。

本轮没有观察到“同一基础 claim 经 summary、working note、later conclusion 后，被最终决策当作多份独立证据计权”的充分证据。文本重复和显著性确实存在，但不能据此宣称 duplicate inflation 已成立。

## 2. 材料身份和时序

主检查点：

- 来源 run：`clean-monitor-fyn-2.2.0-roadmap-dual-opus48-root-capture-20260919-r5`
- `review_id=82b7bf855a6d4a4fb1b741a8271b6ce0`
- provider request sequence：45
- task turn：44
- public event cursor / archive sequence：87
- live capture time：`1789829921.342458`
- 派生检查点版本：`2b4e0b49d8e767bc980dcaad5958d600b3de40397da2408806731e2894e42799`

`cp-local-repair` 只新增研究侧 NewAllStrings 修复。AppMetadata、JSON、Sprintf 相关文件与 source root checkpoint 逐字节相同：

| 对象 | 文件 | SHA-256 |
|---|---|---|
| AppMetadata | `app.go` | `f779269e...b1cec` |
| AppMetadata | `app/app.go` | `bf06a426...640e4` |
| AppMetadata | `app/meta.go` | `2036ee2d...c54d6` |
| AppMetadata | `app_test.go` | `a8b3190f...3b70` |
| AppMetadata | `test/testapp.go` | `6b89747e...55be9` |
| JSON | `theme/json.go` | `e92c5d7a...14b9` |
| Sprintf | `data/binding/sprintf.go` | `e635966a...a830` |

因此，R7--R12 派生诊断中 JSON/Sprintf 与 post-repair App 观察不存在“后来代码变了、旧证据继续被当作当前证据”的混杂。App 在真实任务 turn 30--34 的修复前后确有版本变化，runtime 可以检测这一变化；是否语义上已充分修复仍需模型或研究侧判断。

provider History 快照没有给每条 message 保存独立 wall-clock timestamp。本审计没有伪造时间：对这些条目标记 `timestamp=null`，同时保留准确 message index、review/request identity、最近 task turn；public events 则使用原始 `archived_at`。

## 3. AppMetadata lineage

### 3.1 可追溯链

1. **original requirement**：`original_task.txt:27-46` 要求字段、所有 App 实现的 `Metadata()`、package-level `SetMetadata` 和默认值。完整原文也在 provider History message 2；Supervisor 后来再次读取对应行。
2. **task-agent claim**：event 25 / turn 13 宣称 Target 1 complete。
3. **direct observation**：History messages 39--63 读取 `app.go`、`app/meta.go`、实现搜索与原要求，发现 defaults、package function、dummy/test implementations 三个缺口。原始 tool receipts 保留路径、范围、hash 或 command output。
4. **private note**：`working.md:48-81` 写入三个 open issues，并保留所有七个目标的任务理解。
5. **intervention**：History message 68 发送三个有依据的纠正；event 57 显示 Task Agent 接收。
6. **repair**：events 59/63/67（turn 30--34）修改 defaults/package function/dummyApp/testApp。
7. **post-repair observation**：History messages 76/80/87 直接读取修复文件；message 88 判断这三个缺口已解决并转向 NewAllStrings。
8. **task summary/root claim**：`IMPLEMENTATION_SUMMARY.md:6-19` 与 event 87 把 Target 1/整题标为完成。
9. **later reasoning**：R7 root 及多份 R9--R12 结论把 AppMetadata 作为“已完成”；R11 requirement-side selector 两次又把 AppMetadata 选为首要检查对象。

### 3.2 四类失效

- **source_identity_loss：部分成立。** 原始 tool receipts 没丢来源；最终 prose 常把它折叠为 `Target 1 complete`。但主要 post-repair 支持确实来自 direct observations，因此不能把所有简写都当成错误。
- **derivation_or_duplicate_inflation：未证实。** claim、summary、root claim 多次重复，但没有轨迹证明最终裁决把它们当成多份独立观察计权。
- **scope_or_version_inflation：scope 成立，version 局部成立。** App 的局部修复证据后来参与 whole-task approval；pre-repair note/观察在版本变化后没有被显式 supersede。post-repair 文件到 R12 没再变化。
- **retrieval/control failure：成立。** 完整 History 已有 post-repair reads，模型仍重复选择 App；同时 `working.md` 一直是修复前版本。这里是 stale private state 与历史显著性共同影响选择，而不是 raw provenance 缺失。

**为什么 AppMetadata 持续成为焦点？** 它是唯一形成“direct defect → intervention → repair → post-repair reads”的长而显著 episode，又是 working note 唯一展开成 open issues 的目标。R11 selector 选择它更符合显著性/控制偏好，而不是证据缺失；轻量 provenance 标签未必能降低这种锚定，除非还改变 state revision 或 retrieval policy。

## 4. JSON Theme lineage

### 4.1 可追溯链

1. **original requirement**：`original_task.txt:50-76` 明确 API 签名、JSON schema、hex、variant、Fonts/Icons。
2. **task-agent claim**：events 27/29 创建 `theme/json.go`，随后宣称 Target 2 complete。
3. **task compaction**：event 74 的 `key_info` 只保留 `Target 2 COMPLETE - theme/json.go created`。这里 `Task Agent claims` 的来源限定消失，file-created 被组织成 target status。
4. **task summary**：`IMPLEMENTATION_SUMMARY.md:21-29` 再次标完成，且写出的 `FromJSON(data []byte)` 既不等于原要求，也不等于实际代码。
5. **root claim**：event 87 声称 all 7 complete/tests passing。
6. **false approvals**：R7 root、R9 root records、R11 多份 false approvals 没读 `theme/json.go`，却以 summary/claim/sparse checks 表述 JSON complete。
7. **direct observation**：R8 root prompt-control、R10 local-support-r1、R11 B-r2、R12 G-r2 读取/搜索实际定义并回看原要求，发现 `FromJSON(data string, base fyne.Theme)` 多了参数。完成机会存在时会拒绝；R12 G-r2 因预算用尽没有 finish。

### 4.2 四类失效

- **source_identity_loss：成立。** event 74 将 claim 压成无来源 `COMPLETE`；部分 root prose 把 task-authored summary 称为 completion evidence，而不再清楚区分 claim 与 observation。
- **derivation_or_duplicate_inflation：未证实。** claim → compacted status → implementation summary → root claim 的派生链清楚，但没有直接证据表明模型把四者当四份独立支持；可以说重复提高显著性，不能说已发生独立计权。
- **scope_or_version_inflation：scope 成立，version 不成立。** “文件已创建/有函数/构建测试声明”扩大为 JSON target 和 whole-task complete；JSON 文件在 R7--R12 未变化。
- **retrieval/control failure：强成立且为主因。** 直接观察一旦被选择，模型能精确发现冲突。多数错误批准的关键差别不是 provenance 字段有无，而是没有读取实现/要求。

## 5. Sprintf binding lineage

### 5.1 可追溯链

1. **original requirement**：`original_task.txt:80-95` 与 `working.md:20-24` 都保留 reverse `Set()` + `fmt.Sscanf` 要求。
2. **task-agent claim**：events 31/33 创建实现，随后 task memory 把 Target 3 记为 complete。
3. **task compaction**：event 74 保留 `Target 3 COMPLETE - sprintf.go created`，不保留 direct/claimed 区分。
4. **task summary**：`IMPLEMENTATION_SUMMARY.md:31-40` 同时写 `Target 3 ✓` 和 `Read-only bindings (Set() is no-op)`。这意味着语义冲突已经存在于模型可读材料内，不需要额外 provenance graph 才能暴露。
5. **false approvals**：R7/R9/R11 的多份整体批准沿用 summary/claim，没有读取实现，也没有把 read-only 与 reverse-write 原要求对照。
6. **direct observation**：R10 neutral local-support-r1 先读原要求，再对 frozen Sprintf implementation 做有范围的 reverse-Set 搜索；零命中后把它表述为 apparent concern，并据此限制 completion。

### 5.2 四类失效

- **source_identity_loss：成立于 compacted status/final prose。** 原要求与 contradictory summary 本身没有丢。
- **derivation_or_duplicate_inflation：未证实。** 仍只有重复/显著性证据。
- **scope_or_version_inflation：scope 成立，version 不成立。** file creation、reactive Get 和 task summary 被扩大为满足 reverse Set 及整题完成。
- **retrieval/control failure：强成立且为主因。** 甚至 summary 内已有 `Set() is no-op`，但没有被选中与 requirement 比较。

**为什么 Sprintf 更少进入调查？** App 有显著的纠偏 episode 和 stale open note；JSON 有容易搜索的显式 `FromJSON` API 名称，并在多个诊断里成为自然的下一个目标。Sprintf 的关键缺口需要重新读取较早的详细行为要求，再把它与 `Set` 的语义实现对照。它在 History 中位置更早、没有 repair episode，而且 summary 的“read-only”说法被 `Target 3 ✓` 包裹。这些都指向 target selection、历史显著性和语义取证成本，不是 requirement/provenance 没有保存。词频仅用于定位记录，不作为上述结论依据。

## 6. 三对象对照：representation vs retrieval/control

| 现象 | AppMetadata | JSON | Sprintf | 判定 |
|---|---|---|---|---|
| 原要求仍可见 | 是，且多次重读 | 是 | 是，working note 也保留 | 非 representation omission |
| direct observation | 大量，修复前后都有 | 少；一旦出现即推翻 claim | 极少；出现后形成 concern | 调查选择不均 |
| 私有状态更新 | 未随修复更新 | 只有简短任务理解 | 只有简短任务理解 | App 有 state revision 缺口 |
| claim → summary 来源弱化 | 有，但有独立 direct support | 明显 | 明显 | 派生表面 provenance loss |
| local → whole scope 扩大 | 是 | 是 | 是 | completion evidence drift |
| 版本陈旧 | pre-repair App 有；post-repair 无 | 无 | 无 | 不支持普遍 version 问题 |
| 直接证据取得后能否利用 | 能 | 通常能 | 能形成正确 concern | retrieval/control 是主要瓶颈 |

逐项判定：

1. **Representation omission：不成立于三个原要求。** 它们都在原任务和 working note 中。
2. **Source qualification loss：局部成立。** task compaction、summary-derived status 和一些结论删弱了 `claimed/direct` 区分。
3. **Scope inflation：成立。** 文件存在、局部修复和任务方摘要被扩大到目标/整题完成。
4. **Duplicate inflation：不成立。** 没有足够的决策引用证据。
5. **Version inflation：只在 App 早期 private note/观察成立；不是 JSON/Sprintf 的解释。**
6. **Retrieval/control failure：三者均成立，JSON/Sprintf 最清楚。**

因此，R13 不支持“先实现 H3 Evidence-Type Active View”。它最多支持保留一个低成本 P1 作为未来独立消融：不是因为系统没有 provenance，而是检验在派生材料上保留来源/范围/版本标签是否能减少 claim 被无资格消费。P2/P3 当前应推迟。

## 7. Runtime-deterministic provenance 边界

| 字段 | runtime 可确定？ | 可安全生成的内容 | 不能自动声称的内容 |
|---|---|---|---|
| `source_type` | 是（粗粒度） | original task、task message/summary、tool result、private file write、intervention 等通道身份 | claim 是否真实、summary 是否充分 |
| message/tool/file identity | 是 | review/request/message index、tool_use id、virtual path | 文件内容是否满足语义要求 |
| timestamp/turn | 有记录时是 | archived_at、task_turn、request sequence | 缺失时推测精确时间 |
| workspace/checkpoint version | 是 | checkpoint id、manifest hash、run identity | 同版本意味着语义正确 |
| file hash | 是 | read 时 hash、checkpoint hash、后续 hash | hash 变化是否影响某要求 |
| read/search range | 是 | path、lines/offset、query scope、truncated/more、success/failure | 零命中意味着全仓库不存在；局部 read 意味函数不存在 |
| summary direct inputs | 部分 | synopsis `raw_event`、生成请求当时可见消息集合 | summary 具体用了哪些输入、是否忠实；当前 working note 无逐句依赖 |
| repair time/changed files | 是（机械层） | write/patch event、时间、路径、pre/post hash | 修改构成语义 repair、repair 完整 |
| `version_changed_since_observation` | 是 | observation hash 与当前 hash 是否不同 | observation semantically stale |
| derived relation | 部分 | “在包含这些输入的请求中生成”、summary-to-raw-event link | 精确语义依赖、独立性权重 |
| evidence scope | 机械范围是；语义范围否 | 读了哪个文件/哪几行/搜索什么范围 | 此观察支持 API、行为、target 或 whole-task 到何种程度 |

设计红线：runtime 可以写 `task_agent_claim`，不能写 `claim_false`；可以写 `version_changed_since_observation=true`，不能写 `evidence_invalid`；可以写 `read lines 1-100, more=true`，不能写 `function absent`。

## 8. 最小表示候选（仅设计，不实现）

### P1 — Provenance tags only（仅保留为可选最小消融）

- **机制**：给现有 claim/summary/tool receipt/private-note 引用附粗粒度 `source_type`、路径/消息身份、实际读取范围、workspace/hash 与 version-changed 标记。不建 knowledge base，不自动判真，不改变调查顺序。
- **新增持久状态**：每个已存在 artifact/reference 约 5--8 个短 metadata 字段；不复制正文。
- **模型可见 token**：若只在当前被展示的材料上渲染，预计每项约 15--40 tokens；必须设总项数/总 token 上限。
- **新增调用**：0。
- **runtime 字段**：通道来源、request/tool/file identity、时间/turn、hash、机械读取范围、版本变化。
- **LLM 字段**：语义支持范围、真假、是否足以改变决定。
- **避免 checklist**：只标记本来已出现/被读取的材料，不枚举所有要求，不生成 PASS/FAIL。
- **避免泄漏**：标签来自通道和 manifest；不含 JSON/Sprintf 名称、预期标签或研究评价。
- **应改变的现象**：若 source loss 真有因果作用，root reasoning 应更少把 task-agent summary 当 direct observation；它不应自动解决“根本没读 JSON/Sprintf”。
- **直接淘汰**：同预算下仍以 claim/summary 直接批准，或只增 token/措辞而不改变证据消费；正确控制变慢/未完成。
- **本轮状态**：`deferred instrumentation candidate`，不是 H3 晋级。需要用户另行确认才实现。

### P2 — Bounded evidence view（推迟）

- **机制**：仅在 root completion 等边界，从已有材料中展示少量当前相关 evidence items，保留来源/版本/范围；不列全任务 PASS/FAIL。
- **新增持久状态**：理想情况下无，按需投影现有索引；若需要“相关性”缓存则必须单列。
- **模型可见 token**：预计 300--1,000 tokens/边界，取决于 3--8 项及摘录；无实测。
- **新增调用**：0。
- **runtime 字段**：可提供 provenance/index；**“当前相关的少量项目”通常需要策略或模型判断**。
- **LLM 字段**：相关性、语义 scope、是否足够。
- **避免 checklist**：硬上限少量 items，不覆盖所有 requirements，不输出状态表。
- **避免泄漏**：只能从当前部署可见材料按通用规则选；不得用研究者已知 JSON/Sprintf 位置。
- **应改变的现象**：理论上降低 stale App episode 对 JSON/Sprintf 的遮蔽。
- **直接淘汰**：选中项仍由显著性主导，或 view 需要已知缺陷/新模型调用才能有效。
- **本轮状态**：`not justified`。R13 尚未给出通用、无泄漏的相关性选择机制；贸然实现会把 retrieval policy 混入 representation。

### P3 — Minimal lineage state（推迟/当前不建议）

- **机制**：持久保存 item id、source、derived-from、version relation；不传播真假，不做 TMS/ATMS。
- **新增持久状态**：随事件/summary/note 线性增长的节点与边；维护成本显著高于 P1。
- **模型可见 token**：若原样展示会很高，必须再有 query/view；这又引入 retrieval 机制。
- **新增调用**：可为 0，但语义 derived-from 无法全靠 runtime 准确生成。
- **runtime 字段**：机械生成 request-parent set、tool/file/version 边；不能确定逐句语义依赖。
- **LLM 字段**：语义派生、支持关系、是否独立。
- **避免 checklist**：节点围绕实际 artifacts，不按 requirements 建表；但图仍可能变成隐式 checklist/knowledge base。
- **避免泄漏**：只记录运行中已出现的节点，研究评价不入图。
- **应改变的现象**：只有 duplicate inflation/source derivation 真是主因时才应改善。
- **直接淘汰**：无法证明重复派生被决策独立计权，或模型仍不检索图；本轮已满足前一淘汰信号。
- **本轮状态**：`do not implement`。

## 9. H1 与 provenance 候选保持独立

- **H1 Terminal Budget Reserve** 是 control/closure safeguard：保证最后一次调用可用于裁决，针对 R12 已见的“取到反例但没有 finish”闭环损失。其历史预算审计结果冻结保留。
- **P1/P2/P3** 属于 epistemic representation/consumption 候选：处理来源、范围、版本在派生材料和判断中的可见性。
- 二者理论上可组合，但当前没有组合实验依据。不得因为叙事完整把 H1 与 P1/H3 一起实现或一起归因。

## 10. 停止点

本轮到此停止。结论不是“provenance 无用”，而是：

1. raw runtime provenance 已经比先前假设完整；
2. 主要瓶颈是选什么、读什么、何时停止调查并作决定；
3. 表示层真正暴露的是 derived surfaces 的 source/scope qualification 与 stale private note；
4. 尚无 duplicate inflation 证据支撑 P3/TMS；
5. H3 不应按原优先级直接实现。P1 仅作为最低成本、可证伪的独立候选保留，P2/P3 推迟。
