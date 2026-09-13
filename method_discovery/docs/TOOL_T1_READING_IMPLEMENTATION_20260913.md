# T1 读取工具：工程实现完成

依据：CLAUDE_FYNE_R1_COMPLETE_TOOL_AUDIT_20260913.md；用户确认先改工具、后讨论策略。

本阶段只改file_read实现及其工具说明，未改稳定监察策略、调度、状态组织、provider、GA适配、模型配置。未启动真实任务或调用模型API。

## 改前与改后

- tail原仅在live_awareness开启时出现在schema；现在一直可用，不必启用另一个机制。
- 原count只限制行数，单行JSONL可返回巨量内容；现在默认内容上限20000字符，可调整到200000，超出返回next_read参数。按Unicode字符续读，保留行内offset，原始材料无删改。不增加语义过滤层。
- next_read只续完本次选定范围，不悄悄扩大阅读范围。more_lines_after_range另行说明文件后面是否还有其他行；tail续读转换成明确行范围，避免再次取尾造成重复或跳跃。
- 原文件不存在只报路径；现在说明文件尚可能未生成，不得视为行为不存在。
- 普通读取仍只要求path；offset通常无需模型自行计算，直接采用工具返回的next_read。

## 验证

- 初次针对性回归36通过、1失败：旧测试要求关闭live_awareness时隐藏tail。更新为两种配置均有tail，符合本阶段解除耦合的目标，没有恢复旧行为。
- 最终 `tests/test_monitor*.py`（排除旧退役monitor_semantic_files套件）：281 passed，15.29秒。
- 新测试覆盖Unicode巨行无损续读、换行边界、CRLF、尾读续读、空文件、EOF、无效offset/budget、文件不存在和基础schema；diff --check通过。
- 改动文件：monitor_agent_core/{agent,workspace}.py、tests/test_monitor_read_continuation.py、tests/test_monitor_live_awareness.py。本阶段代码总量小于600行。

## 限制与后续

读取的是live文件而非冻结快照；返回sha256和明确提示，内容被重写时需要重新读取相关范围。未增加快照或强制版本前置条件，不限制并发观察。
本次是模型可见content输出预算，不是整个JSON消息的token硬预算；其他工具与完整原始归档不受影响。仍扫描文件计算原有sha256，未声称实现大文件尾读I/O加速。
效果、默认预算是否合适需后续真实任务验证。T2组合查询续读与T3执行会话仍未实现；本阶段完成后停下，不自动启动真实任务。
