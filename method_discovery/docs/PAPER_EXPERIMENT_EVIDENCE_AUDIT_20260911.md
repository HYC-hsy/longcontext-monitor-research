# 长程监察论文的实验依据与复现审计

## 结论

现阶段最需要交付的不是一个继续增添机制的监察者，而是一套能够判断机制有没有价值的固定比较。现有 Clean Monitor 是研究平台和工程起点，不是已经得到论文级效果验收的方法。Final120 是异质研究池，不是统一分布、统一评分的正式排行榜。

建议采用三层证据：真实任务终局效果作为主证据；过程与失真分析解释收益；预算匹配与跨任务检验排除替代解释。优先复现 PMA 的可识别机制，并保留朴素持续监察者和工具反馈指导作为强简单对照。ACE 等记忆更新方法按实际失真证据进入，不一次性全部实现。

此报告只完成文献、已有源码和冻结元数据审计。未运行模型、容器或任务；未重新审完所有历史轨迹。以下题源排序是建议，不修改现有划分或批准新增实验。研究问题保持表示遗漏与不足证据闭合，A–D 仍是候选贡献目录。

## 文献实际怎样组织实验

以下数字属于原作者报告，不是本项目复现成绩。各条研究摘要独立列出，避免把不同论文的任务、反馈权限和预算拼成一个不存在的共同协议。

### PMA：最直接的外部对照

PMA 在 Terminal-Bench 2.0 和 τ²-Bench 比较无记忆与记忆干预；前者89题中报告85个有效配对，后者278题。它还比较完整记忆暴露、总是注入、无 bank 的指导和 Mem0。Table 2 中 full 的 micro 为61.2，always-inject 为61.5，故不能概括为选择性在所有统计口径都获胜。最值得借鉴的是“有收益”与“收益来自维护还是选择”分开验证。[论文 §4、Tables 1–2](https://arxiv.org/html/2607.08716v1)

本地源码固定在 `89e5c0d6aadfe531a1aee42fd290d48be89973dd`：`configs/memory_terminalbench.yaml` 实际配置50个任务回合、最近8步、每步触发；`src/memory_agent/memory/memory_agent.py` 的 `process` 分别调用 phase1 和 phase2。配置头部仍称 single-phase，但代码是两阶段，应以实际执行为准。所见 configs 只有两个 Terminal-Bench YAML；未据此认定 τ² 复现入口齐备。[官方仓库](https://github.com/yifannnwu/proactive-memory-agent)

**本项目判断**：PMA 优先作为外部机制对照，而非必须替换 Clean Monitor 的母体。同一模型下复现 memory update→选择提醒是有意义的；若改用 GA、异步调度和我们的预算，名称必须是 PMA-style adapted，而不是原论文结果复现。原论文数字不能与我们隔离环境中的结果直接相减。

### CRITIC：区分外部反馈和纯自我批评

CRITIC 用问答、数学程序合成、毒性任务检验工具反馈修正，比较无工具版本，并单独标记只修错题的 oracle 版本。问答设置最多3轮修正，包含迭代收益分析。可借鉴的是工具反馈消融、迭代收益与错误修正分析，不是把这些短任务换成我们的主 benchmark。[论文 §4](https://arxiv.org/html/2305.11738v2)

官方 program 实现把题目、代码、执行结果送给 critic，再生成和执行修订代码；`use_tool` 可切换反馈。gold 用于评价，所读函数的批评上下文不含 gold。这个结论仅适用于核读路径。[官方 program/critic.py](https://raw.githubusercontent.com/microsoft/ProphetNet/master/CRITIC/src/program/critic.py)

**本项目判断**：当前 tool-feedback 开关只替换一段调查指导，是受启发的简单基线，不是完成 CRITIC 复现。其已有联网正例因参考源码泄露不能接受为干净效果。若未来需要严格工具反馈消融，应保持可获取的公共信息边界一致，明确拿掉的是反馈消费而非把基线变成盲人。

### ACE：记忆更新应对应真实的信息丢失

ACE 在 AppWorld 的 normal/challenge 分别报告 TGC、SGC，并在 FiNER/Formula 报告准确率；比较 base、ICL、MIPROv2、GEPA、Dynamic Cheatsheet，分析消融与成本。其核心是局部增量更新而非反复整体重写。它区分离线上下文适配与跨样本在线适配，不能与本项目单题内纠偏混为一谈。[论文 §3–4](https://arxiv.org/html/2510.04618v2)

本地 revision `bcb7cea0504afad6f55fec4845dd4864c9f9eee7` 的 `playbook_utils.py` 位于仓库根目录，而不是旧审计中容易误读的 `ace/core/` 下。`apply_curator_operations` 将 UPDATE 等列为未实现，主要处理 ADD；另有 bulletpoint analyzer 的整理逻辑。因此不能仅凭论文示意宣称本地 curator 支持完整冲突修订。[官方仓库](https://github.com/ace-agent/ace)

**本项目判断**：如果当前失败是旧判断没有被撤销，单纯增加 ADD 不足以解释修复。只有观察到整体重写丢内容、局部依据随压缩消失等证据后，才优先判别增量维护；不为了学术外形引入 ID/schema 负担。

### ReasoningBank：学习成功与失败，而不是只保存轨迹

ReasoningBank 在 WebArena、Mind2Web、SWE-bench Verified 比较无记忆、轨迹型 Synapse、工作流型 AWM，并报告成功与步骤开销；MaTTS另做计算扩展比较。这提醒我们要用强简单记忆对照，而不是只击败无记忆。[论文 §4–5](https://arxiv.org/html/2509.25140v1)

**本项目判断**：其跨任务经验积累不能自动成为我们单任务状态维护的公平基线。若使用开发题构建经验库，需冻结后用于所有测试题；不能让某道测试题评价结果流入后续测试。若研究内核仍是单题内恢复，暂不复现整个自进化系统。

### MemCon：成本与跨框架证据值得借鉴，学习假设不能照搬

MemCon 报告 ALFWorld、PDDL、ScienceWorld 等任务及多个框架、模型上的效果和 token 开销。其控制器用任务结束成功/失败奖励更新并跨任务保存 Q 值。因此它虽不需要预训练，也不是本项目当前意义下的非学习、测试时不消费评分的同条件对照。[论文 §3–4、附录](https://arxiv.org/html/2607.13591v1)

**本项目判断**：借鉴跨框架和效果—成本设计，不因有数学模型就移植整个 UCB。其有限离散状态、条件平稳等假设不自动适用于随任务 Agent 改动而变化的监察过程。

### PM-Bench：评估遗漏，也评估多做、错做

PM-Bench 用延迟意图、取消/改期、主动查询等情形，报告 Set-F1、precision、更新命中、误触发和查询量。其自动 heartbeat 与多 Agent 并未因查询更多就统一更好。这是借鉴“收益与误干预同时计量”的直接依据。[论文 §3–4、Table 2](https://arxiv.org/html/2607.12385v1)

**本项目判断**：可作为诊断维度来源；不以其合成情景替代完整真实任务。若正式增加该基准，需承认它主要检验适时执行意图，不足以单独证明软件任务中完成证据的充分性。

### MemoryArena：将局部进展和完整任务成功分开

MemoryArena 比较长上下文、外部记忆和 RAG，在购物、旅行、搜索及形式推理中使用相互依赖的多会话子任务，报告成功率、进展分数、依赖深度与延迟。其不同环境成功定义不完全相同，不宜把一个平均数当成通用成功率。[论文 §3–4](https://arxiv.org/html/2602.16313v1)

**本项目判断**：适合检验信息是否真正参与后续行动；但跨会话协议与我们当前同一持续任务会话有差异。当前池内10题没有历史完成评价可用标志，不能视为立即可用的便宜泛化证据。

### 补充近邻，不扩大第一轮复现范围

Reflexion 的所读 HotpotQA 路径把答案正确性用于反思与 scratchpad，不能直接进入无 checker 主实验。[源码](https://raw.githubusercontent.com/noahshinn/reflexion/main/hotpotqa_runs/agents.py)

近期《Making Prospective Memory SLM-Shaped》也研究 PM-Bench 上的类型化意图存储；本轮只核实摘要，未审实验与代码，不据其自报结果作基线选择。它进一步提示“增加固定状态字段”不能直接作为创新结论。[论文摘要](https://arxiv.org/abs/2609.01272)

## 现有120题的真实资产情况

来源：`long_context_bench/docs/BENCHMARK_V1_FINAL_120_FREEZE_REPORT.md`；`method_discovery/r0_real_tasks/manifest.json`、`tasks.jsonl`。下表是冻结记录统计，不是本轮实时可运行认证。

|来源|总数|method_dev|stage_validation|final_holdout|历史完成评价可用标志为true|
|---|---:|---:|---:|---:|---:|
|RoadmapBench|31|17|7|7|31|
|LHTB|30|16|7|7|30|
|ResearchClaw|12|6|3|3|0|
|MemGym-DR|10|5|3|2|0|
|MemoryArena|10|5|3|2|0|
|Claw-SWE|9|4|2|3|9|
|AMA|7|3|2|2|0|
|TB2|5|2|1|2|5|
|WildClaw|3|1|1|1|0|
|ClawBench|3|1|1|1|0|
|合计|120|60|30|30|75|

45题需评价适配核验；false 不等于题源没有官方评分，也不等于任务失败。长度标签为 strong_observed 40、medium_observed 39、short_observed 41，是历史实现轨迹描述，不是冻结任务的固有长程标签。

旧普查62题证据不足，28题 premature_completion 全来自 RoadmapBench，8题表示遗漏中7题来自受控 MemGym notes、1题来自 ClawBench。不能将这些比例外推总体，也不能把“结束时原生测试未全过”单独作为偏移证据。见 `some_research/11_final120_empirical_pivot.md` 与 `exploration/full_survey/FINAL120_FULL_SURVEY_REPORT.md`。

`final_holdout` 是冻结后的前瞻保留，不是从未被历史普查接触过。重复开发曝光、参考解接触、同仓库版本亲缘还需做 metadata-only 账本；不能为了整理账本打开留出任务答案或用其选择方法。现有冻结划分保持不变。

## 推荐的题源角色，而不是同时新增所有题源

### 主问题场：RoadmapBench

原基准包含跨版本升级的多要求任务，适合同时观察完整解决与目标级别进展；官方也给出防访问代码托管平台的网络隔离提示。[论文](https://arxiv.org/html/2605.15846v1)、[官方 README](https://raw.githubusercontent.com/UniPat-AI/RoadmapBench/main/README.md)

建议保留其为首要方法开发场，利用已接入环境，但从 Fyne 单题转成预先固定的多仓库 method_dev 小面板。完整解决率为主，现有 phase/reward 为辅助；先核实 phase 权重，不把7/7与reward转换视为恒等关系。

风险是参考源码污染、仓库版本重叠、测试与题意错配、无网缺依赖。现有 `no-network-unix-inference-v1` 保持。旧联网得分不作同条件对照；预装依赖、可见源码和资源限制须对所有方法一致。不开放网络补下载后还标成离线实验。

### 公共对照场：Terminal-Bench

Terminal-Bench 官方2.1修复2.0中28/89题，涉及依赖漂移、资源和题意/测试不一致。[官方2.1说明](https://www.tbench.ai/news/terminal-bench-2-1)

建议新正式证据优先评估2.1可用性；忠实复核 PMA 原设置则固定2.0。两者不可混分，也不宜把一个版本的微小优势解释成方法优势。当前池只有5道TB2，不能称已具备全基准实验。扩题、换版本与无网筛选均须另行确认。需要真实网络功能的任务不得靠删要求“适配”无网。

### 非代码场：只选一个

首选候选是固定版本的 τ² 文本域：与PMA连接直接，能观察政策、用户条件和环境修改。但其现仓库已展示τ³及任务修订，必须固定历史/选定版本；用户模拟器、私有目标和终局评分不可暴露给监察者。[官方仓库](https://github.com/sierra-research/tau2-bench)

备选是 AppWorld：可执行应用交互、原生划分、明确完成动作，适合检查目标与副作用。官方文档将 ground_truth 单独列出并明确不应给测试 Agent；我们的通用 code_run 不能通过本地文件越过此边界。[官方仓库](https://github.com/StonyBrookNLP/appworld)

两者都不是已完成接入。选哪个取决于静态隔离/适配审计，不取决于先跑哪个得分好。若两者都需要明显扩张工程，先收束“长程软件/终端任务监察”的证据，并向用户确认论文声明是否缩窄；不得私自用QA成绩替代Agent泛化。

MemoryArena 可作后续记忆压力验证；PM-Bench可作机制诊断。LHTB 的时限内持续执行契约与“减少早停”定义可能不同，先核对，不能从30个历史可评分标志直接升为主实验。

## 实验要借鉴的是排除解释，不是榜单数字

|可能的解释|必要比较|不能替代该比较的证据|
|只是多了一个强模型|同模型/工具的朴素持续监察者|只与纯GA比较|
|只是多算了一些|总预算匹配、多个预算档位|只统计任务Agent token|
|只是记住更多内容|强滚动summary/always-visible状态；若声称检索优势再加RAG|“我们有图/版本”|
|只是完成前检查有效|仅终局审议 vs 持续监察，同总上限|挑几次意图纠偏故事|
|只是某道题调出来|固定面板、留出任务、仓库亲缘控制|Fyne换随机种子多跑几次|
|状态机制根本没被用|真实输入/更新/消费记录及机制关闭对照|工具存在或文件有字段|
|新方法损害原来会做的题|同题win/loss/tie和误干预分析|只列救回的任务|

## 优势待证的过程维度

1. **完整恢复而非口头接受**：纠偏送达后，公开计划、动作与最终结果是否相符；Agent说“明白了”不算修好。
2. **局部修好后的持续保持**：后续修改是否重新破坏已支持要求，区分同一问题复发与新的独立要求。
3. **意见可撤销**：监察依据被新公开证据推翻后，是否改正自身建议，而不是反复要求错误动作。
4. **意图级及时性**：仅对公开表达的计划计量，分别记录证据可见、首次读取、决定、送达、任务响应时间；不推断不可见思维。
5. **调查代价与误干预**：同样获得结果需要多少模型/工具/时间；对没有足够证据的事件允许unknown。

这些是本项目希望发挥的优势，不是已证明近邻论文完全没有研究的空白。不能仅以多加指标宣布创新。

## 证据质量与局限

本轮复核了PMA、ACE本地固定源码中的关键入口，CRITIC/Reflexion官方选定源文件，以及相关论文实验章节和官方基准说明。没有完整运行复现，CRITIC远端main尚未锁commit；其他方法的全仓数据、许可、执行闭环仍须在选定后核验。

没有遍历研究池全部隐藏评价文件、没有将留出题重新分组、没有模型API调用。没有声称检查完所有最新文献或保证最优基准组合。PMA论文Tables 1/2的完整方法数字存在口径/运行差异，故本文不从中拼出统一准确增益；版本信息以所列固定文档为准。

## 来源索引

1. Wu et al., Remember When It Matters, 2026，§3–4：[论文](https://arxiv.org/html/2607.08716v1)，[代码](https://github.com/yifannnwu/proactive-memory-agent)。
2. Gou et al., CRITIC, ICLR 2024，§4：[论文](https://arxiv.org/html/2305.11738v2)，[代码](https://github.com/microsoft/ProphetNet/tree/master/CRITIC)。
3. Zhang et al., Agentic Context Engineering，§3–4：[论文v2](https://arxiv.org/html/2510.04618v2)，[代码](https://github.com/ace-agent/ace)。
4. Ouyang et al., ReasoningBank，§4–5：[论文v1](https://arxiv.org/html/2509.25140v1)。
5. Jiang et al., MemCon，§3–4：[论文](https://arxiv.org/html/2607.13591v1)。
6. Liu and Gabriel, PM-Bench，§3–4：[论文](https://arxiv.org/html/2607.12385v1)。
7. He et al., MemoryArena，§3–4：[论文](https://arxiv.org/html/2602.16313v1)，[代码](https://github.com/ZexueHe/MemoryArena)。
8. RoadmapBench：[论文](https://arxiv.org/html/2605.15846v1)，[README](https://raw.githubusercontent.com/UniPat-AI/RoadmapBench/main/README.md)。
9. Terminal-Bench Team：[2.1修订](https://www.tbench.ai/news/terminal-bench-2-1)。
10. Sierra：[τ基准仓库](https://github.com/sierra-research/tau2-bench)。
11. AppWorld：[官方仓库与信息边界](https://github.com/StonyBrookNLP/appworld)。其ACL2024 Best Resource Paper定位是资源论文，不作为本方法达到Best Paper的保证。
12. 本地冻结记录：`long_context_bench/docs/BENCHMARK_V1_FINAL_120_FREEZE_REPORT.md`、`method_discovery/r0_real_tasks/{manifest.json,tasks.jsonl,protocol.json}`。
13. 本地研究证据：`some_research/11_final120_empirical_pivot.md`、`some_research/exploration/pma_deep_audit_and_reproduction.md`、`method_discovery/docs/PHASE1_EXISTING_MECHANISM_FIT_AUDIT_20260911.md`、`PHASE1_TOOL_FEEDBACK_ADAPTATION_DESIGN_20260911.md`、`PHASE1_OFFLINE_ISOLATION_IMPLEMENTATION_20260911.md`。
