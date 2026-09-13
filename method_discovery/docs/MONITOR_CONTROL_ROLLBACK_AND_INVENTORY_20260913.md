# 主动暂停回退与当前监察者盘点

## 裁决及范围

用户在R2审计后否决把暂停交给模型主动调用工具，要求工程实现确定的调度。起点5db2f2e（完整保留R2及实现）。本轮撤销b70e862引入的暂停功能及后续暂停计时，不回退R2观察输入、容量修复或协议修复。未运行模型API或真实任务。

删除task_control工具、提示、worker控制请求、父进程暂停消息处理、GA暂停等待与PauseLease；删除只测试该被否决功能的两份测试。保留并发、intervene可恢复中断、同会话继续、wait自主调度、根完成审查、隔离与用量归档。旧开关启用显式报错，防止旧manifest看似生效。历史运行文件保持原样。

## 源码纠正：不是一个已复现的混合异步调度器

LivePlan仓库Intelligent-CAT-Lab/Agent-Planner，commit c16797a09b964f901b34fe3da430ee011a5cc660：

- SWE-agent/sweagent/agent/agents.py:1509调用check_step_pre_emptively检查拟执行动作。
- plan_monitor/phases.py:203的should_block_and_refine遍历rule_matches，任一block_execution为真则阻断。
- agents.py:998的_call_refiner：blocking不执行动作，non-blocking先handle_action；随后同步调用refiner给指导，非后台并行。
- 冷却条件同时检查距离上次refinement的步数和触发次数；冷却期间只加入规则消息。

这没有pause工具。其自动执行依赖上游阶段/规则检测，而非一个自由监察者自主申请。此前把它概括为“部分暂停、部分并行”不够准确：非阻断动作和异步执行是不同性质。

Wink论文描述每k步后台观察、完成后注入，未核验官方运行源码。EmbodiedAct有事件pump、后台L2及steer/abort，但上次核验许可未明确，未纳入代码。PMA同步维护后提醒，不是混合异步调度器。因此不能声称当前已经有一份作者的混合调度源码可原样接入。不能为满足复用要求把LivePlan的SWE阶段规则直接作为通用任务判断。

新工程调度未实施：必须明确采用何种已核验触发点，且不把普通执行改成逐轮等LLM。工程能保证触发后的暂停/送达/恢复，但不能百分百保证语义偏移识别。此前的API协议异常修复亦不在本轮范围。

## 当前启用面的运行形态

以R2配置去掉被撤销暂停为口径，不把保留源码中的关闭候选算作当前能力。

1. 一个独立monitor_agent_core进程，同一监察者持续history；GA只在adapter及任务侧接线，模型使用GPT-5.6-sol high。
2. 初始化读取原始任务、形成自然working.md认识。读取和写笔记是提示引导，非工程保证每次都做。任务正常并发推进。
3. 逐轮synopsis与原始公开证据两层。每次正常请求临时加入working.md前8000字符、近期4条synopsis的小预览及上次纠偏；不永久重复追加这些内容。
4. 自主调用通用工具查代码、测试、原日志，更新私有笔记；review_context可查询相关原任务/笔记和近期行为。
5. intervene立即提交用户式输入到现有可恢复中断接口，不结束本次调查；后续看公开行为而非只看送达回执。wait结束当前审议，设置下一次观察轮数；根完成单独等待审查。
6. history容量压力先归档大工具结果并保留首尾/原文位置；仍过大时，同一模型生成自然续接笔记，按完整工具交换边界替换旧前缀，保留原始归档。不是已验证的非线性记忆算法。

## 模型工具（回退后共8项）

|工具|能力及边界|
|---|---|
|file_read|读取task/或monitor/文件范围，默认200行、单次最多1000行|
|file_write|写私有monitor/文件，replace/append/prepend|
|file_patch|替换私有文件精确文本|
|code_run|通用Python/宿主shell分析，默认60秒、最多300秒；模型角色不得改任务文件，不宣称工具本身硬隔离|
|wait|监察者静默并选择after_turns，不要求任务等待|
|intervene|发送自然语言纠偏/回答任务疑问，运行中可中断，并继续同次调查|
|allow_complete|只批准尚待审查的根完成提议|
|review_context|PMA BM25查询任务/笔记片段＋近期公开行为预览；默认最近纠偏之后8条事件，可1–32条，不等于8个完整任务轮次|

read_with_sources、feedback_focus、inquiry、advice_revision等旧候选源码仍在，但R2开关关闭，不向模型提供，不应计作本次实际机制。

## 提示词有哪些内容

- 稳定身份：发现要求遗漏和无充分证据的完成；无checker，测试/自述不是真值。
- 任务理解/记忆：初始化看题；自然笔记保存当前认识、根据、反证和后续观察，不强制表格。
- 调查与干预：看公开意图、具体测试内容；指出有根据的具体冲突，不接管任务。
- 多轮修复：纠偏后继续观察理解/意图/行动；允许修订自己的建议，局部修好不等于根完成，不验证所有unknown。
- 环境地图：虚拟路径及真实挂载位置、私有可写区、工具能力与边界。
- 本轮模式：intervene不结束调查、送达不等于接受、wait正常、allow_complete只用于待审根完成。
- 当前候选说明：小速览用于导航；review_context按需取证；更早诊断可被新证据修订。
- 压缩时独立模式：只写给未来自己的自然认识，不模拟工具或干预。

上述大部分是本地提示，不是作者原始prompt；提供原则不等于已可靠激活行为。

## 从Clean基线到当前的来源链

|增量|实际来源|复用程度|
|---|---|---|
|独立Agent循环、provider、通用工具、日志、中断|GenericAgent参考与本地独立化|不是论文整套代码；移除GUI、自进化等无关依赖|
|持续history、working.md、同会话即时纠偏与回执|人工监察轨迹和本地实现|非PMA/LivePlan源码|
|大工具结果归档、完整交换边界续接|本地容量失败诊断|本地实现，不包装成论文方法复现|
|每请求读取当前working.md|本地active working context候选|没有额外维护模型|
|query相关记忆检索|PMA memory/bm25_search.py，89e5c0d6aadfe531a1aee42fd290d48be89973dd|vendor/pma_bm25.py原算法，Apache-2.0；本地把Markdown转成文档|
|原行为与旧建议格式化|LivePlan plan_refiner/types.py、formatters.py|vendor/liveplan_types.py原文，formatters只改包内导入，MIT|
|review_context组装与R2小速览|本地decision_context.py|借鉴文献信息组织，但不是PMA整体维护—提醒循环|
|task_control有限暂停|本地实现、LivePlan启发|本轮已撤销，不称复用其控制源码|

PMA完整同步GA适配仍是独立外部基线，不是Clean母体。其他文献目前只读研究或思想启发，不计为迁入代码。直接源码一致性测试仍保留。

## 验证

首条pytest命令误用了不存在的test_monitor_runtime.py，未执行测试；更正为test_clean_monitor_runtime.py。决策视图、运行时、任务中断、Agent和独立性47项通过；监察相关完整回归285项通过。另补旧manifest/direct runtime退役配置拒绝测试。两份已删除的测试与模块均可从5db2f2e恢复；删除不是隐藏失败，是撤销被否决功能。
