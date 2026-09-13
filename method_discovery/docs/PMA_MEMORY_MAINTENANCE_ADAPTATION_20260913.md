# PMA 记忆维护接入持续监察者：实现与启动门禁

## 目标和基线

用户批准将PMA实际维护机制作为下一候选，解决判断依据逐渐被完成进度替代的问题。
服务于表示遗漏/错误闭合（创新A/B），不替换研究母体或宣称新算法已有效。
父版本053a9d3，改前标签checkpoint-before-pma-memory-20260913；未提交的.gitignore及历史文件未混入。
依据TOOLS_REPAIR_R2_META_REASONING_AUDIT_20260913.md：原要求被局部修复清单替换，已知缺项也被降级。
PMA自身FBR存在错误语义进入记忆后被接受的反例，因此本候选可能失败，不能预先保证解决错误闭合。

## 实施步骤

1. 独立包内逐文件纳入作者源码，每步分别为UniversalMemory、MemoryAgent、BM25，均不足600行。
2. 接入一次唤醒一次的维护调用、持久化、更新后记忆的实际消费、异常与成本留痕。
3. 做确定性接线、既有工具/控制回归、独立Linux导入检查，准备但不启动同题manifest。
测试代码、适配与接线步骤各自也在600行以内。没有改任务Agent执行循环或增加暂停工具。

## 作者代码与适配边界

仓库https://github.com/yifannnwu/proactive-memory-agent，commit
89e5c0d6aadfe531a1aee42fd290d48be89973dd，Apache-2.0。
`src/memory_agent/memory/{memory_agent,universal_memory,bm25_search}.py`
原样复制到独立包`monitor_agent_core/vendor/pma_memory/`，与作者仓库按统一换行比较全部一致。
复用BANK_TOOLS、PHASE1_SYSTEM、_build_phase1_prompt、_execute_tool_calls、UniversalMemory、
_format_memory_bank及其BM25超过50条时按知识/经验各top20选择逻辑。
完整作者文件保留，但不是所有函数都调用：不调用process、原text-only第二阶段、原逐任务步同步调度。
作者实际入口memory_enabled_agent._trigger_memory_agent等待process后取pending injection；
作者process的两个实际模型调用不传共享history，不能据docstring称共享会话。

我们的第二阶段仍是现有持续、有工具的监察者，拥有原history、文件/代码工具、纠偏/静默/完成控制。
这是PMA第一阶段机制适配，不是完整PMA复现；独立PMA外部基线不修改。

## 实际数据流

开关`monitor_pma_memory`，默认false；GA桥接开关`GA_MONITOR_PMA_MEMORY=1`，Harbor显式转发。
每次review开始，原任务 + 最近8条第一层synopsis + 最近至多80000字符的完整公开监察会话消息
组成维护输入（包含此前查阅结果和判断）。不输入加密reasoning/signature，不接触隐藏评分。
超出范围的历史明确标注省略；完整原始公开证据仍由原工具主动读取。
这与PMA原始“最近8个任务步骤的实际输出”不同，必须在效果解释中保留该适配差异。
本版不新增第三层任务观察，也不声称维护者已经读遍全部原始历史。

使用同一provider配置和取消句柄进行一次临时phase1请求；调用前保存持续history/system/hooks，
调用后或异常时恢复。维护请求不会把银行工具的未配对调用塞进持续history。
原工具调查仍持续同一会话。维护库位于monitor/pma_memory.json，原子写入，按任务隔离。
作者删除操作在当前库移除记录，但audit/dialogue.jsonl保留before/operations/after，旧证据不抹除。
操作失败整批回滚，异常向运行时显式传播，不生成SILENT或完成许可。

每个后续正常请求临时可见更新后的bank；原working.md、历史与主动工具保留，不强制新的调查顺序。
同一review内新调查首先进入持续history，下一wake再进入维护；不是每次工具调用后重新维护。
银行事实仍是模型判断而非认证证据，现有完成控制仍由监察者根据公开证据决定。
因此本版是加上可靠的维护—消费连接，不是已经完成判断依据的正确性保障。

## 成本与控制

每wake新增一次同模型调用；单独记录maintenance耗时、usage、输入/输出、操作及前后库。
普通provider用量/请求记录标注monitor_phase=pma_memory_maintenance，汇总时不得再把audit副本重复相加。
维持现有wake-owned stop：首次wake屏障覆盖新增维护延迟，首次纠偏后局部并发不改变。
这是确定的额外延迟，不能预称降本或更及时；真实测试要比较是否收益大于代价。
记忆压缩阈值、任务模型、监察模型、现有唤醒/投递策略均未改变。

## 验证与限制

- 新增test_monitor_pma_memory.py：更新后可见、原工具保留、会话恢复、异常恢复、删除修订留痕、
  task-local、源码一致性，以及真实provider类使用假传输的接线检查。
- 联合test_monitor_agent、decision_context、core_independence、correction_schedule、host_contract、
  completion_interrupt_lifecycle：最终63 passed（10.53秒），零API；包含纠偏后同一review不重复维护及容器开关转发检查。
- 另运行旧test_clean_monitor_runtime，5个失败均发生在旧fixture缺task_id或task_workspace处。
  HEAD原签名/桥接已要求这些参数；本轮没有修改这些接口，也没有为过旧测试放宽接口。
  不宣称仓库全量测试通过。
- shortuuid已在Windows ga_bench和现有Linux运行环境中存在，并加入独立包安装依赖。
- 无网络Docker使用现有Linux Python3.12运行环境、只挂独立包导入成功，4个作者bank工具可用；未挂密钥、未调用API。
- 待真实运行验证：Claude是否合理保存/修订依据、记忆污染、首次延迟和整体效果。

## 下一次真实门禁

准备脚本method_discovery/prepare_pma_memory_run.py，输出artifacts/pma_memory_20260913/fyne_r1_manifest.json。
Fyne2.2，与tools-repair-r2同题、任务/监察者各自独立Claude Opus4.8配置，500turn/10000秒，
保持no-network-unix-inference-v1。唯一候选新增为上述维护链与可见bank。
主要看原要求是否存活、局部修复是否仍越权关闭全局要求、依据是否修订；同时统计新增成本和延迟。
native verifier仅事后评价。此处工程通过不等于方法有效；真实启动须另经用户确认。
