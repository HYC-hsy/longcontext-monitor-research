# R11 Selector Failure Anatomy

基线为 `8ff6cb7`。这是一次纯离线解剖：没有调用模型、没有修改 A/B selector、没有运行新实验，也没有开发 C/D/E/F/G。分析只使用冻结 request、原任务、六份真实首动作与回执、父 History、私有状态和本地 audit。

Selector 没有输出自由文本理由，因此本文只解释“实际可见输入＋实际动作＋真实回执”能够支持的失效机制，不声称读取了模型隐藏思维。

## 当时到底可见什么

### A：完整父上下文

R7 的 A 看到了原 Supervisor 的 95 条 History（约 181,993 个消息内容字符）、4,967 字符稳定 system、完整 178 行原任务、root-completion 决策范围、冻结索引描述及三个读取/搜索工具。History 足以知道 AppMetadata 曾被具体调查、纠偏和复查；它也包含 JSON/Sprintf 原要求。

但信息组织很不对称：History 中 `AppMetadata` 出现 52 次，`FromJSON` 19 次，`Sprintf` 14 次；AppMetadata 的直接调查延伸到第 87 条消息，而 JSON/Sprintf 最近主要停留在第 74 条附近的任务方实现摘要。完成相关措辞共出现 54 次，直到第 93 条。输入没有一个状态明确区分“直接检查过”“只是任务方声明”“尚无判别性证据”。

因此，A 并非缺少 JSON/Sprintf 文本，而是没有把大量历史组织成可比较的调查价值。它两次都选择重读最新根完成声明，属于价值排序和观察设计失败。

### B：要求侧短视图

R7 的 B 使用空 selector History，只看到完整原任务、root-completion 范围、冻结 scope/version/file-count 和三个工具。它明确看不到任务方完成摘要、父模型整体完成叙述，也看不到 AppMetadata 已调查和修复的历史。

因此 B 两次重查 AppMetadata 不能解释成“明知已经修好仍重复”。原要求按 Target 1 到 Target 7 排列，AppMetadata 是首个、最具体、最容易做符号搜索的对象；JSON 和 Sprintf 位于 Target 2/3，且真正的风险分别需要签名比较和行为语义比较。B 缺少最小 coverage state，无法区分首个要求和最薄弱要求。

### 正确小任务

两个 selector 都看到完整、仅 414 字符的两项要求，以及“冻结范围有三个文件”的索引。A 额外看到一条“任务 Agent 提议完成”的父消息，B 没有。两者都先递归 `file_list`。列目录能建立地图，却不能区分 Clamp/IsEven 的正确实现与空壳实现；其后 A 错误未决，B 用尽预算没有裁决，而 O 三次调用完成了正确批准。

## 六次首动作逐条解剖

| 序号 | 条件/状态 | 首动作 | 对象类型 | 是否有决策判别力 | 能否知道已覆盖 | 失效分类 |
|---|---|---|---|---|---|---|
| 2 | A / R7 | 读 public events 最后一行 | 任务方完成声明 | 否：真假实现都可能产生同一声明 | 能；完整 History 和 system 都说明它只是 provisional claim | Target selection + Observation design |
| 3 | B / R7 | 搜索 `type AppMetadata struct` | 已修复要求 | 否：只证明一个符号存在 | 不能；短视图删除了修复 History，又没有 coverage state | Target selection + Observation design |
| 4 | B / R7 | 搜索全部 `AppMetadata` | 已修复要求 | 否：18 个命中仍不能判断其他独立目标 | 不能；同上 | Target selection + Observation design |
| 5 | A / R7 | 读 public events 第 87 行 | 任务方完成声明 | 否：重复已有 claim | 能；该声明已在完整 History 中 | Target selection + Observation design |
| 8 | A / 正确控制 | 递归列 workspace | 工作区库存 | 否：三文件目录兼容正确与错误实现 | 不适用 | Observation design + Control allocation |
| 9 | B / 正确控制 | 递归列 workspace | 工作区库存 | 否：没有检查任何要求语义 | 不适用 | Observation design + Control allocation |

六次工具均执行成功，但首动作本身的判别性为 0/6。第 4 项最终找到了 JSON 签名冲突，是父 Supervisor 随后另行搜索 `FromJSON` 并回读原要求所得；不能反向记到 AppMetadata 首动作名下。

### 三种失败的边界

- **Target selection failure**：选错当前最值得核验的前提。R7 的完成声明和已修 AppMetadata 属于此类。
- **Observation design failure**：动作能返回信息，但正确与错误状态都可能返回相同结果。六次首动作全部具有此问题。
- **Control allocation failure**：强制前置动作占用或重组预算，使原本可完成的父调查变差。正确控制的 A/B 提供了实际证据；R7 中不能仅凭少一次父调用推定这一点。

这些分类用于生成候选，不改变 R11 原评分。

## JSON 与 Sprintf 为什么没有成为首选

不能简单说模型“忽略了答案”：

1. **位置与显著性**：A 的历史中两者存在，但 AppMetadata 的直接调查更密、更近；完成声明也更新。B 只有按 Target 1→7 排列的原任务，首个具体符号天然占优。
2. **证据类型未分层**：A 没有可消费的“直接观察 vs 任务声明 vs 摘要”覆盖前沿。JSON/Sprintf 被多次提及，容易被误当作已经覆盖，而实际上多为任务方自述。
3. **工具入口过低层**：selector 从 `read/list/search` 直接开始，没有先绑定一个会改变 root decision 的前提；满足工具语法不等于选择了有价值的调查。
4. **缺少结果反事实**：prompt 只说“most likely to obtain evidence capable of changing the decision”，没有让动作同时说明“看到 A 会支持什么、看到 B 会阻止什么”。因此完成声明、符号存在和目录库存都能被包装为“相关信息”。
5. **一调用约束的副作用**：面对复杂语义要求，安全的目录/符号动作比直接比较签名或 Set 行为更容易生成；正确小任务证明这会把预算花在地图而不是判别观察上。

## 下一批最小候选

### E. Decision-Discriminating Frontier

- 针对：Target selection 与 Observation design。
- 改变：一次 selector 调用同时产生具体前提 P、真假时应出现的两个区分结果、以及服务于 P 的一个现有工具动作。
- 唯一主要差异：首动作必须绑定 root decision 的未决前提和结果对照；父模型仍使用完整状态，预算仍为 1+5。
- 不是只加提示：用可审计、实际消费的动作接口保存 premise/outcomes/tool call；工程只验证可追溯性并执行动作，不判语义。
- 不是旧三轮选题：P、对照结果和动作在同一次模型响应中完成，没有独立问题会话。
- 淘汰：仍选已修要求/声明/库存，或写出的两个结果都不会改变完成判断，或再次拖坏正确控制。

### F. Coverage-Gap Frontier

- 针对：B 无法知道 AppMetadata 已覆盖的 Target selection/representation failure。
- 改变：只向 selector 暴露少量根相关薄弱前提，区分 claim/summary-only 与 direct observation，并保留来源和版本；不自动 PASS、不列全任务 checklist。
- 唯一主要差异：B 从“无覆盖状态”变为“有界 coverage frontier”，其余工具和 1+5 不变。
- 不是只加提示：frontier 是跨决策可审计状态，不是让模型口头“注意未验证项”。
- 不是旧三轮选题：不增加问答阶段；selector 仍只调用一次。
- 淘汰：仍反复选择已直接覆盖前提，frontier 漏掉决定性薄弱点，或盲化构造后收益消失。
- 风险：最容易退化成 checklist，或由研究者把已知缺陷泄漏进 frontier，因此首轮优先级低于 E/G。

### G. Counterfactual Observation Selection

- 针对：六次共同的 Observation design failure。
- 改变：动作执行前必须同时给出“要求正确时预期看到什么”和“要求错误时哪种不同观察会暴露它”，再发出工具调用。
- 唯一主要差异：动作按反事实区分力选择，而不是按相关性/信息量选择。
- 不是只加提示：两个 counterfactual outcomes 与可执行动作绑定在同一接口并被记录；缺字段是协议失败，语义优劣仍由研究侧审计。
- 不是旧三轮选题：仍是一调用一动作，没有额外裁判或问题阶段。
- 淘汰：继续选择 claim/file-list 并填写泛化结果，或仅让模型统一变得未决。
- 局限：G 不解决“该检查哪个要求”，因此可作为 E 的 observation-design 消融，但不应先与 F 组合。

## 理论映射边界

- 能观测性/观测设计对应“观察能否区分与当前决定有关的状态”。
- 新息对应“回执是否只是重述任务方声明或旧认识”。
- 主动诊断与实验设计对应“有限成本下选最能区分竞争解释的查询”。
- Value of Computation 对应“查询改变最终决定的潜在价值是否大于调用成本”。
- 真值/理由维护对应“直接支持、任务声明和派生摘要是否被区分并保持版本边界”。

这些理论只提供问题结构和候选灵感。当前 Agent 系统不满足经典数学前提，因此不继承最优性、稳定性或可观测性保证。

## Candidate priority

1. **E — Decision-Discriminating Frontier**
2. **G — Counterfactual Observation Selection**
3. **F — Coverage-Gap Frontier**

Why：E 同时直击 R11 的目标选择和 0/6 判别性失败，仍可限制在一个调用内；G 是最干净的观察设计消融，但不能解决目标选错；F 最能解释 B 重查 AppMetadata，却引入持久状态、泄漏和 checklist 风险，宜在 E/G 不能解决重复目标后再试。

What would falsify each：E 若仍不能选择决策前提或伤害正确控制即淘汰；G 若生成泛化反事实却仍执行 claim/list 动作即淘汰；F 若盲化生成的 frontier 仍不能改变选择，或必须依赖研究者已知缺陷才有效，即淘汰。

下一轮若获批准，最小建议是先独立比较 O 与 E，保持 6 对 1+5；G 作为观察设计消融，F 单独作为状态候选。不得组合后再追认贡献，也不得把 JSON/Sprintf 位置写进候选输入。
