# R14 Closure Budget Semantics Audit（2026-09-21）

## 0. 范围、基线与结论

- 基线：`e3d98e4`。
- 本轮只审计历史材料与生产代码；没有调用模型 API、运行实验、实现 H1、增加调用，或修改 R10--R13。
- 机器可读审计：`../runs/r14_closure_budget_semantics/budget_protocol_audit.json`。

结论先行：R12 G-r2 暴露了一个真实但尚未归因完毕的 **closure opportunity loss**。它同时涉及有限监督资源与当前诊断协议：工具回执必须等下一次 `provider.complete()` 才能被模型消费，而六次实验 ceiling 被耗尽后没有裁决机会。现有证据不能说明“固定保留第六次”是通用方法，更不能说明 reserve 后一定会正确拒绝。

`6-call` 是方法发现诊断中的 **experimental calibration**，不是理论最优值、不是当前在线 Supervisor 的 **method assumption**，也不是 **deployment invariant**。更一般的候选应称为 **Resource-Aware Closure Control**；fixed terminal reserve 只是其中一个尚未实现的实例。

## 1. `4 → 6` 的历史来源与继承链

### 1.1 最初的四次 pilot

独立核验 pilot 最初使用四次请求。`INDEPENDENT_VERIFICATION_PILOT_AUDIT_20260918.md` 与 `INDEPENDENT_VERIFICATION_CHECKPOINT_FREEZE_20260918.md` 都记录：四次对 D 的常规 `read → commit expectation → read → decide` 序列过短，因此该 pilot 被排除，B/C/D 共同 ceiling 调为六次请求、八个工具循环 turn。

这里的“protocol-limited”有严格边界：四次不能让当时的 D 协议正常展开。它不证明六次最优，也不证明真实部署应只有六次。

### 1.2 为什么是六次

历史材料支持三个目的：

1. **experimental calibration**：给已定义的 B/C/D 流程一个能够正常结束的共同上限；
2. **fair-comparison control**：三组共享相同请求 ceiling，避免 D 无限制多调用；
3. **cost containment**：限制小型诊断的 API 开销。

它没有成为：

- **method assumption**：没有理论说明有效监督恰好需要六次；
- **deployment constraint**：在线 `MonitorRuntime` 默认每次 review 最多 20 turn，而非六次；
- **compute equality**：相同 request 数没有平衡 History 长度、input/cache/output token 或 continuation 请求。pilot 报告本身已经显示 B/C/D token 成本差异很大。

### 1.3 后续继承链

六次 ceiling 随实验基础设施被继承，而非被重新理论化：

1. 独立核验 B/C/D：共同 `max_requests=6`；
2. decision-question 三路 A/B/C：`DiagnosticConfig.total_calls=6`，并明确称为 “one six-call ceiling”；
3. R7 直接调查/恢复判断；
4. R8 scope prompt / scoped decision；
5. R9 scope-prompt replication；
6. R10 neutral counterexample-consumption；
7. R11 O/A/B；
8. R12 O/G/E。

这些实验采用六次是为了冻结比较口径。它们没有把六次验证为论文机制或部署预算。

| 分类 | 本轮判断 |
|---|---|
| experimental calibration | 是：从四次 pilot 调到六次，使协议可运行并控制比较成本 |
| method assumption | 否：没有机制或理论要求恰好六次 |
| deployment constraint | 否：线上默认 review 上限是 20，另受 deadline、context、transport 等限制 |

## 2. 一个 logical call 在当前诊断里是什么

### 2.1 生产调用链

```text
run_review loop
  → CallBudget.consume()
  → provider.complete(messages, tools)       # 1 logical call
      → append current input/tool receipts to History
      → optional compaction/continuation
      → provider transport request (+ retries)
      → return assistant text/tool_use
  → host dispatches zero or more tool calls  # no logical call
  → tool receipts become next-loop messages
  → next provider.complete()                 # next logical call consumes receipts
  → ...
  → model emits finish_parent_decision
  → host validates and ends diagnostic
```

代码锚点：

- `decision_question_diagnostic.py:58-70`：`CallBudget`；
- `decision_question_diagnostic.py:420-500`：包装 `client.complete()`，每次高层调用先 `consume()`；
- `monitor_agent_core/loop.py:14-152`：模型响应、工具执行和下一轮回执；
- `monitor_agent_core/provider.py:478-508`：`complete()` 的 History 与用量提交；
- `decision_question_diagnostic.py:336-344`：诊断结束工具。

### 2.2 精确语义

- 每次高层 `provider.complete()` 尝试计一个 logical call；即使没有取得 usage 或最终失败，预算已经消费。
- 一次响应中的工具执行由宿主完成，不另计 logical call；多个工具仍属于产生它们的同一次模型调用，但会增加工具操作和 wall time。
- 工具结果在本轮响应结束后才加入下一轮输入。模型不能在产生 `file_read` 的同一个响应中看到该 read 的返回值。
- `finish_parent_decision` 不是宿主自动推断，而必须出现在某次模型响应的 tool call 中。因此第六次若选择 `file_read`，回执虽会被保存，却没有第七次模型调用在本 episode 中理解它并提交裁决。
- transport retry 与 logical call 分开：一次 `complete()` 内 `_request_batch()` 可有多次传输 attempt。retry 增加延迟与潜在成本，但不增加 `CallBudget.used`。
- private maintenance 的 `file_write/file_patch` 是普通工具：工具本身不计 logical call，但产生写操作的模型响应占用一次，并可能挤占有限 turn。
- semantic continuation/format repair 是特殊缺口：压缩路径通过 `client._request([])` 发真实模型请求，不经过 `client.complete()`，因此消耗 token、延迟和可能的费用，却不增加当前 logical-call 计数。六次 ceiling 不是完整的模型计算预算。

### 2.3 “最后一次 read 没有价值”需要限定

在当前有界诊断中，最后一次 read 不能改变该 episode 的正式评分决定；这是协议事实。在线 loop 在 turn limit 处会保存未消费回执，未来 wake 仍可能继续使用，因此不能把它泛化为“最后一次 read 在持续 Supervisor 中永远没有价值”。

## 3. 三种 closure 协议模型

### Protocol A：当前模式

```text
LLM call → tool → receipt → next LLM call → decision
```

优点是调查和裁决完全由同一通用循环组织。缺点是最后一次工具观察天然需要后续模型机会，固定 ceiling 可在“证据刚到达”时截断闭环。

### Protocol B：fixed terminal reserve

```text
总预算 B
前 B-1 次：可调查
第 B 次：只能裁决
```

它不增加 logical-call ceiling，但减少最后一次调查自由。它只在“固定 B 且 episode 必须当场裁决”的部署假设下自然。它可能修复 closure opportunity loss，也可能让关键反例本来需要第 B 次调查时更早失败。

公平比较应让 O 与 reserve 条件拥有相同总调用、模型、证据和工具；差异仅是最后一次 affordance。但这仍只检验固定 reserve，不证明它适用于在线 20-turn review 或动态预算。

### Protocol C：closure 不与 investigation budget 竞争

```text
最多 B 次调查推理
+ 一个固定 finalization opportunity
```

这在概念上把 episode termination 与 investigation computation 分账，可能更接近“系统最终必须输出控制动作”的部署接口。但 finalization 仍是昂贵 LLM 推理，不能称为真正免费。

若采用 C，公平方式只能是：

1. 对所有条件都使用相同的二维预算 `investigation ≤ B, closure ≤ 1`；或
2. 让 baseline 同样获得相同总模型调用，并完整统计最后调用的 token、费用和延迟。

给 treatment 一个未计成本的第七次、而 O 仍只有六次，会混淆机制与更多计算。论文可把 closure opportunity 单列，但总 API 成本仍必须计入。

## 4. 真实在线 Supervisor 与诊断 harness 的差异

### 4.1 在线不是六次不变量

在线路径为：

- `MonitorRuntime(... max_review_turns=20)` 默认传给 `MonitorAgent`；
- 每次 wake/root completion 调用 `monitor.review()`；
- `run_review(... max_turns=self.max_review_turns)` 在通用工具循环内调查；
- root handoff 时模型可在任意响应发 `allow_complete` 或 `intervene`，并无专门的第六次 finalization stage。

因此：

```text
6-call is not a deployment invariant.
```

在线路径仍有相同的模型—工具交替：若某一 review 的最后允许 turn 读文件，它也需要未来模型请求才能消费回执。但在线默认 ceiling 是 20，而且 History 持续存在；这与六次离线 episode 的计分终止不同。

### 4.2 在线资源约束

线上至少受以下资源共同约束：

- 每 review 的 `max_review_turns`（默认 20）；
- 整个 run deadline（默认构造参数 `run_timeout_seconds=10000`，可由绝对 deadline 覆盖）；
- root completion 等待告警/等待时间与运行 deadline；
- provider connect/read timeout、有限 transport retries 与恢复 deadline；
- context window、History char limit、压缩与 continuation；
- token/API cost（记录，但当前不是统一硬 ceiling）；
- 工具 wall time；
- 并发监察下的 task blocking latency：普通调查应并发，静默→唤醒和 root completion 屏障会阻塞任务侧推进。

调查、纠偏、等待和完成都从同一 review turn 循环产生模型响应；`intervene` 可通过 live callback 立即送达且继续观察，`wait`/`allow_complete` 结束 review。它们没有各自固定六次配额。continuation 还会产生 CallBudget 未覆盖的额外请求。

## 5. R12 G-r2：事实与反事实边界

### 5.1 轨迹直接支持的事实

1. global call 1 的 selector 没有遵守唯一结构化 action 协议；其直接 `file_read` 没作为 selector 观察执行。
2. 父阶段 call 2--4 依次读取/搜索完成声明、`NewAllStrings` 与修复后的 `all.go`。
3. global call 5 搜索 `FromJSON`，取得真实签名冲突；回执明确只剩一个 logical call，并要求以 `finish_parent_decision` 结束。
4. global call 6 继续读取 Desktop，而没有提交正式裁决。
5. 因此本六次诊断 episode 丢失了 closure opportunity；这不等同于已知若有机会裁决就会作出正确决定。

### 5.2 轨迹不能支持的反事实

- 去掉 selector 后模型一定沿相同路径、并一定成功；
- 强制第六次 finish 后模型一定正确拒绝；
- 无限预算一定解决问题；
- 限制第六次工具后一定不会发生格式失败、未决或错误批准；
- G 的失败完全由预算造成。G 的 selector 协议失败和 observation quality 仍是独立问题。

所以本轮只确认：`closure opportunity lost`；不确认：`the missing decision would have been correct`。

## 6. Resource-Aware Closure Control 候选卡

### 6.1 研究对象

> 在有限监督资源下，如何避免 investigation 消耗掉形成有效控制决策所需的剩余资源。

它只覆盖：已经或接近取得足够证据后，能否完成控制闭环。它不解释为何选错目标、不读 JSON/Sprintf、重复 AppMetadata，或忽略已有材料。

### 6.2 可能实例（均未选择、未实现）

#### RACC-1：fixed terminal-call reserve

- 针对：固定 episode ceiling 下最后一次工具回执无法消费。
- 假设：episode 必须在固定 B 内正式结束，且提前裁决价值高于第 B 次调查。
- 真实成本：不增加 call ceiling，但可能牺牲一次调查；token 可能变化。
- 公平比较：O 与 treatment 同总调用，唯一差异是最后一次工具权限。
- 淘汰证据：经常阻止第 B 次关键取证、并未提高完成裁决，或使正确状态更多未决/误拒绝。

#### RACC-2：adaptive stopping / reserve

- 针对：调查价值已低或已有决定性证据时仍继续读。
- 假设：可由通用、非领域特化信号判断剩余资源与 closure 需求；不能预知正确答案。
- 真实成本：可不增加 call，但需要状态/协议信息，可能改变模型可见 token 或控制逻辑。
- 公平比较：相同总资源 ceiling；预注册停止规则，不按结果回看调整。
- 淘汰证据：停止信号不能在不泄漏答案的情况下可靠产生，或过早停止损害取证/正常放行。

#### RACC-3：separate investigation / closure accounting

- 针对：把必须发生的 termination decision 与可选调查竞争同一一维配额。
- 假设：部署接口保证一个结束机会，并接受二维预算。
- 真实成本：通常增加一次真实模型推理；绝不能叫免费。
- 公平比较：所有条件同样获得 `B investigation + 1 closure`，并报告总 calls/tokens/cost/latency；或按总计算严格匹配。
- 淘汰证据：额外 closure 只增加成本而不改善有效决定，或普通 O 在相同总计算下同样有效。

### 6.3 当前状态

`design candidate; no implementation selected`。原 H1 固定第六次 reserve 降级为 RACC-1 实例，不再代表整个候选。

## 7. 与 retrieval/control 主线的关系

候选池应拆成两条：

### A. Investigation / retrieval control

解释“看什么、为何没有读取关键证据、为何重复旧局部、怎样选择有判别力的观察”。R13 表明 JSON/Sprintf 一旦取得 direct evidence，通常能被正确使用；这里仍是当前主要瓶颈。

### B. Closure / resource control

解释“已有或接近足够证据时，是否还保留形成控制决定的资源”。R12 G-r2 是直接线索，但只来自当前诊断 ceiling。

二者可能最终组合，但目前没有组合实验依据，不能统称为一个 Supervisor 改进。

## 8. 预算单位审计

### 8.1 为什么 call count 适合当前小型诊断

- 明确、确定、易冻结；
- 表示顺序性模型决策机会；
- 能揭示工具回执至少需要下一次推理这一协议结构；
- 便于 O/A/B/G/E 等相同 harness 的粗粒度比较。

### 8.2 它遗漏什么

- input/output/cache/reasoning token 的巨大差异；
- 模型/路由的美元成本；
- continuation/format-repair 等绕过 `complete()` 的真实请求；
- transport retry 与失败请求；
- wall-clock latency；
- task blocking latency；
- 文件/搜索/code execution 的操作数、I/O 与运行时间。

### 8.3 正式实验至少同时报告

1. logical model calls，以及所有真实 provider requests/attempts；
2. input/output/cache token，模型与可得美元成本；
3. supervisor wall time；
4. task blocking latency（并发架构的关键部署指标）；
5. tool operations、失败率及工具 wall time；
6. completion-boundary latency 与普通并发监察延迟分开。

当前小型诊断可继续用 logical calls 作硬 ceiling，但 token/cost 与 latency 应是共同主要报告量，而不是事后附注。call count 不能单独代表有限预算 Supervisor 的全部资源。

## 9. 决策与停止点

- 不实现 H1；不把最后一次强制 finish 视为已选方法。
- 候选改名为 Resource-Aware Closure Control，并保留三个可证伪实例。
- 六次继续只描述现有诊断协议；任何后续实验若采用不同 closure accounting，必须对 baseline 同样适用并报告全部真实成本。
- retrieval/control 仍是主线；closure 只是独立的后段控制问题。
- 本轮无模型、无实验，到此停止。
