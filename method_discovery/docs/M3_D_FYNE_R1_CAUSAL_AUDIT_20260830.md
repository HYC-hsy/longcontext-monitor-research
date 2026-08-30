# M3-D Fyne 2.2 R1 完整因果审计

日期：2026-08-30
状态：离线审计完成；未修改方法代码；未启动新任务；候选尚未接受
运行：`m3-m3d_decision_sufficient_control-fyn-2.2.0-roadmap-r1`

## 1. 审计问题与边界

本次审计不以快速提出补丁为目标，而是回答：

1. 任务为什么在 500 turn 附近仍没有形成可接受的根完成；
2. 任务 Agent 是在一个局部问题中循环，还是不断发生新的根任务偏移；
3. M3-D 的 bounded inquiry 是否实际限制了调查；
4. 监察者哪些判断帮助了任务，哪些行为增加了负担或未能改变任务轨迹；
5. 失败可能分别来自任务难度、任务 Agent 长程状态、监察认知、D 的生命周期实现、并发调度和归档基础设施中的哪一层。

在线运行没有使用 native verifier、gold patch、隐藏测试或 checker。任务由人工提前终止，
没有 native verifier 分数。以下结论只基于公开任务、任务 Agent 公开轨迹、监察决策、干预
交付事件、provider usage 和运行归档。未完成不能直接计作方法 0 分，局部绿测也不能计作任务
成功。

## 2. 运行完整性与事实摘要

- 公开事件起止：`2026-08-30T11:14:18.419619Z` 至
  `2026-08-30T12:49:33.908980Z`，约 95 分 15 秒。
- 任务 Agent 到达 turn 479；终止前最后一次 provider 调用可能未形成完整响应。
- `public_trajectory.jsonl` 的最后完整归档为 turn 473；turn 474--479 仍可在
  `agent_stdout.log` 中恢复。
- 任务 Agent provider usage：479 次调用，683,687 uncached input、214,341 output、
  967,937 cache creation、9,204,882 cache read token。
- 监察 provider usage：239 次调用，5,584,864 input、201,323 output、3,939,200
  cached input token。
- 正式监察决策：96 份；49 份产生非空干预候选，异步普通路径最终 ready/injected 各 13 次。
- 异步干预从源决策到任务 Agent 消费平均相差 7 turns，中位数 7，范围 3--11 turns；
  ready 后通常在约 0.03 秒内注入，主要延迟发生在监察形成 ready 之前或任务 Agent 已继续推进。
- 根 completion proposal 共 11 次，全部得到 `CONTINUE`；没有 `allow_complete`。
- 监察注意模式为 patrol 3 次、focused 93 次。
- D inquiry 生命周期记录为 opened 1 次、carried 27 次、switched 11 次、closed 0 次。
- 发生 3 次监察 JSON protocol retry，其中 2 次恢复；最后一次与 completion worker 重建重叠。
- 监察 worker 共被停止/重建 10 次，原因均为 `completion_priority_reconstruction`，不是普通
  后台审议阻塞任务 Agent。
- Harbor 父 `result.json` 仍保留 `n_running_trials=1` / `finished_at=null`，这是杀死 launcher
  后没有完成终止记账的陈旧状态，不表示任务仍在运行。

## 3. 证据归档自身存在真实损坏

`research_events.jsonl` 共可严格解析 6,195 条记录，另有 25 行不能作为独立 JSON 解析。
这些不是 PowerShell 默认编码造成的假阳性：损坏行包含 JSON 中段、尾段或两个并发事件的
拼接片段，例如 monitor context、provider request 和 history transform 内容被拆到独立行。

这说明至少一个 append-only 归档在多进程/多线程并发写入时没有保证整条 JSONL 记录的原子性。
它没有被证明直接改变在线模型行为，但带来三个实际影响：

- provider request/response/usage 总数存在小幅低估可能；
- 部分监察唤醒与上下文视图无法完全按事件 ID 重建；
- 后续若以这些事件计算精确延迟、成本或因果顺序，会把记录缺失误判为模型没有观察。

因此，本报告只对 decision 文件、public trajectory、stdout 和可解析事件相互印证的事实作强
声明；无法交叉验证的部分保留为不确定。

## 4. 任务轨迹不是单一局部循环

### 4.1 前半程：真实契约缺口被逐步修复

监察者先后发现并纠正了多项真实问题：

- `MainMenu.Refresh` 缺失、`Menu.Refresh` 只有占位行为；
- `ToolbarAction.SetIcon` 只写字段而没有刷新；
- `Hyperlink.OnTapped` 调用 callback 后仍继续打开 URL；
- menu/main-menu 双向 Refresh 形成递归；
- 为 tray 增加非需求 getter 扩张了 `desktop.App`；
- ordinary menu refresh 可能错误替换当前 tray menu；
- `Entry.SetMinRowsVisible(0/-1)` 错误覆盖默认行数；
- `NewAllStrings` 完全遗漏；
- `StringToStringWithFormat` 和 `NewSprintf` 缩窄了明确契约；
- Bytes 支持及其测试曾被 Agent 尝试删除；
- App interface 扩张没有覆盖所有 concrete/test implementations。

这些干预多数不是完美主义：它们直接对应原始公开要求，且 Agent 在收到后确实修改代码、测试
或撤销错误方案。M0/M1/M2 保留下来的契约重建、证据能力区分、意图级纠偏和冲突重开仍有
明显正作用。

### 4.2 中段：反复发生“局部绿测 -> 根任务完成”的错误提升

任务 Agent 在 turn 122、202、213、228、280、291、297、355、378、394、473 共 11 次提出
根完成。每次都仍有公开的硬 obligation 缺失、实现未接入生产路径、测试 oracle 不充分，或把
未完成状态报告当成最终交付。监察者全部拒绝完成是有根据的。

因此，长时运行的直接现象不是“监察者不准 Agent 交卷”，而是 Agent 多次把某一局部 slice 的
成功错误提升为全局成功。监察者能阻止 unsupported closure，却没有让 Agent 获得一个在后续
压缩和 repair 中持续稳定的根任务完成模型。

### 4.3 turn 378--410：根任务表示发生明显塌缩

最强证据出现在 turn 378--394：

- Agent 说需要重新寻找最初 roadmap；
- 随后声称拿不到完整 roadmap，只能记录“存在什么”而不是实现要求；
- 它生成状态报告，并把当前工作重述成与原始七个 targets 不一致的范围；
- 监察者在 completion boundary 重新注入精确根要求后，Agent 才恢复 Target 2 实现。

这不只是一般的代码困难。stdout 显示 Task Agent history 在本次运行中 58 次发生实际压缩/消息
移除；后期前台 `earlier_context` 只保留原任务头尾的缩略片段。原始用户任务名义上仍存在，
但精确条款不再始终处于 Agent 可直接利用的工作上下文。Agent 的 working checkpoint 又被自己
的局部结论和完成报告污染，因此出现“任务就在历史里，却认知上认为拿不到”的状态。

监察者有独立的原任务和 69 项 root obligation ledger，因此可以在完成边界重建要求；但这些
状态没有成为任务 Agent 持续可消费的根任务认知，只在发现冲突后以用户式消息局部注入。这解释
了为什么纠偏每次有效，却需要反复发生。

### 4.4 turn 414--470：局部 URI inquiry 实际是收敛的

这一段不能归类为无价值无限验证：

1. 监察者指出 Fonts/Icons URI 分支没有任何行为证据，而实现会静默吞掉 load error；
2. Agent 写一个同时验证两个资源 map 的有界测试；
3. 测试失败后，调查依次区分 resource lookup、URI parse、repository availability 和 test setup；
4. 最终发现 file repository 需要 caller-side 注册；
5. 在不弱化原 payload assertions 的情况下补齐测试环境；
6. 原 focused test 通过，Agent 在 turn 470 立即把 Target 2 标为完成并回到全局 suite/root completion。

这是 D 所追求的“结果会改变下一动作、得到结果后停止局部调查”的行为级正证据。调查用了约
26 turns，但每一步都缩小同一个可观察失败的因果范围，且没有继续追查通过后的内部细节。

问题在于后台生命周期没有忠实记录这段语义收敛：它把每次自然语言改写都记作 `switched`，
turn 470 的实际完成没有形成 `closed`，到 turn 473 仍显示旧 inquiry 为 `carried`。

### 4.5 turn 473--479：根任务再次被错误闭合，但纠偏仍被吸收

Agent 在 turn 473 用“4/5 targets verified”报告再次提出完成，把 Target 4/7 混合并保留
MenuItem compatibility 与 production tray integration 缺口。completion 监察者明确指出：

- Target 4 是 Menu/MainMenu runtime refresh；
- Target 7 是独立 `desktop.App` interface；
- 当前报告没有证明窗口/tray refresh production path；
- 根任务不能因部分 targets 绿测而结束。

Agent 随即在 turn 474--479 承认“MAJOR ERRORS IDENTIFIED”，重新读取 `menu.go` 和
`driver/desktop/app.go`，准备继续修复。人工终止发生在这次 uptake 之后，因此不能知道它最终
能否完成。但已经足以证明：监察信息可被理解，问题不是 Agent 完全不服从；问题是 uptake 没有
转化成跨长程稳定的根任务状态。

## 5. M3-D 生命周期实现与模型行为之间的脱节

### 5.1 291 轮的 inquiry 在语义上早已被替代，后台却持续 carry

decision 58 在 turn 291 打开 inquiry，等待一个不执行测试 binary 的全库 compile observation。
turn 297 后，监察者已转向 tray production path、public struct compatibility、validator symbol 等
不同问题；但模型在最小输出中省略了可选 `discriminative_step`，后台将省略解释为继续保留旧
inquiry。直到 turn 414 模型再次显式提供 URI inquiry，旧状态才被记作 switched。

所以 `carried 27 次` 不能全部解释为模型执着于 compile 问题；相当一部分是陈旧状态自动继承。

### 5.2 closure 的协议要求与“可选自然 working note”冲突

当前模型提示把 `discriminative_step` 描述为可选自然工作笔记，并要求“clear it”；后台只有在
模型显式输出空字符串/空 mapping，或 focused repair 释放到 patrol 时才真正关闭。字段省略在
minimal frontstage 下既不更新也不关闭对象。

模型正常地不重复一个已经不再重要的可选字段时，工程语义却是“旧 inquiry 仍开放”。因此
0 closed 首先证明的是生命周期协议没有和模型自然表达对齐，不能直接证明模型从未停止思考。

### 5.3 exact text equality 把同一 inquiry 的自然推进误标为 switch

turn 414、423、427、432、441、442、445、450、455、461、465 的工作笔记都围绕同一 Target 2
URI 证据债逐步更新，但后台以完整文本相等判断 identity。任何重述、结果吸收或下一子观察变化
都会重置 opened turn/cursor，并把旧 inquiry 关闭为 switched。

结果是：

- 无法测量一个语义 inquiry 的真实年龄和 probe 次数；
- “切换到新问题”与“同一问题根据证据自然推进”不可区分；
- 每次文本变化都会让 boundedness 计数重新开始；
- 实验原本预注册的 closure latency 失去可信测量基础。

### 5.4 inquiry closure 与 focused 调度没有形成有效控制通路

D 管理的是 `discriminative_step`，而监察唤醒密度主要由另一个 `open_episode` 和 attention mode
控制。此次早期 repair episode 长期不释放，93/96 决策保持 focused。提示又规定“有另一个具体
repair 需要跟踪时不要回 patrol”。在一个始终有根缺口的七目标任务上，这个条件几乎永远成立。

因此，即使 Target 2 URI inquiry 在行为上已经 decision-sufficient，关闭该 inquiry 也不必然：

- 关闭过宽 repair episode；
- 把 attention 降为 patrol；
- 降低 intent/result 边界的强模型审议密度；
- 阻止下一个根 completion 重新触发全量重建。

这解释了为什么 D 可以改善一次局部调查，却没有带来全局收敛和成本停止。机制的状态变量与
真正控制调度的状态变量是脱节的。

### 5.5 inquiry 没有与“等待的公开结果”建立可审计关联

minimal wake 只告诉模型：有 inquiry、archive cursor 前进、公开活动已发生。它不告诉后台哪一
条 tool result 回答了哪一个 inquiry；每次仍由模型主动读取轨迹并重新理解。模型在 URI 段做到了，
但 compile inquiry 被遗漏，说明这依赖偶然的自然语言续接而不是稳定生命周期。

这不是要求 online checker 判断结果对错。当前缺失的是更基础的可观测关联：某个已选择的公开
probe 是否已经返回，以及旧 inquiry 是否已被后续行动事实上替代。语义裁决仍应属于同一监察者。

## 6. 监察者帮助了什么，又没有帮助什么

### 已有正能力

- 能从原始任务而非 Agent 自述恢复遗漏要求；
- 能分辨 compile、局部绿测、mock 自证、pipeline exit 0 和 production behavior 的证据能力；
- 能在错误意图落成过程中连续纠偏，而不只在最终交卷时检查；
- 正确推进时多数不重复向 Agent 发消息；
- completion boundary 能阻止 11 次有公开反证的错误闭合；
- 普通后台监察、protocol retry 和 worker 重建没有冻结任务 Agent；
- 形成的 13 次异步输入均在下一安全模型边界注入，没有破坏正在执行的普通工具。

### 尚未达到的能力

- 不能把一次纠偏转化为任务 Agent 持续可用的根任务认知；
- focused repair 没有清晰的局部/根层级，导致一个 episode 横跨多个 targets；
- D 的 inquiry 状态不忠实反映模型实际上在调查什么；
- 对 Agent 的干预形成平均落后 7 turns，仍弱于人工在高风险 repair 中的贴身响应；
- completion 控制是有效安全阀，却变成 11 次重复的事后兜底；
- 监察者主要阻止错误完成，没有在每次 release 后帮助 Agent 保留一个简洁、稳定、可继续执行的
  根任务视图。

## 7. 成本与并发行为

D 的总监察输入约 558 万 token，高于 C-r2 的约 390 万；但 D 也运行到 479 task calls，而 C-r2
在约 209 calls 被终止。按 task call 归一化：

- C-r2：170 / 209 = 0.81 monitor calls per task call；
- D-r1：239 / 479 = 0.50 monitor calls per task call。

所以 D 不能简单描述为“每一步监察更密”：按任务推进归一化，监察调用密度反而下降约 39%。
但任务没有完成，总运行更长，最终绝对成本仍更高。单次随机运行、provider 时延和不同任务轨迹
使该比例不能作为 D 优于 C 的正式结论。

13 次异步干预的 ready-to-inject 通常很快，说明队列交付不是主要延迟；从监察依据形成所在 turn
到任务 Agent 消费仍相差 3--11 turns，平均 7。一次 source turn 374 的 ready 候选在队列中约
93.7 秒后才注入，属于明显异常。当前并发设计实现了“不冻结任务”，但没有达到人工 focused
阶段几乎连续跟随的响应上界。

11 次 completion proposal 中 10 次触发 worker stop/restart。它们是为 completion priority 主动
重建而非崩溃，但反复重建会丢弃在途普通 review，并使 decision 序列出现同 turn 重复和一次
turn 122 -> 121 逆序。此次共有 7 处相邻 decision turn 非递增。没有证据显示它直接导致错误
干预，但它削弱了状态更新的时序确定性。

## 8. 可能根因分层

### 8.1 高置信根因

1. **任务 Agent 的根任务表示不能跨长程 repair 稳定存活。** 证据是反复 completion、turn
   378--394 的任务范围丢失、被精确根要求重新注入后立即恢复。
2. **D 的 lifecycle capture 不忠实。** 可选字段省略会 carry、文本改写会 switch、实际局部结束
   不会 close；0 closed 与真实行为矛盾。
3. **局部 inquiry 与 focused/open repair 调度脱节。** inquiry 的 decision sufficiency 不能直接
   结束深审议或缩小 repair episode。
4. **根 completion 目前是反复纠错的安全阀，而非一次最终边界。** 11 次 CONTINUE 表明
   unsupported closure 被抓住，但上游认知没有稳定修复。
5. **JSONL 并发归档不可靠。** 25 行真实断裂使精确实验测量受污染。

### 8.2 中等置信原因

1. **任务规模放大了状态失真。** 69 个细粒度 obligations、7 个相对独立 targets、Go public API
   compatibility 和 GUI production path 使局部成功很容易遮蔽根状态；但同题正是候选公平比较
   所需，不能因此把失败全归咎于“题出得不好”。
2. **Agent 自写 completion report/checkpoint 成为污染源。** 多份 `IMPLEMENTATION_SUMMARY`、
   verification report 和“complete” checkpoint 反复进入后续工作记忆，使自述证据与根契约竞争。
3. **监察干预通常很长且包含多个 obligation。** 许多消息约 800--1,500 字符，能纠正具体问题，
   但也可能让 Agent 把当前提醒当作新的局部任务，而不是恢复完整根任务。
4. **完成重建与后台 review 的竞态增加认知断裂。** worker 重建、重复 turn 决策和 freshness
   替换可能让连续 focused episode 的状态更新次序不稳定。

### 8.3 仍不能由本次运行确定

- 如果不使用 D，完全相同随机轨迹是否会更快或更慢完成；
- URI inquiry 的 26 turns 是否是最小必要成本，还是强模型可在更少观察中定位 repository setup；
- MenuItem unkeyed literal compatibility 与新增字段要求是否在该任务中本身不可同时满足；
- turn 479 后 Agent 是否可能在剩余 21 turns 内完成；
- 无监察 baseline 在本题上是否也会发生同样次数的错误 completion；
- 25 行事件损坏是否漏掉了少量 provider usage 或 intervention freshness 事件。

## 9. 与 M3-C R2 的审慎比较

M3-C R2 的决定性失败是：binding reactive behavior 已有足够证据后，监察仍继续深入 callback
精确次数、queue ordering 和 sentinel。D-r1 没有原样重现这个具体 failure；Target 2 URI 段在
测试通过后实际停止，并回到根任务。这是 D 的有限正信号。

但 D 没有获得可接受的全局结果，且新增 lifecycle 没有记录出一次真实 close。它把 C 的
“缺 decision stopping”转化成了两个更具体的问题：

- 模型可以在局部行为上停止，但工程状态不知道它已经停止；
- 即使局部停止，任务 Agent 仍会在根层错误闭合，focused scheduler 也不会因此释放。

所以不能据本次单例裁决 D 优于 C，也不能把 D 简单判为无效。更准确的结论是：D 提出的局部
decision-sufficient 思想获得一个行为级正例，但其生命周期测量和对全局控制的作用链没有成立。

## 10. 当前审计裁决

本次运行提供了足够证据说明当前 M3-D 不能作为冻结版本：任务未完成、根状态反复塌缩、D 的
核心 closure 指标不可测、focused 未释放、绝对成本很高。

同时，不应回退 M0--M2 已有能力，也不应把 D 的全部思想判死。值得保留的事实是：监察者能
发现真实偏移，任务 Agent 能及时吸收，局部 URI inquiry 能沿单一判别链收敛，异步架构没有把
普通监察重新串行化。当前主要失败发生在“局部认知、工程生命周期、调度状态、根任务持续表示”
四者没有形成一个一致控制循环，并叠加了至少一项错误的根契约解释，而不是模型完全没有智能
或监察完全无效。后续复核证据见第 12 节。

本报告刻意不指定下一版实现方案。后续设计应先由用户决定：优先修复 D 的生命周期真实性与
调度作用链，还是把更高优先级放在任务 Agent 可持续消费的根任务状态与 completion 前闭合上。

## 11. 原始证据路径

- trial 根目录：
  `long_context_bench/output/m3_real_tasks/human_gap_increments/m3d_decision_sufficient_control/fyn-2.2.0-roadmap/jobs/m3-m3d_decision_sufficient_control-fyn-2.2.0-roadmap-r1/fyn-2.2.0-roadmap__FDP7Urf`
- 任务输出：`agent/agent_stdout.log`、`agent/agent_stderr.log`
- 公开轨迹：`agent/m0_monitor/public_trajectory.jsonl`
- 监察决策：`agent/m0_monitor/decision_0001.json` 至 `decision_0096.json`
- 研究事件与 token：`agent/research_events.jsonl`
- 原始公开任务：`agent/m0_monitor/original_public_task.txt`
- D 实现规格：`method_discovery/docs/M3_D_DECISION_SUFFICIENT_IMPLEMENTATION_REPORT_20260830.md`
- C 对照审计：`method_discovery/docs/M3_C_FYNE_R2_CAUSAL_AUDIT_20260830.md`

## 12. 带着“四层一致控制循环”假设回看轨迹后的复核

### 12.1 可证伪判据

如果四层已经形成一致控制循环，则一个局部 observation 得到结果后，应同时看到：

1. **局部认知**：监察模型吸收结果，更新或结束当前问题；
2. **工程生命周期**：inquiry、decision focus、repair episode 和 root state 与该语义变化一致；
3. **调度状态**：已结束的局部问题不再维持旧的 focused cadence；
4. **根任务持续表示**：局部结果写回根任务进度，任务 Agent 后续不会把已知缺口遗忘或把局部
   完成提升成全局完成。

只要四者在关键转折点同步更新，原判断就应被推翻。实际轨迹没有满足该条件，但也暴露出一个
不能归入“四层脱节”的独立语义错误。

### 12.2 同一最终快照中的直接不一致

turn 473 后保存的 authoritative/checkpoint state 同时包含：

- `open_repair_episode = repair-280-56`，revision 21；其最初问题是 App implementation
  compile coverage，当前 residual 已变为 menu refresh、desktop interface 和 compatibility；
- `m32_observation_plan.updated_turn = 291`，仍要求每 3 turns 观察一次旧 compile-only 命令；
- `m3_decision_focus.updated_turn = 465`，仍关注 URI test 的 caller-side file repository setup；
- `m3_discriminative_step.updated_turn = 465`，仍等待一个实际上在 turn 470 已经通过的 URI test；
- `last_internal_turn = 473`，最新语义问题却已经是根 completion 对 Target 4/7 的错误闭合；
- root ledger 的 69 项 obligation 仍全部为 `unknown`。

这不是不同文件的偶然历史归档。它们都是下一次 monitor wake 可读取或直接用于运行控制的当前
状态，却分别停留在 turn 280、291、465 和 473 的不同问题上。

### 12.3 根 ledger 实际没有维护任务进度

逐个统计 decision 1、25、40、56、58、59、70、75、78、80、85、89、95、96，
`root_obligation_audit` 始终为：

> `unknown: 69`

`m1_workspace.json` 最终也显示：

- `update_count = 0`；
- 69 个 root obligation 全部 `updated_turn = 0`、`state = unknown`；
- `semantic_impact_history = 0`；
- 只有三个由 repair 控制生成的 episode object，其中两个 inactive、一个从 turn 280 延续到
  turn 473。

但这不是监察模型没有尝试维护状态。`research_events.jsonl` 中有 98 次
`root_obligation_semantic_binding`：模型每次提交 1--29 条自然语言 sparse root updates；98 次
全部 `updates_bound = 0`，全部带 binding ambiguity。主要失败形式是：

- `Target 2.3: Fonts and Icons URI resource overrides` 一类自然语义引用，被判为
  `unmatched or duplicate`，虽然它显然对应两个已初始化 obligation；
- `Menu.Refresh re-renders ...`、`MainMenu.Refresh ...` 等语义等价重述也无法绑定固定条目；
- completion 时模型偶尔同时给 sparse updates 和 full snapshot，整笔事务因 mixed representation
  被拒绝；
- 后台坚持原子事务，任一引用歧义会保留全部旧 ledger，因此没有部分正确更新能够落地。

所以当前 persistent root state 实际只保存了“原始要求目录”，没有保存“每项要求当前由什么
证据支持、争议、失效或仍未知”。更准确的因果链不是“模型没有维护”，而是：

> 模型用自然语言表达了状态变化
> -> 工程 binder 无法把语义重述绑定到固定 obligation
> -> 98 次事务全部回滚
> -> 模型下一次醒来仍得到 69 UNKNOWN
> -> completion 只能再次临场重建。

这解释了监察者为什么仍能发现遗漏，却不能把本轮验证稳定积累成下一轮完成判断。它也是结构化
状态限制模型的直接实例：上下游都是同一个模型，模型自身能理解的语义更新却无法穿过中间绑定
层回到它的下一轮上下文。

代码复核进一步确认这是 prompt/runtime 契约错配：prompt 明确允许 `short exact quote or
unambiguous natural reference`，并承诺 runtime 绑定自然变化；实际 binder 只接受规范化文本完全
相等或唯一的字符串包含关系，不做语义绑定。模型遵守 prompt 所提交的 `Target N: ...` 式自然
引用，因措辞与初始化 clause 不构成字面包含而全部失败。该失败是确定性的，不是本次模型偶然
选词不佳。

### 12.4 局部认知与 lifecycle 的明确反例

URI slice 提供了最干净的对照：

- turn 465：模型正确记录“测试注册 file repository 后，pass 即释放 inquiry”；
- turn 469--470：相同 payload assertions 通过，Task Agent 明确结束 URI 调查并进入全局 suite；
- turn 473：Task Agent 已在做 root completion，不再调查 URI；
- 但 checkpoint 仍保留 turn 465 inquiry，decision 96 把它记成 `carried`，而不是 closed。

因此模型/Agent 的实际局部行为已经结束，工程生命周期却没有结束。这直接证实第一、二层脱节，
不是根据总成本反推出来的猜测。

### 12.5 lifecycle 确实影响调度，而非无害陈旧字段

调度记录显示：

- turn 0 的 patrol plan 为 20 turns；
- turn 118 和 262 曾真实回到 patrol；
- turn 277 再进入 focused；
- turn 291 把 observation plan 改为 3 turns；
- 此后直到 turn 465，所有后台 scheduled review 都携带这个 `updated_turn=291` 的 3-turn plan；
- 总计 60 次 scheduled review 中 57 次为 focused，仅 3 次 patrol。

运行时代码在 focused 下不等待 patrol distance，而会在每个公开 intent/result 边界尝试跟进；
completion `continue_task` 又被代码直接规范化为 focused。只要模型不主动回 patrol，旧 repair
episode 就继续保留；任何新干预只更新同一 episode 的 current residual 并增加 revision。

所以状态不一致确实进入了控制路径：旧 plan 虽在 focused 分支中不直接决定等待距离，但
`attention=focused` 和未释放 repair episode 决定了密集唤醒；completion CONTINUE 又持续强化
该状态。它不是单纯影响日志美观。

### 12.6 根任务表示没有从监察层传回执行层形成闭环

任务 Agent 在 turn 378--394 丢失 roadmap 范围，监察者在 turn 394 重新给出精确七 targets
后，Agent 在 turn 396 立即恢复 Target 2 实现。这证明：

- 监察者当时拥有足够根任务知识；
- Task Agent 当时没有可操作地保留同等知识；
- 一次干预能恢复，但恢复结果没有成为稳定根状态。

之后 Target 2 通过，Agent 又在 turn 473 把七 targets 重述为“4/5 verified”，再次混淆 Target
4 和 7。监察者再次恢复根任务，Agent 在 turn 474--479 又立即正确回到 Menu/desktop 文件。

这两次“精确注入后立即恢复、长程推进后再次塌缩”是第四层没有闭环的直接行为证据。

### 12.7 重要反证：四层脱节不是唯一原因

监察者从 turn 297 起把旧 unkeyed `MenuItem` literal 兼容性作为 confirmed conflict，并在
turn 355、374、378、394、473 等根边界持续将其作为阻塞。这个判断过强：

- 公开任务同时明确要求给 `MenuItem` 增加 `Icon` 和 `Shortcut` 两个字段；
- Go 的 unkeyed struct literal 必须提供当前全部字段，因此无法同时增加字段并保持旧 positional
  literal 继续编译；
- 官方 solution patch 也直接在 `MenuItem` 末尾增加这两个字段；
- 官方 Target 4 tests 使用 keyed literals，并没有要求旧 unkeyed literal 继续编译。

因此监察者把宽泛的 “Existing APIs remain unchanged” 具体化成了一个任务本身、官方 solution
和 verifier 都没有满足的条件。它随后要求 Agent 寻找“同时增加字段又维持旧 literal”的方案，
制造了不可闭合的 repair residual。

这是一项**错误的根契约解释**，不是 lifecycle bookkeeping 问题。即使四层完全同步，只要同步
的是这个错误目标，系统仍可能无限 focused。它也是 turn 297--394 长期不收敛的重要独立原因。

### 12.8 另一项观察误差

decision 96 以“搜索没有找到 `driver/desktop/app.go`”支持 Target 7 未完成；但 Task Agent 在随后
turn 478 直接列出并打开了该文件。未找到公开 diff 或搜索结果只能支持“尚未观察到”，不能支持
文件不存在。监察者最终要求继续检查而不是直接要求重写，因此损害小于 unkeyed literal 误判，
但它表明根 completion 重建中仍存在“未观察到 -> 不存在/冲突”的证据升级风险。

### 12.9 复核后的因果判断

原假设得到部分确认，但必须改写为联合原因：

> 当前 M3-D 没有把局部认知、工程生命周期、调度状态和根任务持续表示组成同一个闭环；同时，
> 监察者至少一次把模糊兼容性目标错误提升为不可满足的硬条件。状态脱节让旧问题、旧节奏和空
> 根 ledger 长期存活，错误任务模型则让这个循环即使获得更多证据也无法正确释放。

证据支持的因果顺序更接近：

1. Task Agent 长程压缩和局部报告导致根任务表示漂移；
2. monitor completion reconstruction 能发现许多真实遗漏，但根 ledger 不积累进度；
3. 某次重建把 unkeyed compatibility 误设为硬 blocker；
4. 所有后续干预被吸收到同一个长期 repair episode，completion CONTINUE 强制 focused；
5. D 的局部 inquiry 可以在行为上收敛，但 lifecycle 不关闭，也不能改变 focused 调度；
6. Task Agent 再次错误完成，循环重新开始。

因此不能只“把四个状态字段同步起来”就期待问题解决；也不能只改 prompt 让模型少检查。下一步
若进入设计，至少要分别处理状态闭环真实性与根契约/warrant 的可修订性，并通过同题轨迹验证
二者不会互相放大。本节仍只做归因，不预先指定实现。

## 13. 带着既有五项问题再次回看后的新增发现

本节不把第 12 节已经确认的现象换名重复计数，而是专门检查：在“根状态未积累、生命周期未闭合、调度长期 focused、任务 Agent 根任务漂移、根契约误判”之外，是否还有独立进入控制链的问题。结论是有，其中前三项已经在本次运行中实际发生；第四项是被现有状态写入失败暂时遮蔽、但修复 binder 后会立即暴露的并发风险；第五项是独立的归档工程问题。

### 13.1 新问题一：根 ledger 的初始化表示本身不正交

69 项初始 obligation 并不都是互相独立的原子要求。末尾 completion criteria 又重复汇总了前面的具体条款：例如 0060 重复 JSON theme 的 0011--0025，0061 重复 reactive binding，0062--0068 又分别重复 MenuItem、toolbar、Menu、Hyperlink、Entry、NewAllStrings 和 desktop App。与此同时，0059 的宽泛“Existing APIs remain unchanged except constructor changes”与任务明确要求增加接口方法和 struct 字段之间存在需要解释的张力。

这带来两个实际后果：

1. 监察者按人类方式说“Target 4 已有证据”时，可能同时对应若干细项和一个汇总项，天然不是唯一绑定；
2. completion 重建会把同一语义既当详细 obligation 又当 completion criterion 再审一次，而宽泛兼容性条款又容易压过明确的局部变更要求。

因此，root-state 失败不只发生在写入 binder；其上游任务表示也制造了歧义和重复审计。这是独立于模型能力的 representation defect，并且与论文研究的 representation omission / unsupported closure 主问题直接相关。

### 13.2 新问题二：状态写入失败没有回到监察者的认知回路

`research_events.jsonl` 中共有 98 个 `root_obligation_semantic_binding` 事件，全部是 `updates_bound = 0`。模型实际提交过 1--29 条自然语言状态更新，但 runtime 因 unmatched/duplicate 或 mixed representation 保留旧 ledger。

关键不只是“更新失败”，而是这些 `ambiguities` 没有进入后续 monitor history、cognitive checkpoint 或下一轮可见的写入确认。于是下一轮模型仍看到 69 个 UNKNOWN，却不知道：

- 自己上一轮已经尝试更新；
- 哪些引用没有绑定；
- 事务为什么整体回滚；
- 应该重述引用、拆分更新，还是要求工具协助定位。

这形成了一个缺失的 action--acknowledgement channel：监察者的“动作”是状态修订，但环境既未确认成功，也未把失败作为 observation 返回。98 次重复失败因此不是模型简单健忘，而是闭环在 actuator acknowledgement 处断开。这是比“根状态没有维护好”更底层的新原因。

### 13.3 新问题三：repair episode 没有稳定的语义作用域

最终开放的 `repair-280-56` 最初针对 concrete App implementation 的 compile coverage，最终却承载了 menu refresh、desktop interface、compatibility 以及 root completion 等问题：

- 从 turn 280 持续到 turn 473；
- revision 达到 21；
- 累积 21 个 challenges；
- 单个 episode 序列化后约 57 KB。

实现允许每次新干预继续改写同一 episode 的 `current_residual` 和 `current_exit_condition`，但没有根据问题是否仍属同一因果修复链来关闭或切换 episode。于是“干预后持续跟踪直到确认”被实现成“只要没有回 patrol，后续异质问题都并入同一 repair”。这会同时污染连续认知、扩大每次唤醒上下文，并让 focused attention 获得一个长期不释放的工程锚点。

这不是否定持续 repair loop；相反，它说明 repair 的持续性必须服从语义连续性，而不能只服从一个仍为 open 的布尔状态。

### 13.4 新问题四：异步决策的状态提交缺少单调性保护

轨迹中存在较新的 completion review 先完成、较旧普通 review 后提交的顺序，例如 decision 25 处理 turn 122，随后 decision 26 又处理 turn 121；还存在 turn 213、228、280、297、355、394 的同 turn 双决策。它们获得连续的 `state_transaction_id`，并可分别修改 attention、repair episode、checkpoint 和未来 root ledger。

当前 freshness 逻辑主要防止过期干预消息被投递给任务 Agent，却没有证明旧观察不能覆盖较新状态。本次运行中 root updates 全部被 binder 拒绝，因此没有观察到 root ledger 被实际回退；所以这项应分级为**有直接轨迹证据的潜在并发故障**，不能夸大为本次失败的既成原因。但一旦状态写入恢复，它可能使“修好的长期记忆”被旧的异步 review 再次覆盖。

### 13.5 新问题五：completion 拒绝与高频 focused 调度被机械耦合

runtime 对任何 `continue_task` completion decision 都直接规范化为 `attention_mode = focused`，不再单独判断余留问题是否需要逐边界紧跟。根 completion 提议本身还会停止并重建 worker。本次 11 次 completion 提议全部被拒绝，因而每次根审计既重启执行生命周期，又强化 focused 调度。

这解释了为什么一次错误的根契约解释会被系统放大：错误 blocker 不仅阻止完成，还自动提高后续监察频率。这里缺少的是两个正交判断：

1. 根任务现在能否完成；
2. 剩余不确定性是否需要密集在线跟踪。

`continue_task` 并不逻辑蕴含 `focused`。这是调度作用链中的独立耦合问题，不只是旧 observation plan 没清理。

### 13.6 归档完整性仍有问题，但不是本次语义失败的主因

`research_events.jsonl` 有 6195 条可解析记录，同时有 25 个破损行，符合多写入者并发追加未做到整行原子化的既有异常。`authoritative_state.json` 用 Python 标准 JSON 解析器可正常读取；PowerShell `ConvertFrom-Json` 的失败不能作为该文件损坏证据。因此新增确认的是 JSONL 归档原子性问题，而不是 authoritative state 快照损坏。

该问题会妨碍论文审计和精确统计，但现有 decision 文件、state snapshot 与大多数事件足以支持本报告的控制链归因；没有证据表明这 25 行破损直接改变了在线监察决策。

### 13.7 没有被证据支持的新解释

再次回看后，下列说法仍不成立或证据不足：

- **“只是题太难”**：局部 URI 问题能按判别链收敛，精确干预也能立即恢复任务 Agent 的目标；难度不能解释状态写回全部失败。
- **“只要更频繁唤醒就能解决”**：93/96 次 decision 已处于 focused，高频并未修复写入反馈和错误 warrant。
- **“D 的 inquiry 本身导致所有循环”**：URI inquiry 在行为上正确结束；真正的问题是结束没有同步到 lifecycle、scheduler 和 root state。
- **“每个重复 decision 都造成了错误干预”**：部分消息被 freshness 机制抑制；目前只能确认状态提交存在风险，不能把每对重复 review 都算成已发生伤害。

### 13.8 更新后的因果图景

经过第二轮回看，最符合证据的图景不再只是“四层没有一致”，而是：

> 非正交的根任务表示制造绑定歧义与契约张力；监察者产生的自然语义修订被严格字符串 binder 全部拒绝，失败又不反馈给下一轮认知；空的根状态迫使 completion 反复临场重建，其中一次生成了错误硬约束；开放 repair episode 吸收后续异质问题，completion 拒绝又机械强化 focused；异步提交缺少单调性保护，使未来修复状态写入后仍存在被旧观察覆盖的风险。

因此原五项判断没有被推翻，但需要增加三个更上游的确定问题——**任务表示不正交、修订执行失败、执行失败无反馈**——以及两个控制层问题——**repair 作用域漂移、completion/attention 非正交耦合**。这说明下一步不能只调整监察者 prompt 或给四个状态字段做同步；必须把“模型形成判断 → 状态修订被可靠执行并确认 → 生命周期与调度消费同一已确认状态”视为一个端到端闭环来验证。

## 14. 对第 13 节问题清单的反证式复核与校正

本节再次逐项寻找反例，避免把同时出现的现象都写成独立根因。复核改变了两项证据等级，但没有改变最核心的状态闭环判断。

### 14.1 仍被直接证据确认的问题

1. **根任务状态没有积累：确认。** 最终 authoritative ledger 和 M1 workspace 均保持 69 项 UNKNOWN、`update_count=0`，而且中途抽样 decision 也没有状态进展。不存在“状态实际更新，只是最终快照丢失”的反例。
2. **自然语言修订全部没有落地：确认。** 98 个 binding 事件全部 `updates_bound=0`；代码只做规范化精确匹配或唯一字符串包含，与 prompt 承诺的 natural reference 不一致。
3. **写入失败未反馈给下一轮认知：确认。** binding ambiguity 虽保存在 decision/event 归档中，但在 monitor checkpoint 和 history archives 中均不可见；只有 full snapshot 身份错误进入同一次调用内的 protocol retry，sparse update binding failure 没有对应的下一轮 acknowledgement。
4. **错误根契约解释形成真实 blocker：确认。** unkeyed `MenuItem` 兼容性要求与公开任务的明确新增字段、官方 solution 和官方测试均不相容，却从 turn 297 持续进入后续 completion 阻断。
5. **局部 lifecycle 与调度没有随已完成观察一起释放：确认。** URI probe 在 turn 470 已通过，最终 checkpoint/inquiry 仍停在 turn 465；93/96 个 decision 为 focused，旧 plan 和开放 episode 仍存在。

此外，原子事务策略构成已确认的放大器：一批 sparse updates 中只要有一个引用失败，整批候选即置为 `None`，所以其中可能正确绑定的状态也不能部分积累。这不是新的模型错误，而是“binder 失败为何造成 69 项长期全空”的工程机制。

### 14.2 需要降级的判断一：ledger 重复不是本次 binding 失败的主因

非正交 ledger 是真实表示缺陷，但其在本次 binding 日志中的直接作用小于第 13 节最初表述。98 个事件共产生 335 条错误：

- 316 条为 `unmatched or duplicate`；
- 18 条为 sparse/full mixed representation；
- 只有 1 条明确是多匹配 `ambiguous`，即 `Entry.SetMinRowsVisible`。

因此本次 98 次全失败的主因应排序为：

> prompt 允许语义重述，但 binder 只接受字面匹配；批次原子回滚进一步放大失败。

ledger 重复主要增加 completion 审计负担和未来绑定歧义风险，并参与了宽泛 compatibility 条款的错误解释，但不能称为本次全部状态写入失败的主要原因。

### 14.3 需要降级的判断二：repair episode 膨胀已确认，但“作用域 bug”尚未单独成立

`repair-280-56` 的确达到 revision 21、21 个 challenge、约 57 KB，并依次覆盖 App compile、menu/tray、compatibility、Target 2 URI 和最终根 completion。然而它的原始 discrepancy 已写明“and, more broadly, several target clauses”，原始 exit condition 也要求随后进行 fresh root coverage review。也就是说，它从建立之初就是一次**根 completion repair**，不是严格的 App 局部 repair。

所以更严谨的结论是：

- episode 长期扩张和没有释放是事实；
- 它与错误 blocker、根状态写入失败共同造成高成本循环；
- 但现有证据不能单独证明“每换一个 target 就必须新建 episode”；根级 repair 是否允许跨 target 持续，是下一版需要明确的语义边界，而不是已经裁决的唯一正确实现。

真正已确认的缺陷是：episode 没有把局部 inquiry 的完成、根 obligation 的已确认变化和剩余 blocker 结构化地区分开，因此 revision 只会追加，无法证明何时应缩小、切换或释放。

### 14.4 completion → focused：机制强耦合确认，运行内独立贡献未确认

代码明确在 completion boundary 上执行：`continue_task -> focused`、`allow_complete -> patrol`，覆盖模型自主 attention 判断。因此机制耦合本身是确定事实。

但本次多数 completion proposal 发生时，监察者已经因为开放 repair episode 处于 focused。轨迹不能回答“去掉该强制映射后，本次会少多少次 review”。所以它应被表述为：

- 已确认的设计耦合；
- 对错误 blocker 的合理放大路径；
- 尚未通过同题消融证明的独立成本原因。

### 14.5 异步旧决策覆盖：风险确认，实际损害仍未发生

turn 122/121 的逆序提交和多个同 turn 双决策均存在，因此缺少 state commit 单调性保护是事实。与此同时，当前 freshness 机制确实抑制了部分过期消息，且本次 root writes 全部失败，没有找到“旧 decision 已把一个成功的新 ledger 状态覆盖掉”的实例。

所以继续维持原分级：这是修复 binder 前必须处理或至少加入回归证明的并发风险，不是本次不收敛的既成主因。

### 14.6 复核后的最终问题层级

**本次不收敛的确定主因：**

1. prompt/runtime 的 root-state 修订契约不一致；
2. 批次原子回滚使所有进展无法部分落地；
3. 写入失败没有反馈给监察者，导致重复失败；
4. 根状态长期为空，completion 被迫反复临场重建；
5. 临场重建产生了错误的 unkeyed compatibility blocker；
6. 已完成的局部 inquiry、开放 repair、focused attention 和根 completion 没有共同释放。

**已确认的放大机制，但独立贡献尚未消融：**

- 根 ledger 的重复和宽泛条款；
- 根级 repair episode 的无界 revision；
- `continue_task -> focused` 强耦合。

**修复前必须防范的潜在工程风险：**

- 异步旧观察晚提交覆盖新状态；
- 并发 JSONL 追加产生破损行。

这次反证复核后的关键变化是：不能笼统地说“七个问题都同等成立”。最先要修的不是 episode 分类或更多 prompt 原则，而是**让监察者已经形成的正确语义修订能够被执行、得到确认，并成为下一轮真正可消费的状态**。只有该闭环成立后，才有条件通过同题轨迹判断 repair scope 与 completion-attention 解耦各自还有多少独立收益。
