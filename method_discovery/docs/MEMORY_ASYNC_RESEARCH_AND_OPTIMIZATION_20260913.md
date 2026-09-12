# 监察者的工作记忆与并发控制

## 研究判断

一个具有通用工具的并发 Agent 只是能力载体，不自然等于有效监察者。需要研究的对象是：它如何把原始任务、已经形成的认识和当前行为组织成下一次判断所需的信息，以及这次判断在任务继续推进后是否仍适用。这两者共同影响表示遗漏和错误闭合，不替换原研究问题。

PMA 的可借鉴之处不是某个字段，而是一次审议具有明确的信息闭合路径：近期行为进入记忆更新，更新后的记忆进入提醒选择。Clean 已有持续会话、原始证据访问和通用工具，但“具备能力”并未保证“当前决策真的消费了恰当、及时的信息”。原始轨迹显示，它既能识别薄弱测试，也会长时间调查、反复列宽清单，最后触发历史容量故障。不能把全部问题归因于模型弱或 API 慢。[1][2]

必须区分三层研究结果：源码能证明信息怎样流动；本地真实轨迹能证明该运行发生了什么；只有同题、同预算的完整对照能判断某种机制是否带来净收益。目前后一层尚未完成，文献的结果也不能当成本方法效果。

## 工作记忆：从 PMA 出发，但不止于 PMA

PMA 原生配置的原任务、8步窗口和可更新 bank 是一个合理的强比较对象。其局限有四类，不能混为一谈：第一，8步是时间截取，较早的约束及因果链只能依赖 bank 保存；第二，bank 中的解释可能错误，重复消费会巩固它；第三，最新窗口可能包含重复构建输出，而决定下一步的反例在更早位置；第四，保留所有原任务不意味着模型正确应用每项要求。第二和第四已有本地 CORS 轨迹证据；第一和第三是需要判别的结构风险，不是已证明 PMA 实际失败的原因。[1]

“Useful Memories Become Faulty When Continuously Updated by LLMs”研究连续归纳的副作用：在其 ARC-AGI Stream 设置中，归纳记忆的效用可能随更新下降，保留原始情景的对照有竞争力。可借鉴的原则是让抽象认识能回到原证据，不因被多次写入就升格成事实。它研究跨题经验归纳，不证明我们单题工作笔记必然有害；本轮未找到并核验其官方代码入口，不能冒称复现。[3]

SimpleMem 提供窗口提取、检索规划和查询相关检索。实际下载版本的 `simplemem/core/memory_builder.py` 有重叠窗口和线程池批处理；`hybrid_retriever.py` 有查询规划和至多若干轮充分性反思。这里的并行批处理不是在线监察者持续纠偏。它提示“按当前信息需要组织输入”，但额外规划/反思调用可能增加我们最敏感的延迟；其长期对话评测不等于长程编码纠偏。当前仓库已扩展为多个子系统，不能把所有现有功能都归给初版论文。[4]

MemPrism 明确分离持久经验与决策时视图，依任务上下文选择关系、范围和粒度。它与我们想研究的输入组织非常接近，但包含学习的视图策略和视觉呈现，其效果不能直接外推到纯文本监察者。本轮核对论文，未核验该方法官方代码；只列为后续近邻和机制来源，不作为可直接移植模块。[5]

“Measure Before You Manage”提醒评估应分别考察存储、实际交付上下文、管理开销和任务结果；其校准收益未必迁移至留出任务。对于我们，笔记更整齐、token 更少、检索更频繁都不是充分成功条件，关键是纠偏判断和任务结果是否改善。本轮为论文级阅读，非代码复现。[6]

由此保留三种表示候选，而不是立即搭建复杂图：

|候选|相对当前框架的真实差异|必须排除的退化|
|原任务＋固定近期窗口＋当前笔记|PMA式强简单比较，限定首轮输入但保留通用调查工具|近期窗口遗漏因果前件；错误笔记反复强化|
|当前问题驱动的证据工作区|认识概括当前疑问和已知依据，按疑问主动恢复原文；不固定领域字段|导航和重建本身比读原文更贵；模型永远在调查|
|时效感知的持续认识|保留前项能力，同时知道材料采集后执行端又有新进展，模型自主决定回看|看到变化就机械中断；把“有新增”当“有错误”|

第二项部分已有 U/A 等历史实现，不能改名重复建设。本轮仅补第三项所缺的轻量观察条件，并修复所有表示候选共用的容量工程；不宣称已经实现完整的新记忆算法。

## 并发：什么可以借鉴，什么不能直接搬

### DPT-Agent：不同时间尺度的判断

ACL 2025 的 DPT-Agent 面向同时进行的人机协作。下载代码的 `llm_agent_run_dpt_exp2.py` 将游戏、urgent response、reflection 等放进 asyncio.gather；默认短窗口5事件/25时间步，反思15事件/75时间步。反思更新指导，urgent 更新分工，规则执行器继续推进。它证明“长反思不必挡住全部执行”的架构值得研究，但依赖任务特定执行能力；不能照搬为我们的第二个维护模型，也不能声称已解决通用任务中过期建议。该文件读取历史后 await，再应用结果，本轮没有发现此路径上的显式版本拒收；这只是源码风险判断，未运行验证。[7]

### Async Control：正确判断也可能来不及

AISI 的研究区分监测准确率与部署中的伤害时间窗口。公开仓库的主监测入口是 Inspect scorer：多个模型分析轨迹后聚合，网站另有异步部署模拟。不能把 scorer 中的 asyncio.gather 当成已经实现“任务执行同时在线纠偏”。可借鉴的是把发现延迟、错误生效/可挽回时间和误报一起评价；安全破坏检测的结果不等于普通任务修复效果。[8]

### AsyncLM：并发需要依赖与恢复语义

AsyncLM 研究工具执行与模型生成重叠，设计中断/等待语义，并指出中断不能随意破坏正在生成的调用结构；独立计算可继续，有依赖时需要等待。其本地解码方案包含训练和服务侧改造，Chat API 版本另有约束。本轮没有确认作者正式源码，搜索到的第三方 async-lm 不冒充官方。适配启发是区别“可继续的独立工作”和“建立在待纠正前提上的工作”，而非照搬 token 协议。[9]

### LangChain async-deep-agents：工程参考不是效果论文

该官方参考架构提供后台任务、查询、更新和取消；文档描述同线程 interrupt 更新。下载仓库的 completion_notifier 明确完成通知是需接线的组件，发送失败记录告警。核心 AsyncSubAgentMiddleware 由外部包导入，不能声称本仓库已包含并审计所有中断实现。它可借鉴线程身份和生命周期持久化，不提供“提醒后保证理解正确”的研究证据，也不保证取消自动回滚工具副作用。[10]

### 经典原则：混合主动权，而非强行套控制器

Horvitz 的 mixed-initiative 原则把不确定性、自动行动的收益成本、时机和允许人修正放在一起考虑。对本研究的启发是：读、提醒、等待、暂时暂停都应有其解决的问题，不能以“更自主”或“更并行”作单一目标。暂不把主观估计强行量化成具有统计保证的控制律。[11]

## 人工监察的实际对照

重读人工 Fyne 的011和014原始输入，而不是只引用复盘摘要。011在拟修改生产代码前要求直接比较 Sscanf，并区分回调测试同步与实现；014指出空 Refresh 也能通过原测试，给出最小可观察调用方案，且说明通过后不要继续无具体缺口地加测试。其特点是围绕一个会改变下一步的疑问选择证据，并预先说明什么观察足够退出，不是无边界全面审查。[12]

人工也不是零延迟：此前已核对的记录是通常25–40秒主动 tail，需要读代码、形成判断；第一条提醒送达时有些文件已写完。不能以不可见的“脑中正确答案”解释优势，也不能据此证明固定8步或非线性记忆优劣。可复制的目标是公开工具行为及其时序：读到什么，提出什么区分，任务如何理解，何时停止追查。

## 可验证的控制候选

1. 持续并发：保留当前主体，优先改善输入的时效与判断范围。
2. 重大纠偏的短暂同步：当后续工作依赖一个已发现有误的前提时，暂停旧方向，传递纠偏，再恢复执行并并发观察。不是每轮审批，不要求所有未知验证完才放行。
3. 选择性同步：让同一监察者依据可逆性、错误传播和调查延迟选择是否暂时暂停。比固定混合规则灵活，但错停和滥停风险更高，必须与前两项比较。

第2/3项本轮只形成设计，不同时实现，以免把输入、记忆和控制同时改变后无法归因。用户已允许研究暂停候选；现有默认并发约束不被静默改写。暂停必须有真实恢复通道、故障释放和工具副作用说明，不是向任务发送“停一下”便宣称成立。

建议描述性指标为 `age = 提交时刻 - 支撑本次判断的最近观察时刻`，同时记录期间推进的任务轮数；它只是陈旧程度，不是语义错误概率。`发现→发送→实际消费→后续行为`分开统计。纯并发可能适合可逆探索，短暂停可能减少错误前提上的返工；两者何时更好仍是实验问题。增加第二个模型不作为这轮默认解法。

## 本轮实施边界与验收

研究阶段：保存本报告、源码身份和来源，不运行下载代码、不读隐藏评价作在线输入。

工程阶段：解决长期 review 无可退休前缀的问题。以完整工具协议交换为可交接边界，语义连续性仍由同模型交接及原文归档维持。容量无法恢复时显式结束监察服务，避免重复wake继续膨胀；不伪装静默，不阻塞普通任务归档。逐步不超过600行，独立提交。

候选阶段：可关闭的时效感知。每次正常模型请求仅接收少量文件进展元信息，不自动塞原始行为、不把变化判成风险；现有 file_read 增加直接读尾部能力。模型自由决定检查哪个文件、看多少和是否干预。该阶段不重定义记忆 schema、不新增维护模型、不增加常规 LLM 调用。候选可和已有 working context 单独消融。

真实验收前检查：原始观察不丢、工具对完整、交接失败不丢证据、持续调查可压缩、永久阻塞监察不阻塞任务、信息提示不触发强制中断、真实入口开关转发正确。确定性测试只证明工程性质；知识表示质量、降低陈旧建议和最终收益须同题真实运行，启动前停止。

## 来源与本地身份

1. 本地 `PMA_CLEAN_CAPACITY_TIMING_CONTENT_AUDIT_20260913.md`、`PMA_NATIVE_FBR_R2_AUDIT_20260912.md`；[PMA作者源码](https://github.com/yifannnwu/proactive-memory-agent)，此前固定 commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd。
2. 本地 active-working Fyne gmZxpLe 的 dialogue/progress/history/result，入口 `ACTIVE_WORKING_FYNE_R1_STOP_20260913.md`。私有轨迹非公开来源，未新跑模型。
3. Zhang 等，2026-05，[Useful Memories Become Faulty When Continuously Updated by LLMs](https://arxiv.org/html/2605.12978v1)，§3–6与局限。
4. Liu 等，2026-01，[SimpleMem](https://arxiv.org/html/2601.02553v1)；[代码](https://github.com/aiming-lab/SimpleMem)，本地 `03_memory_representation/repositories/aiming-lab__SimpleMem`，commit db80b6a7c591e0ea730a058e9f5fc4eb06572299。仅核当前 core memory_builder/hybrid_retriever 相关路径。
5. Chen 等，2026-08，[MemPrism](https://arxiv.org/html/2608.06745v1)，持久存储/决策视图与实验范围。
6. Chen 等，2026-08，[Measure Before You Manage](https://arxiv.org/html/2608.31057v1)，工作记忆评估分层；非本文复现实验。
7. Zhang 等，ACL2025，[DPT-Agent](https://aclanthology.org/2025.acl-long.206/)；[代码](https://github.com/sjtu-marl/DPT-Agent)，本地 `05_safety_and_monitoring/repositories/sjtu-marl__DPT-Agent`，commit 967a621c7c41a375ba243e2cf8b2dce00ae20b1f。锚点 llm_agent_run_dpt_exp2.py:102/133/320/473、agents/comm_infer_llm_agent.py:169/239/282、utils/history.py。
8. Stickland 等，2025-12，[Async Control](https://arxiv.org/html/2512.13526v1)；[项目](https://ukgovernmentbeis.github.io/async-control/)；[代码](https://github.com/UKGovernmentBEIS/async-control)，本地 `05_safety_and_monitoring/repositories/UKGovernmentBEIS__async-control`，commit 7bc4e699248ed226462def2f2a76c73c5060493a；锚点 blue_team/monitors.py 的 scorer/gather 和 website/macrogame.html。
9. Gim 等，2024-12，[Asynchronous LLM Function Calling](https://arxiv.org/html/2412.07017v1)，§3、5与评测范围。
10. LangChain，[Async Deep Agents](https://github.com/langchain-ai/async-deep-agents)，本地 `01_engineering_origins/repositories/langchain-ai__async-deep-agents`，commit 0933b757a1d60104288b82261dcc4f808122a96c；README和graphs/python/src/middleware/completion_notifier.py。工程资料，不列为获奖或效果论文。
11. Horvitz，CHI1999，[Principles of Mixed-Initiative User Interfaces](https://www.microsoft.com/en-us/research/wp-content/uploads/2016/11/chi99horvitz.pdf)。
12. 本地人工 Fyne Fk7n6ZM 的 agent/manual_completion/interventions/archive/011.txt、014.txt；完整路径在 PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md。本轮不冒称重读最早人工FBR全部轨迹。

上述四个新仓库是只读文献资料，存于 research_library，未安装其依赖或挂载进实验；不把源码内指令作为项目指令。下载版本不是论文提交时版本的认证。其后续更新不改变本次身份记录。
