# 续接工程修复 A：可诊断性（不含恢复策略）

来源：专家 ROOT_DECISION_R1_audit_and_next_steps_2026-09-17.md。
R1 实际失败响应未留档，无法事后确定拒绝原因。本次不声称复现其确切输入。

## 改动

- provider 保留 Anthropic message id、stop_reason、流完成标记、block类型；
  与 usage 分离，逐请求清除旧元数据。模型上下文不接收这些元数据。
- 续接调用使用 transaction_id / purpose，记录实际 request_id 以及 system、空工具
  指纹。在 note_text 校验前将完整解析响应写入本地 audit/continuation_responses。
- 原有三个 note_text 拒绝分支使用 ValueError 子类与固定 code；不扩大通过范围。
- 失败记录区分 request、response_archive、note_validation、可选验证及 note_storage。
  运行时跨进程回执携带内容无关的 cause_chain 和失败时间，不附任意内层异常正文。
- note_validated、continuation_saved、compaction_committed 分别表示校验、保存和
  历史替换；归档/校验失败时不删历史前缀，不执行续接返回的工具。

## 明确保留的未完成项

本步仅补诊断：stop_reason 已记录，但尚未按 max_tokens 等原因拒绝或恢复。
下一步 B 将定义用途校验和最多一次受限格式恢复；当前截断文本仍可能通过旧文本
校验，不能称已修好截断接收问题。无新增模型调用、无自动重试、无策略或预算变化。
未修改根合同/simple、PMA调度、bank或压缩阈值。未更换模型。
请求暴露计数、强制压缩与动态提议联动仍需后续综合验收，不以选择事件代替请求。

## 验证

ga_bench pytest：continuation_diagnostics、continuation_mode、handoff_validation、
provider、root_contract、pma_fused 合计116 passed。
覆盖解析→请求→续接校验→历史提交的确定性链路（模拟网络，不是真实API）、
意外工具/混合响应、失败前留档、失败原因链、存储故障、请求身份关联及现有回归。
git diff --check 通过；单步代码与测试改动小于600行。

扩展运行 transport_recovery + clean_monitor_runtime：17 passed，5 failed。
失败为旧夹具缺少必需 task_id / task_workspace，在构造运行时/适配器时发生，
未进入本次诊断分支；本次没有改这些构造参数。未放宽生产校验，也未修无关夹具。
因此总计133项通过、5项失败，不宣称整个仓库回归全绿。

## 归档与发布

本地原始响应可能包含模型专有块或任务信息，不纳入公开导出白名单。
公开进度仅元数据，不把原始正文当错误消息发布。现有导出脚本不扫描此新目录。
本轮未运行真实API/任务，未推送远端；旧R1保持不可评分的工程失败。

下一阶段 B 完成后，两组需要重新生成相同源码/宿主 hash 的 manifest 和新 run-id。
