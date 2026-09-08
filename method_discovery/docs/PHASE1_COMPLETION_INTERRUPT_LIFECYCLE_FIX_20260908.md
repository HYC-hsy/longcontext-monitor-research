# 完成等待与即时纠偏的生命周期衔接修复

用户在即时干预R1审计后授权“先修”。本轮只修确定的控制衔接，不改因果判断策略、不换模型、不启动真实任务。审计依据：PHASE1_LIVE_INTERVENTION_FYNE_R1_AUDIT_20260908.md。

## 改前与改后

改前：任务等待completion专用队列。普通intervene能进入任务邮箱，但无法解除该等待；worker结束普通review后又审已经过期的完成提议，产生300秒空等及重复模型调查。

改后：普通intervene仍通过唯一的任务中断邮箱交付。交付成功后，运行时同时解除当前completion等待并作废其代次；返回只说明继续处理已有纠偏，不复制纠偏内容。GA已有循环优先消费中断，消息只进入一次。若中断恰在completion注册前到达，任务侧只读的interrupt_pending查询阻止新建无意义等待。

失效信息为进程共享整数代次，仅描述请求是否仍有效，不分析自然语言、不决定语义正确性、不自动允许完成。worker合并唤醒命令时跳过失效completion，保留仍有效的任务进展。新完成提议有新代次，迟到旧回复不能批准它。

## 文件

- GenericAgent-main/monitor_agent_core/runtime.py：交付成功解除完成等待、过期代次过滤、一次性接收完成回复、注册前查询已有中断。
- GenericAgent-main/agentmain.py：提供现有ResumableInterruption.is_requested只读回调；GA专有对象未进入独立核心。
- GenericAgent-main/tests/test_monitor_completion_interrupt_lifecycle.py：5项新交叉时序回归。

本轮实现与测试分两步，每步均小于600新增/删除行；保留先前未提交的即时干预候选，不回退用户内容。不改prompt、provider、压缩、观察内容、模型等级、300秒超时值或无checker边界。

## 验证

1. 初始现有回归31项通过。
2. 新增与runtime/live-intervention联合17项通过。
3. 扩大联合87项通过，7.09秒：
   `python -m pytest tests/test_monitor_agent.py tests/test_monitor_provider.py tests/test_clean_monitor_runtime.py tests/test_monitor_handoff_recovery.py tests/test_monitor_agent_workspace.py tests/test_monitor_live_progress.py tests/test_manual_completion_boundary.py tests/test_research_agent_loop.py tests/test_monitor_live_intervention.py tests/test_monitor_completion_interrupt_lifecycle.py -q`
4. 强化测试明确等待旧提议实际被过滤后再提交新提议，新增5项复跑通过。
5. git diff --check通过，仅已有CRLF提示。

新测试运行真实_worker/MonitorRuntime控制代码，fake模型无API：普通review阻塞时归档不阻塞；完成请求随后到达；普通纠偏使任务恢复而review尚未结束；旧completion不再产生模型审查；新completion可批准。其余覆盖注册前中断、交付失败不解除等待、超时后迟到回复不影响下一提议、过期completion不吞最新boundary。

## 限制与门禁

若completion审议已经开始后才失效，不强行销毁监察者会话或取消其进行中的工具；旧批准不能生效，但正在进行的计算不保证全部节省。没有任何纠偏或完成决定时，既有300秒超时继续仍保留。

本轮不解决监察者未经验证断言死锁、调查期间认识过时、先长篇记录后观察的问题；它们仍需独立机制判别。工程回归不等于已改善真实任务完成率。

当前停在真实运行前。源码变化使上一manifest摘要过期，若后续获准真实验证需重新预检/生成manifest，并保持共同Fyne任务、Opus4.8/GPT5.6-sol high及既有预算；不自动换medium或重跑。
