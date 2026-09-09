# 阶段1 / S2候选U：按需恢复判断依据

日期：2026-09-08。用户已授权候选实现；仅工程验收，真实启动仍需独立确认。
父版本：f2ac266（clean-monitor-foundation-20260908）；研究文档提交66a2427。

## 目标与证据锚点

维持原研究问题：表示遗漏、无充分证据的错误闭合；本次服务A/B的依据保留与可修订性，不新增checker。
自动Fyne incremental-audit R1在认识续接后，把no-partial-mutation建议升格为原任务要求，尚不能据此锁定压缩是唯一原因。
本轮重读人工参考入口及原始011/014：人工对照实际Sscanf与测试断言，检查真实Refresh调用而非字段变化。
启发是按当前疑问恢复判断依据，不是把这些领域规则加入提示词。

## 本次最小实现

`model_config.monitor_grounded_context=true`启用；缺省false。现有runtime原样传递model_config，无GA专用新接线。
1. 模型仍通过file_write/file_patch维护自然Markdown笔记，不强制字段、ID或每轮写入。
2. 可在笔记中留下简单内联链接，例如`[依据](task/original_task.txt#L10-L30)`，支持尖括号包裹含空格路径。
3. 可选工具`read_with_sources(path, start=1, count=200)`同时返回所选笔记与其链接的实际当前原文。不是让模型凭记忆重新写引用。
4. 确定性工具只展开一跳，默认来源前200行，显式范围单次最多1000行，每次最多8条链接。未展开链接、后续笔记行和缺失来源显式可见；继续用同工具分页或普通file_read/code_run，不限制原子能力。
5. 每次读取将笔记、源摘录、全文hash与时间归档到`monitor/audit/source_reads/`；同一链接与上次读取相比，分别报告文件变化与摘录变化，旧原文留存可回查。模型不需要填写hash。
6. 压缩维持既有算法，只在启用时提醒续接保留有用链接/调查路径；没有额外维护模型调用或强制重读。

实际差异：过去恢复笔记需自行再次定位/读取各来源；现在一次按需读取可将笔记和原依据共同带入同一History。不是自动找对来源、自动判真或承诺新算法已有效。
链接可以指向原任务、实际代码、公开日志或私有认识；私有认识不会因此成为任务事实。两层任务观察不变，局部调查笔记不是第三层语义证据。

## 保留与边界

- 不改并发调度、强制纠偏、模型唤醒轮数、completion生命周期或任务侧工具。
- 不要求调用新工具才能干预、静默或完成；不用时不产生额外API调用。
- 不实施W写入校验或R额外控制循环，不叠加多个待判别机制。
- 文件变动不是语义失效，未变不是笔记正确；行号可能漂移。第一次读取无法知道笔记撰写时的源版本。
- 多文件读取不是同时快照；并发任务可以在读取后继续修改。变化比较只在再次调用时进行，不是后台自动失效检测。
- 链接为轻量内联语法，不声称完整Markdown解析器或语义索引。不递归扩展或自动抓公网链接。
- 复用file_read的读取实现：为全文hash会扫描源文件；大日志及过多来源仍有I/O/上下文成本。provider既有工具结果归档仍适用。未证明降本或延迟改善。
- 模型可能不使用工具、引用错位置，或仍误读原文；这些属于真实候选判别，不通过强制流程掩盖。

## 文件与验证

- `monitor_agent_core/grounded_context.py`：确定性来源读取、变化回执、版本归档。
- `monitor_agent_core/agent.py`：可选工具/提示/压缩续接接线，关闭后保持旧工具与稳定提示。
- `tests/test_monitor_grounded_context.py`：真实文件、跨重启、缺失/越界、范围、无递归、同会话工具与直接干预验证。
- 根`.gitignore`：精确放行新测试和本报告；核心新模块已被现有包规则覆盖。

首轮30项通过；扩大核心/provider/工作区/runtime/恢复/实时干预/归档/完成生命周期联合回归78项通过（6.03秒）。
命令：在GenericAgent-main运行ga_bench Python的pytest，指定test_monitor_grounded_context、test_monitor_agent、test_monitor_provider、test_monitor_core_independence、test_monitor_agent_workspace、test_clean_monitor_runtime、test_monitor_handoff_recovery、test_monitor_live_progress、test_monitor_live_intervention、test_monitor_incremental_audit、test_monitor_completion_interrupt_lifecycle。
每个实现步骤均小于600增删行；未修改密钥、模型、预算、任务材料或启动Docker/API实验。

## 下一门禁

工程可用不等于有效。建议同一Fyne method_dev任务/模型/预算运行候选U，启动前生成新manifest并报成本与判别目标；用户确认前不得启动。
重点看模型是否主动恢复依据、有没有改变错误纠偏/错误闭合、是否保留已有有效纠偏，以及调查成本/响应延迟；若仅增加阅读而不改变控制结果，也必须如实记录。
W仍是独立待实现对照，不因U工程通过就排除；R仍后置。尚未冻结论文方法。
