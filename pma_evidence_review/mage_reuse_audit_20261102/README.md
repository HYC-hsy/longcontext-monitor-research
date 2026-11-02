# MAGE 与现有 P1：复用、遗漏和必要适配核查

固定对照：MAGE `868e36bd3bdb378250f2f7457af5960193c9598c`；P1候选 `c5678323b6986aa84ee7407890a146bb5af40318`。本轮只读代码与已有结果，无代码改造、模型调用或任务运行。未引入用户暂不需要的树分支、执行回退、额外审核者。

## 结论表

|项目|MAGE实际实现|我们当前实现|判断|
|---|---|---|---|
|原始事件保存|底层集中保存动作—观察节点，上层引用ID|每轮重复存model_input、visible_events、raw_generation_context，其中近期窗口重叠|值得借鉴事件表＋引用，减少重复；精确模型输入快照仍要保留，重复存档不是已证实的模型错误原因。|
|摘要关联范围|Store自动关联当前待整理段的_raw_node_ids，并清空该段|每条新记忆绑定生成时同一个八轮输入窗口，可能含旧摘要、状态、无关事件|关联变粗了。这不是去掉树所必需；但PMA没有Actor主动Store边界，补成精确覆盖需先明确谁确定片段。|
|实际读源|内部保留节点，未提供等价的只读read_source工具|自写工具返回最多8000字符的投影视图，超大事件整条省略，无分页；完整投影前材料只归档|完整保存未等于完整可读。该返回策略是自定边界，应优先检查简化/按事件读取；MAGE没有现成分页组件能直接搬。|
|无效工具后的恢复|返回错误观察，进入下一轮；参数TypeError转换为可读错误|未知工具记录为tool_error；只有请求memory_read_source才进入续答，实验遇错误停止|有限纠正是可借鉴但未移植的机制，不需要树/回退。必须显式限调用预算并保留失败，不能静默重跑追认首测。|
|当前上下文组织|当前路径摘要＋未压缩raw；必要且环境提供时补当前环境观察|原任务独立保留，旧bank/status＋近期八轮动作回执|原任务和近期原文并未遗漏。MAGE的_current_env来自环境，不等于自由生成状态；不能把P1状态当独立观测。|
|只读来源接口|没有与memory_read_source等价的普通模型工具|我们新增只读ID工具与来源校验|不是重复造了现成轮子。MAGE Backtrace实际是截短上下文/恢复执行，不是展开证据阅读。|
|工具对话协议|自定义ActionName[{JSON}]文本协议，输入仍为system/user|PMA已有结构化tool calls及文本fallback，读源后文本续接|不能声称我们漏搬了MAGE的原生tool messages回路；切换整套解析器会增加不必要改造。|
|事件去重|同父下action.name＋observation＋可选env相等即合并，不比较params|可靠event_id标记已见，同文不同ID不合并|保留我们的规则；直接照抄会有不同命令同回执被误并风险。|
|任务/来源身份保护|主要为内存树/列表，无同等持久化校验|任务隔离、条目内容与来源哈希、绑定失败撤回本次保存|必要工程，应保留。不是LLM承担这些校验。|
|历史角色隔离|同一Actor生成行动与Store摘要|外部P1看到另一Actor历史，其中包含旧工具名和SYSTEM/RULES文字|外部观察者架构必须适配，MAGE没有现成隔离模块可直接替代。|
|提示生成|动作说明、格式示例、轨迹由prompt组件生成|候选对BASE提示做多次str.replace后追加规则|存在可维护性风险，可考虑单一模板/显式槽位；未证明引起本次真实错误，不宜当成语义根因。|

## 与首轮实测的关系

- 旧版25f4首测4例中没有一次实际读源，因此8000字符投影、只读active条目等限制不能解释为“导致了此次已发生的读源误判”。这次没有读源消费可供这样归因。
- 第一例局部成功写成整体完成，是摘要语义失真。MAGE普通Store也由模型写摘要，没有一个可直接移植、保证忠实的通用检查器。
- 第四例file_read出现在收到的结构化返回，宿主正确拒绝。不能把它归为文本fallback误解析，也不能说换MAGE解析器就能解决。历史角色漂移是与可见输入/输出一致的解释，尚非原始HTTP层证明。
- c567修了角色隔离与范围措辞，但尚未真实复测。31项离线通过只代表相关接线检查。

## 真正缺的与没缺的

最值得补齐的是：**原始事件可独立寻址、摘要关联的覆盖范围清楚、归档资料能被消费方实际读到。** 三者不依赖执行回退或树分支。

当前实现更准确的名称是“原PMA摘要＋生成窗口归档＋有限只读回查”，不是MAGE完整的分段记忆组织。整窗索引并非错误设计，但不能把它说成精确证据覆盖。

相反，没有发现MAGE已有一套可直接替换SourceArchive的成熟回查组件。DictAgentSTMemory只是task_id到(action, observation)列表。也没有发现被遗漏的通用摘要真值审核器或自动发现后续反证的组件。

删除知识不应与删除原始事实混同；但MAGE保留历史节点主要服务树/回退，不是现成的“已删GAP阅读接口”。我们active-only读取是自定限制，未来P2需要历史查询时应明确事件读取权限，不必引入旧版本知识自动复活。

## 固定源码定位

- [MAGE TreeNode/SummaryNode及覆盖ID](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/memory/ExplorationTree.py#L22-L62)
- [MAGE Store覆盖当前段](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/agents/MAGEAgent.py#L406-L447)
- [MAGE当前摘要/raw/环境上下文](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/agents/MAGEAgent.py#L185-L238)
- [MAGE工具错误回执](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/agents/BaseAgent.py#L209-L253)
- [MAGE无效动作保留/下一轮](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/agents/MAGEAgent.py#L298-L316)
- [MAGE简单动作观察列表](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/memory/AgentSTMemory.py#L24-L37)
- [MAGE节点去重](https://github.com/Komorebi660/MAGE/blob/868e36bd3bdb378250f2f7457af5960193c9598c/agentcore/memory/ExplorationTree.py#L165-L179)
- [本方投影限长](https://github.com/HYC-hsy/longcontext-monitor-research/blob/c5678323b6986aa84ee7407890a146bb5af40318/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/p1_source_archive.py#L48-L127)
- [本方捕获、绑定与活动读取](https://github.com/HYC-hsy/longcontext-monitor-research/blob/c5678323b6986aa84ee7407890a146bb5af40318/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/p1_source_archive.py#L187-L249)
- [本方维护工具与续答](https://github.com/HYC-hsy/longcontext-monitor-research/blob/c5678323b6986aa84ee7407890a146bb5af40318/method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/p1_source_agent.py#L101-L245)

固定MAGE树的134个路径中，仅查到benchmark/webshop/WebShopEnv/LICENSE.md，未找到覆盖MAGE核心agentcore的明确许可；该嵌套许可证不能自动覆盖核心代码。因此本轮只做结构与接口对照，没有直接复制核心代码发布。
