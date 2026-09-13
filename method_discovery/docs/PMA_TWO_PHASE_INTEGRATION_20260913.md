# PMA 完整记忆执行链接入

## 授权、目标和范围

用户批准接入作者维护—比较—提醒完整循环，尽可能使用原代码；真实启动仍另行确认。
服务表示遗漏与错误闭合的判断依据问题，不变更研究主体、模型、checker边界或控制顺序。
改前回退标签checkpoint-before-pma-two-phase-20260913（2130894，生产代码源自73d0d4d）。
步骤：作者输入方法提取和宿主映射；完整process接线；失败/会话/控制回归；准备真实门禁。
各步骤代码增删合计均小于600行，没有模型API调用。

## 实际复用

作者仓库yifannnwu/proactive-memory-agent，commit89e5c0d6aadfe531a1aee42fd290d48be89973dd，Apache-2.0。
原样保留memory_agent.py、universal_memory.py、bm25_search.py。
现在直接调用MemoryAgent.process，而非自己分步模仿：
_build_phase1_prompt → _call_llm_phase1 → _execute_tool_calls →
_build_phase2_prompt（更新后的bank）→ _call_llm_phase2 → _parse_phase2_response。
两个system prompt、银行工具、保存/删除/状态更新、BM25与提醒解析保持作者逻辑。
额外从作者memory_enabled_agent.py原样提取_get_memory_agent_context和_format_step_entry，
置于独立vendor/pma_memory/context.py；测试核对两个方法AST一致，未拉入Terminus2/Harbor依赖。

保留差异：不是原论文完整实验复现。任务调度仍为本地wake-owned stop/纠偏后并发；
PMA提醒交给已有持续监察者，不直接注入任务Agent；原根完成权限不交给PMA。

## 输入适配

原来的8条synopsis+最多80000字符监察会话被移除。
现在按宿主标准task_turn合并前后边界，取最近8个任务轮次，交给作者格式化方法。
行为来自原始公开text/tool_calls/tool_results，不引入模型生成的第三层语义观察。
文本和结果各最多10000字符，命令各2000字符，作者保留最多5条命令及剩余数量提示。
裁剪明确标注，附公开事件行位置，最新轮可能未执行完，不冒充完成观察。
补充最多4条有content/stdout的近期监察工具回执，每条3000字符，以及最近提交纠偏4000字符，
分别注明不是整体完成证明/不是uptake证明。不重放整段监察结论；完整history仍在主监察者中。
这些是宿主适配，不声称与作者原始8个Terminus2步骤输入逐字相同。

## 执行与异常

同一provider模型、配置、取消句柄执行两次临时上下文调用，各自恢复持续history/system/hooks。
更新后bank继续进入原active context；第二阶段提醒进入本次wake上下文，仅作为调查线索。
no_intervention不会自动wait或allow_complete；有提醒也不会自动intervene。
现有调查/工具/持续会话、第一次纠偏后并发跟踪、根完成控制均保留。

作者process捕获阶段异常；PhaseTransport记录原异常，第一阶段失败时不再实际请求第二阶段，
process返回后将异常显式传出。未识别的第二阶段输出不是正常静默（先按作者逻辑剔除think标签）。
失败批次恢复上次持久bank，前后状态与attempt留痕。没有恢复旧兼容分支。
阶段调用usage/request_attempt分别标注pma_memory_maintenance与pma_memory_comparison，
audit事件pma_two_phase包含完整作者result（两阶段prompt/raw response/operations）与前后bank。

## 预期与代价

目标：原要求仍在bank时，作者第二阶段是否会提出当前实现/完成声明与其不一致的线索，
从而改变原监察者的调查或纠偏，而不只是重复已知进度。
两次PMA调用加现有调查，较上一版每wake多一次；首次屏障等待也可能更长。
输入整理与第二阶段一起变化，不能把效果差异单独归因于第二阶段；后续需消融。
原PMA并不保证unsupported closure正确，未预宣称有效。

## 工程验证

联合test_monitor_pma_memory、test_monitor_pma_two_phase、test_monitor_agent、decision_context、
core_independence、correction_schedule、host_contract、completion_interrupt_lifecycle：70 passed，11.33秒。
覆盖原process实际调用、原prompt、phase2消费新bank、正常no-op仍走主review、提醒不自动干预、
phase2失败不污染history、工具能力保留、同review不重复维护、八轮合并、原方法一致性。
无网络Docker只挂独立包和既有Linux运行环境，导入成功，无密钥/API/真实任务。
旧R1真实归档的末轮输入映射读取成功：Step76–83，观察文本32584字符（未计银行prompt），
这只是输入工程检查，不是模型效果或成本实验。
此前5项旧fixture接口失败未在本轮扩展修复，不宣称仓库全量测试通过。

## 文件与启动门禁

核心：monitor_agent_core/pma_memory.py（完整process桥）、pma_observation.py（宿主输入）、
vendor/pma_memory/context.py（作者方法）、agent.py（提醒进入wake）。
测试：test_monitor_pma_memory.py与test_monitor_pma_two_phase.py；来源说明vendor/NOTICE.md。
prepare_pma_memory_run.py现在只准备新pma-two-phase run-id，不复用旧R1身份或更改旧manifest。
开关仍为GA_MONITOR_PMA_MEMORY；历史候选通过源码hash与Git回退区分。
预定同一Fyne2.2，独立Claude Opus4.8两方，500轮/10000秒，无网络隔离，native仅事后。
主对照为PMA维护R1，原tools-repair-r2作为辅助参照；真实运行须用户确认。
