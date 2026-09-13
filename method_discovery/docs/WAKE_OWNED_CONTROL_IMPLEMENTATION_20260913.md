# 静默到唤醒的工程等待

## 授权与纠错

用户明确要求将6b541b7的“公开选择intervene后停止”改为“静默到唤醒即停止”。这属于已授权实现，不仅记录计划。代码改动不足600行，未启动API或真实任务。旧实现保存在6b541b7。

## PMA作者原始等待位置

固定仓库yifannnwu/proactive-memory-agent，commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd。
src/memory_agent/memory_enabled_agent.py：

- 332–336：保存原始任务、积累初始观察，触发时await _trigger_memory_agent(step_count=1)，再进入任务episode循环。
- 519–529：本步完成、积累观察后检查should_trigger；触发时await _trigger_memory_agent，返回后才进入后续任务。
- 198–210：_trigger_memory_agent内部await self._memory_agent.process，之后保存应注入内容。

因此其等待由运行顺序决定，不是模型选择暂停，也不是先得到提醒内容才阻断。严格说是每个配置触发点等待，不是所有配置下每步无条件调用；GA同步PMA基线在agent_loop模型调用前pma.review()等待已有适配。

这里复用的是上述已核对运行顺序，并适配独立进程/持续局部循环。没有把原PMA MemoryAgent及银行维护替换进Clean，没有把简单await语义声称为整套控制代码复现。上一版从LivePlan提取的阻断谓词对本次已明确状态转换没有必要，已移除，避免形式上的代码复用。

## 当前实际顺序

1. 初始化：宿主在启动监察进程前安装barrier，避免任务模型抢先启动；进程第一次review握手确认宿主barrier。
2. 从静默醒来：worker依据已有close_watch/next_wake_turn确定真正进入首次审议，发送review_wake；宿主安装barrier及请求取消当前动作，返回确认；worker收到确认后才调用模型。
3. 判断没有问题：wait发review_silent，宿主释放，按模型选择的after_turns等待下次唤醒。
4. 首次纠偏：沿原intervene消息路径送达后finally释放。保持同会话，close_watch为真；本次内部模型调用、工具读取和后续修复跟进不重复握手/阻断。再次纠偏沿原可恢复中断邮箱送达。
5. 局部恢复：模型wait使close_watch为假；下一次唤醒再次先等待。根完成已有独立等待不叠加新barrier。

没有增加模型工具或分类字段。父进程不再另维护focused语义副本，只有worker的原有跟进状态决定是否握手。被动视图、原始证据、私有文件、持续history、容量机制、模型配置保持不变。

## 异常及能力边界

宿主安装失败回拒绝确认，监察不开始模型调用。模型/送达失败、退出或进程死亡释放等待；300秒工程看门狗记录wake_review_timeout并设置监察stop_event，显式终止本次监察，而不是伪装正常静默。宿主barrier自身也保留最终超时保护。

确认表示屏障已安装及取消请求已发出，不保证任意正在运行的系统调用已经物理停止或副作用回滚。任务下一模型调用会等待，尚未执行旧工具被取消。无需等模型输出判断才停止，但真实工具取消延迟、模型决策质量和局部跟进及时性仍需真实验证。

## 变更及验证

- runtime.py：review唤醒握手、初始化barrier、静默释放、异常处理；删除intervene流触发及父进程重复语义状态。
- provider.py：撤销上一版流式纠偏触发，恢复原协议处理；不是修复R2的call_id异常。
- agent.py/correction_barrier.py：角色说明与当前调度一致。
- vendor/liveplan_blocking.py及NOTICE：撤销不再参与调度的局部提取；PMA BM25、LivePlan格式化原有模块未动。
- test_monitor_correction_schedule.py：改为验证在调用首个模型前等待宿主确认、无纠偏静默释放、首次纠偏释放、后续并发、再次唤醒阻断、异常/用户停止释放；其他真实GA循环fixture保留。

针对检查72项通过；完整监察/运行时/中断回归293项通过。未改真实配置或重用旧run-id。下一真实实验仍须新manifest及确认；现有call_id服务兼容异常仍是独立未解决项。
