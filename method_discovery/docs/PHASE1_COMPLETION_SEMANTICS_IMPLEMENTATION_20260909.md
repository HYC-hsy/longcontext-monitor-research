# 完成控制语义修复：工程验收

用户确认DESIGN中的策略后实施。当前阶段完成，无API调用、Docker启动或真实任务运行；未实现R、未修改U的策略、未改变模型或实验预算。

## 改前与改后

|问题|改前|改后|
|普通review中到达完成提议|入口pending=false，已看到提议仍不能批准|每次模型调用前获取当前提议元数据，加入同一会话；批准绑定模型已获知的代次|
|批准时提议已换代|不能在当前普通review处理；依靠后续完成review|工具执行时再校验代次；不把旧批准重绑定新提议；最终pump仍拒绝晚到结果|
|完成时wait|自动合成无语义内容的CONTINUE|工具明确告知任务已在等答复、等任务轮数不会进展；不发送任务消息，允许继续查证/决策|
|300秒没有决定|撤销提议并要求任务继续|只记录completion_delayed，保留同一提议与正在进行的审查，不重复启动review|
|总预算或审查失败|通常仍转CONTINUE|CompletionOutcome.incomplete，经GA adapter转ERROR_FAIL_CLOSED，任务循环退出，不再调用任务模型续写|
|不完整退出的归档|协议结束可能被wrapper当作正常运行结束|runtime写completion_incomplete.json；当前标准Harbor入口优先识别该标记，退出126，archive_status=monitor_review_incomplete|
|被拒绝wait的压缩边界|只要出现wait调用/结果就可算结束|仅accepted控制结果构成完成边界，未结束调查不被误当成可裁剪review|

共享generation和cursor只用于工程身份绑定，模型不维护ID。元数据只是提议位置，不是新增语义中间层。普通任务继续并发、两层观察、通用工具和即时纠偏不变。pending wait不是强制它得出某个答案；如果仍无结论，按已有review步数或总预算记录未完成，不自动批准。

## 文件改动

- `monitor_agent_core/loop.py`：每次调用前的可选状态更新钩子。
- `monitor_agent_core/agent.py`：当前提议续入、已见代次校验、干预后禁止重批、pending wait反馈。
- `monitor_agent_core/runtime.py`：共享提议元数据、沿用原提议等待、迟延记录、总预算/故障未完成出口和原子标记。
- `monitor_agent_core/provider.py`：压缩只以真正accepted控制结果作为review边界。
- `ga_monitor_adapter.py`：从启动器接收截止时刻；incomplete映射独立非成功出口。
- `long_context_bench/adapters/harbor_ga_agent.py`：在启动GA前按原timeout_sec生成截止时刻；识别未完成标记而非协议哨兵即视为成功。
- 测试文件：test_monitor_live_intervention、test_monitor_completion_interrupt_lifecycle、test_clean_monitor_runtime、test_monitor_handoff_recovery、test_monitor_provider、test_monitor_continuation_mode、test_research_agent_loop、test_harbor_tb2_m4。
- `.gitignore`：显式允许本阶段设计/报告及U运行审计文档进入Git；未加入密钥或大日志，未自动commit。

按四步递增实现，每步代码增删远低于600行。工作区仍含此前U改动；不能把整个HEAD diff当作本轮新增，也未回退或覆盖用户改动。

## 验证

GA联合102项通过（7.94秒）：agent、provider、live_intervention、completion_interrupt_lifecycle、clean_monitor_runtime、handoff_recovery、grounded_context、core_independence、research_agent_loop、continuation_mode、incremental_audit。

Harbor/runner联合92项通过（0.82秒）：test_harbor_tb2_m4、test_harbor_ga_lhtb、test_run_ultralong_m12_proofs。

原始JUnit：
- `method_discovery/artifacts/phase1_20260909/completion_semantics_ga.xml`
- `method_discovery/artifacts/phase1_20260909/completion_semantics_harbor.xml`

重点验证同review处理新提议、不可批准未见新代次、干预后旧批准无效、pending wait不恢复任务、迟延后仍能批准同一提议、预算耗尽非成功、普通审查失败不生成continue、任务循环不再续写、压缩仍能保留原文/近期历史。

期间修正测试夹具：旧1秒超时fixture等待的是已废弃的自动续跑，改为真实纠偏使旧代次失效；压缩fixture的纯文本accepted改成实际工具协议JSON；新Harbor fixture补齐必需的monitor_config。没有降低断言或恢复旧协议。

## 限制与下一步

- 194项工程通过，不证明监察效果改善或模型能够自然结束调查。模型可能仍多次pending wait，最终触发现有review上限；会明确作为未完成而非任务偏移继续处理。
- 本次截止时刻/未完成归档端到端接线针对当前Fyne使用的标准Harbor入口。LHTB旧回归通过只说明未改坏既有代码，不等于其持久多阶段会话已完成新截止时刻策略适配；若换此类入口，需单独检查阶段预算，不能宣称所有harness已验证。
- 容器硬杀、磁盘故障等仍可能只留下部分归档；不能承诺一切外部中断都有完整尾部日志。
- 审查故障未在本次扩大自动重试机制；provider现有重试保留，耗尽/审议异常作为明确未完成。
- 下一步先由用户选择真实验证本协议，或进入R候选的独立设计。任何真实启动仍需任务/模型/预算门禁。不自动叠加R或重新跑U。
