# 续接工程修复 B：用途校验与一次格式恢复

在诊断A基础上实施；未修改 decision/simple 的研究处理、PMA bank/阶段、普通调度、
窗口上限或模型。未启动真实任务。R1实际被拒响应缺失，仍不能确定其原始原因。

## 行为

- note_text 消费独立 metadata；max_tokens 拒绝为 truncated_note，tool_use 为
  unexpected_tool，不完整流及非正常stop也拒绝。缺少停止字段保持显式未知，
  不伪造 end_turn；仍执行原文本/工具检查。当前实际Claude解析会保留该字段。
- 主续接事务对 unexpected_tool、empty_note、reasoning_echo、truncated_note
  最多再请求一次笔记，固定同模型、同上下文、同输出上限。不进入第三个review。
- 每次响应各存本地 transaction-attempt 文件；失败工具不执行、不加入History。
  仅替换当前临时续接指令；finally恢复原system、purpose并移除临时输入。
- 重试前检查cancel/stop/deadline，实际请求继续使用既有传输预算。第二次仍失败
  明确终止；存储异常、真实容量超限、非正常停止不无差别重试。
- 调用增加如实计量：第二次标记 continuation_format_repair，request purpose 为
  format_repair，沿用同事务。并不声称零额外调用或零额外成本。
- 可选handoff_validation只复用严格校验，未启用该候选、未增加第二验证阶段。

## 验证

ga_bench pytest：continuation_repair、continuation_diagnostics、continuation_mode、
handoff_validation、provider、root_contract、pma_fused、transport_recovery：137 passed。
无真实API，模拟网络响应。覆盖一次恢复成功/耗尽、工具混合输出、截断、停止/超时、
存储失败、历史保留、用量以及强制压缩期间提议更换后使用最新root request_id。
git diff --check 通过。代码/测试每步小于600行。
旧clean_monitor_runtime缺参夹具问题不在本轮修改；不宣称全仓库全绿。

## 后续

两组须用当前同一底座生成新run-id与source/harness hash，不能复用R1 manifest。
先重跑decision再跑已冻结simple，预检后真实启动需确认。
R1保留为有真实成本的工程失败、无原生评分，不能纳入得分0或候选效果结论。
选中合同不等于模型请求已成功；审计须结合purpose、实际请求/响应和执行控制事件。
本步未推送远端，也未做额外记忆/提示优化。
