# PMA原要求优先与有时序依据候选

用户在R2审计后批准最小实现。父版本bdb09c7，实现基线ccf1537。
研究范围不变：减少unsupported closure；不新增模型、调用阶段、checker或强制测试清单。

## 实际依据

R2 tMxLFoa中：监察12:23:24.503Z确认all.go不存在；任务12:23:25.120Z才选择创建。
监察12:25:39.647Z确认sprintf.go旧实现；任务12:26:18.477Z才选择重写。
PMA将旧观察解释为新写入未生效，形成错误的文件系统经验。
最后记忆仍保留desktop.App要求，却根据DesktopApp与根包go build认定完成。
时间为原始dialogue与research_events；最终原生2/7，不把局部纠偏当整体成功。

## 改动范围

- runtime._archive仅新增archived_at Unix秒元数据，不改唤醒/停止/恢复。
  这是公开边界归档时间，不是精确执行起止时间，不假装具备跨主机时钟同步。
- pma_observation显示最近8步各公开边界的UTC时间、来源；监察命令展示调用和返回时间。
  异步session返回不等于执行结束；重叠/缺失时间不得据此断言写入失效。
  原始轨迹没有时间的历史项明确unknown，不反填推测时间；旧实验保持原样。
  原命令/输出大小边界与最近4检查数保留；时间和来源置于命令前避免长参数截掉元数据。
- pma_judgment新增轻量MemoryAgent子类，只覆盖两阶段输入构造。
  第一阶段整理要求/声明/变更/观察，不提前裁决全局完成；第二阶段先读原要求与近期材料，
  判断什么证据能支持当前决定，再比较记忆。同步修正原system的“先看记忆”步骤。
  不只追加原则而保留冲突的用户任务指令。模型仍自由选择检查形式，不要求字段表单。
- pma_memory实例化该子类；process、工具执行、bank、检索、解析均继承作者代码，vendor零修改。
  因输入构造与提示已适配，不称原提示完整复现。

保持：follow/patrol控制、通用工具、持续history、根完成协议、独立配置与无网络隔离。
每次wake仍原有两个PMA调用；没有新增API调用。输入只增加有界时序说明。

## 工程验证与边界

pytest九组沿用上一阶段：pma_memory、pma_two_phase、follow_wait、correction_schedule、
monitor_agent、core_independence、completion_interrupt_lifecycle、host_contract、decision_context。
新增验证：实际runtime归档时间；旧检查与后续写入均保留不同时间；缺时间unknown；
输入先上下文后记忆；作者process仍原函数；原有工具/完成/并发回归。
首轮75通过1失败，为旧提示短语断言，改成当前维护职责断言。
最终76通过（10.63秒），diff --check通过；代码累计新增120/删除20行，含测试。
这些测试只证明接线与控制未回归，不证明模型真正遵循判断顺序或已经降低错误闭合。
所有代码改动累计小于600行；未调用API、未启动真实任务。

真实验证须新run-id/新源码摘要并单独确认；重点看虚假写入故障、检查范围与完成判断、
有用观察及是否无限验证。暂不调整其他提示或加入新机制。
