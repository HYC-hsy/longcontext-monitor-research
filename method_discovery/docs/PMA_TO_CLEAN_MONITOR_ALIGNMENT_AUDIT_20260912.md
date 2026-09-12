# PMA → Clean Monitor：行为与信息流对齐审计

## 0. 范围、裁决与权限

用户批准只读审计。本文不修改机制、不调用模型、不启动实验。Clean Monitor 是研究主体；PMA 是外部基线及机制来源，不将研究转为 PMA 开发。以下实施顺序是待确认建议，不替换五阶段主路线、无 checker、单一监察者、两层观察、并发或真实启动门禁。

本次重新读取当前源码、原生 PMA R2 的关键 memory steps、Clean 公共基线与 B 的原始 dialogue、人工 Fyne 011/014/015 原文；不是全量重读所有历史。自动/人工对照以同题 Fyne 片段为主，PMA 的 FBR 只作跨题行为启发，不作效果排行。本次没有重读最早人工 FBR，不将 Fyne 经验冒称 FBR 复盘。

**结论：最值得借鉴的是“把当前认识更新后实际用于下一次决定”的短路径；不是重新补一套通用工具，也不是简单增加被动上下文。** 对应缺口有实现和行为证据，但其对最终效果的因果贡献尚未确定。两边共同未解的问题是：已经读到要求与实现，仍作出错误解释或不足证据下的完成判断。

## 1. 对照身份，避免用历史实现冒充现版本

- 当前源码：`GenericAgent-main/monitor_agent_core/agent.py`、`runtime.py`、`provider.py`。源码有 U/W/R/B/A 可选候选，不能因文件存在就认定默认启用或已有效。
- 公共 Clean 真实参照：`phase1-tool-feedback-base-20260911-r1` / `kAxvamr`，UWRBA=0、TOOL_FEEDBACK=0；Opus4.8 任务、GPT-5.6-sol high 监察，202轮、6/7阶段、加权0.9091。已有工程后续修复，不把该运行视为当前逐字节源码的重新验收。
- B 辅助诊断：`phase1-feedback-b-20260911-r4` / `KkQAqgp`，未完整评价，不能按分数选择它。
- PMA R2：Sonnet4.5 + Opus4.6，48轮、6/7阶段、加权0.875，FBR 原生 Terminus2。与上面题目、模型、预算、harness 都不同，不计算相对提升。
- 工具反馈 treatment R2 的7/7涉及目标版本参考源码，不作干净效果证据；本次不借它证明对齐成功。

## 2. 实现对照与取舍

|部位|PMA 实现及实际现象|Clean 实现及证据|裁决|
|---|---|---|---|
|任务锚点|每次 context 提供原任务，初次保存精确要求|初始化读原题；可主动重读，base D256 确实重读|学习原要求稳定可用；无证据必须每轮全文重复|
|近期观察|滑窗8步，含公开 analysis、plan、最多5条命令说明、任务侧已限长终端输出|runtime synopsis 取 summary 或 response 前600字符，含工具名/有无结果但非结果正文；主动读原事件/工作区|PMA 的第一眼材料更完整；不是原始信息无截断。值得作为独立输入候选，不凭此认定是主因|
|当前认识|bank中 status/knowledge/procedural，phase1更新后phase2直接使用|同History，自然working.md，压缩交接；日常更新自主|维护和消费连接是最明确可借鉴点；不能宣称Clean无记忆|
|修复经验|Step17记目录和失败方法，后续提醒复用|同History能连续跟Bytes；私有文件具备读写能力|可学短而具体的经验；不可把未验证解释固化成成功经验|
|提醒|合成相关内容，一次消费，不把bank全发任务；11/11送达|intervene自然语言立即提交，可继续同review观察，已有回执|双方已有具体提醒，不能重新包装为新贡献；保留我们的持续跟进|
|调度|每个处理步两次memory调用，同步执行|并发、主动wait、原始证据查询，根完成单独处理|不复制同步每步审批，不用减弱主体能力换形式上的对齐|
|工具|PMA记忆更新工具；主要分析给定轨迹|file_read/write/patch/code_run已真实大量使用|无证据需新增通用工具；优先让已有能力发挥|
|评价/归档|R2已保存完整终局、提醒输入与操作记录|已有dialogue/history/回执/用量|吸收证据可追溯性，不复制两套收集；完整效果仍须同条件比较|

PMA源码锚点：`src/memory_agent/memory_enabled_agent.py:_get_memory_agent_context/_format_step_entry/_trigger_memory_agent/_get_memory_system_prompt`；`src/memory_agent/memory/memory_agent.py:_format_memory_bank/_build_phase2_prompt/process`。根目录为 `some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent/`。

## 3. 重新核对的行为链

### 3.1 已有能力不可削掉：自动监察并不缺连续纠偏

B D248指出Bytes缺口；D284发现任务用文档说明替代实现；D324发现接口已加但实际分支没接，进一步纠正。主要通过通用工具完成，feedback_focus仅begin1/read0/close0，不能将改善归因专用工具。

公共base有54次file_read、25次code_run、10次intervene、30次wait、一次allow_complete（统计tool_call，不等于调用轮数或净收益）。D483能指出完成报告混入不存在的Canvas.Capture等目标，并恢复原7项任务。这些功能应作为退化检查，不能因学习PMA删除。

### 3.2 当前认识维护不稳定，但不是每轮失忆

公共base对working.md显式写入在D12，更新D34/D90；全501行dialogue中file_write1/file_patch2。file_read/code_run参数扫描发现D30读working.md，D4/D256读原任务；没有发现后期再次更新该文件的显式文件工具调用。未将code_run的一般执行能力等同于禁止其他写法，也不把日志未显式显示推断成绝对没有任何隐式写入。

D34正确把最初方向恢复标为已解决，D90记录绑定/工具栏/菜单关注；后续许多新修复没有在这份文件中形成最新认识。持续History仍包含后续行为，故“笔记旧”不是“模型无记忆”。但一份外部当前认识没有随决策持续维护，是可观察的缺口。

PMA R2有47触发/75操作/11注入，phase2直接消费新bank；Step46记录MIME变量遮蔽并给具体建议，task episode45改名重编译，随后记录恢复。这里维护—建议—后续观察路径明确；任务模型自己也看见编译错误，没有反事实证明提醒必不可少。

### 3.3 多看内容不是充分修复

公共base D201实际收到desktop.App中的fyne.App嵌入，D205却转向其他调查；D5已读原要求，D256又重读，最后D492读取synopsis、D496批准。不是没权限、没有原件或最后完全没有历史；关键缺口是没有确认接口方法集与原要求等价。

B D345实际收到完整bytes_test.go：监听flag在初次AddListener回调后未重置，格式化测试只检查Name/Data前缀。材料已经进入视野，后续仍没有指出这些弱断言。不能因此认定它批准了测试，因为运行未最终allow。

人工014则明确说空Refresh也能过现有断言，要求观察实际调用并重置计数；011要求先比较标准库Sscanf再改生产代码；015要求干净起始版本对照后停止追查。差距不仅是看得多，而是根据具体疑问选择能区分正确与错误解释的证据，并据结果退出。这里是人工建议原文，不是成本公平性或隐藏认知证明。

### 3.4 PMA的稳定维护也能稳定传播错误

Step28输入保留原CORS要求，但提醒主动加入credentials例外；Step30以gofmt后观察标COMPLETE；procedural保存为成功方法，最终该项失败。原要求没有丢失，错误解释与原要求共存。Step14–18另有错误缩进归因被保存复用。

因此不能直接复制“更新更频繁”后声称解决主问题；必须观察更新的是不是有效认识、后续新证据能否推翻它。

## 4. 已锁定与未锁定

- 确定：通用工具和连续跟进已能发挥；不该重建主体。
- 确定：PMA提供更直接的近期行为上下文和更新后bank；Clean依赖自主重建，私有当前认识在参照运行里更新不稳定。
- 确定：两边均存在读到信息仍错判；只优化检索不足以保证解决。
- 未锁定：观察入口与维护衔接哪个对净收益贡献更大；两者不能一起改后归因。
- 未锁定：强制分两次调用、固定三栏、增加输入是否值得成本；不作为默认实现。
- 未锁定：PMA相对Clean更优。FBR48轮与Fyne202轮不是同题工作量，42分与50分也不能用来比较效率。

## 5. 下一阶段建议：先对齐“当前认识被实际用于判断”

暂称“模型自用的活跃工作认识”，是借鉴增强基线，不先声明论文创新。服务A/B，仍处阶段1原因判别与最小候选准备。

下一轮先把设计压到一个可切换差异：怎样在同一监察者会话中，让它自主更新的重要认识在后续相关审议中直接可用，而不是只留在陈旧文件/长对话里。现有自然文件和通用工具足够，优先复用，不加ID、专用修复表单或第二维护模型；不规定每次wake必须写或必须多调一次LLM。若需要额外调用，必须显式列预算并做相应对照。

设计前必须列清现有working.md、压缩续接、U引用恢复、A选定调查的重叠；已实现的不能换名再建。若设计只剩重复提示“维护状态”，则尚未形成值得实现的差异，应停下而非开始跑题。

观察入口作为第二个独立候选：保留主动查询与两层结构，可比较模型主动读到的更完整公开意图/命令/结果视图与当前synopsis导航。先明确遗漏了哪段、多一次查阅的代价，不能默认被动发全量或同步逐轮审议。

## 6. 验收与停止

1. 先完成一个相干设计，准确冻结当前公共底座及可选开关；现有已通过工程不重做大清理。
2. 用户确认后每步≤600行，实现/协议回归只证明工程可运行；不使用合成评分选赢家。
3. 同一完整method_dev任务比较公共底座和单一增强版；任务/模型/预算/隔离一致，真实启动另确认。不以PMA FBR与Clean Fyne分数横比。
4. 同时审计更新、后续实际消费、判断是否改变、真实修复/复发、误干预、根范围、成本与延迟。文件更整齐、写入更多不是晋级依据。
5. 保留原有连续纠偏与通用能力；若旧认识被更稳定地重复但错判不减，停止维护方向扩张，转向依据修订而非加提醒频率。若仅增加算力带来改善，如实报告。
6. 同题出现可解释结论后停止汇报；成立再轮换开发题检查泛化。PMA对照独立保留，不修改作者baseline或向其加入任务答案。

## 7. 原始证据入口与本次交付

公共base：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-phase1-tool-feedback-base-20260911-r1/fyn-2.2.0-roadmap__kAxvamr/agent/monitor/monitor_private/audit/dialogue.jsonl`。
B：同jobs下`clean-monitor-fyn-2.2.0-roadmap-phase1-feedback-b-20260911-r4/fyn-2.2.0-roadmap__KkQAqgp/agent/monitor/monitor_private/audit/dialogue.jsonl`。
人工：同jobs下`clean-monitor-fyn-2.2.0-roadmap-phase1-manual-20260907-r1/fyn-2.2.0-roadmap__Fk7n6ZM/agent/manual_completion/interventions/archive/011.txt`、014、015。
PMA：`bench_runtime/pma_linux_controller/native_fbr_20260912_r2/work/trial/trajectory_memory.json`；完整运行审计见`PMA_NATIVE_FBR_R2_AUDIT_20260912.md`。

本次只新增本报告与checkpoint；验证方式为实际JSONL解析统计、选定原始输入/输出重读、当前源码对照。没有以统计工具数代替效果，没有再次跑API或修改生产文件。本阶段交付后停止，下一是小范围适配设计而非立刻新实验。
