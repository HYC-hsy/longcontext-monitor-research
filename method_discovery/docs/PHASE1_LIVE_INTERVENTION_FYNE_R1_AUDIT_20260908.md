# 即时干预 Fyne R1：控制时序与判断依据审计

本轮只审计、执行无 API 的诊断，不修改执行代码、不启动真实任务。仍属于五阶段路线的阶段1，不接受候选或进入正式实验。

## 审计对象与结论

run：clean-monitor-fyn-2.2.0-roadmap-phase1-live-intervention-20260908-r1；trial J3ab7G4。123轮后主动停止，无完整效果结论。产物根 P：
`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-phase1-live-intervention-20260908-r1/fyn-2.2.0-roadmap__J3ab7G4/agent/`。

主结论不是单纯“high慢”：普通即时发送已工作；普通纠偏与完成等待分离造成确定性控制延迟；模型同时存在调查认识过时、未经验证的因果断言和主要靠生产代码审查的不足。几类问题必须分别判别。

## 1. 已确认的控制缺口：两个收件通道没有接通

UTC时间线（research_events、progress、runtime_receipts联合定位）：

|时间|实际发生|
|---|---|
|07:47:52|普通review c6f22开始，completion=False，启动游标212|
|07:49:27.160|任务114轮完成提议，归档cursor227；request_completion注册pending并开始300秒等待|
|07:51:16附近|同一普通review主动读取到完成消息，模型语义上已经知道任务声称结束|
|07:52:37.836附近|该review发出普通intervention序号2，内容明确不应完成；进入任务中断邮箱，但没有唤醒completion的pending|
|07:54:06.07附近|普通review最终wait后，worker才处理已排队的completion命令|
|07:54:27.172|任务completion超时CONTINUE/TIMEOUT；循环恢复后消费普通纠偏，115轮有明确采纳|
|07:54:41.81附近|新completion review给出continue消息；pending已删除，回执archived_late_or_unmatched|

代码链：
- `monitor_agent_core/runtime.py:76–111`：send_now使用本次review开始时的completion布尔值；调查过程中读到完成消息不会更新这个执行状态。
- `runtime.py:148`：worker在整个monitor.review返回后才读取命令队列；coalesce优先completion不能抢占已在进行的review。
- `runtime.py:241`：普通intervention只调用任务中断接口；`249`的pending.put只对completion类消息执行。
- `runtime.py:269`：完成等待只等自己队列；不是等待“完成回复或新的用户式纠偏”。
- `agent_loop.py:156`：同步完成回调尚未返回，无法走到下一轮的consume_resumable_interruption（62行）。取消模型流/工具不能打断这个queue.get等待。

这不是消息永久丢失：第二条普通纠偏115轮被采纳。迟到的正式completion消息未交给任务，且内容大幅重复第二条。
它也是候选设计文档已经明确留下的限制，本次证实其实际影响；不能事后称此前未知或声称之前95项测试覆盖了这一交叉时序。

无API诊断：用真实MonitorRuntime.request_completion/_pump_outputs，内存队列与fake存档/中断回调复现；将300秒缩为0.2秒，不修改源码。输出ordinary_handed_off=True、completion_still_waiting=True，最终reason=timeout；迟到回复archived_late_or_unmatched。证明不依赖模型速度。
现有两个测试文件共12项仍通过；test_worker_submits_while_same_review_is_still_running只分别验证普通或一开始就在completion模式，没有覆盖普通review期间新completion到达。

## 2. 确认存在无充分依据的强因果断言，不等于所有提醒都错

provider_history.json条目40/44读取sprintf和binditems，46发第二条纠偏：声称普通source.Set会同步回调DataChanged，因此是self-deadlock，并要求移除/重构锁。53的正式completion又重复。

但是此前读到的binding.go已经显示base.trigger调用queueItem(listen.DataChanged)，不是直接调用；该内容后来位于压缩归档`monitor_private/audit/history/a2e532299c244e4d8734d0388adad4f5.json`的[10].content[2].content。Windows读取该长路径须使用长路径前缀；文件实际存在，不是归档丢失。
本次没有看到监察者检查queue.go或运行setter死锁的控制实验。故“普通绑定同步自死锁”证据不足；不能仅凭queueItem名称判定任何场景绝无死锁，但更不能把怀疑当已证实原因指示删锁。

任务115轮把这条解释写成CRITICAL ISSUES，119/122轮按其删锁；122轮代码注释直接写“source bindings will call DataChanged which needs RLock”。这是建议改变任务因果解释的实际证据，不只停留于对话。
此外121轮新Get在RLock下写lastError，并在开头优先返回lastError；尚未观察完整修复和并发测试，不能声明最终缺陷或全部由监察造成，但说明采纳建议不等于正确恢复。

人工参考对照：先读PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md，再核对Fk7n6ZM的实际011.txt：要求先区分fmt.Sscanf契约、测试同步与异步通知，再决定是否修改队列/锁。014.txt要求让测试实际观察SetMainMenu而不是指针/数量。这里的差距是验证自己的因果依据，不是工具权限不足。

## 3. 调查过程中认识会过时；已有history不是没有记忆

初始化352.70秒。最早git status无diff，但之后任务并发改动；模型没有在初始化结束前重新检查增量，working.md仍写“only explored so far”。它能写七项目标，能在后续修订和追踪部分采纳，因此不能说没有task model或没有持续history。

首次干预：07:43:23发送后，07:44:39 file_patch、07:45:05 wait；这约102秒没有读取新的任务行为。随后下一review才读取增量。新的非终结intervene能力已经实现，但模型实际选择先写笔记再wait；尚未形成“发出后立即看理解/意图”的自然连续控制。

wait(1)也不等于从调用时再等1轮：当前worker计算的是review启动时task_turn+1；审议期间任务已推进，因此通常直接处理最新backlog。它没有造成20轮强制静默，但唤醒参数的实际参照点与直觉不一致，应纳入生命周期设计而非调小数字。

读取量：第二次review file_read原始事件从第1行count300，history约113k→640k字符；后续改为119、173、213行等增量范围。原始行含工具和next_prompt等冗余，行数有界不意味着token低。不能把所有重读都归因记忆压缩，也不能把每次请求时间解释成high纯思考时间。

## 4. 测试关注已有部分作用，但尚不是人工式证据生成监督

正确证据：两条普通纠偏指出Hyperlink双调用、错误Toolbar.SetIcon API、空菜单Refresh等；70轮明确接收第一条，74等轮实际修改；115轮接收第二条。第二条正确警告go test | grep | head不足以证明完整成功。

本轮通过file_write/file_patch修改_test.go只发现68轮给dummyApp补Metadata以满足编译接口；不是新功能行为覆盖。code_run是否另行生成全部测试没有做全文件系统终态重建，故不能宣称绝对没有任何测试。监察者没有细读已有具体断言建立行为验证，而主要读生产diff/调用宽测试；到第二条才明确要求focused behavioral tests。
任务114轮把六组修复当成全任务叙述，是范围缩窄信号，不是“少报一项数字就证明漏实现”：初期65轮曾声称全部7项目标，目标1/2已有工作。监察者应据具体要求与证据判断，而不能依赖6/7计数。

## 应保留与下一步边界

保留：单一同会话、通用工具、两层公开证据、并发任务执行、即时非终结intervene、外部自然笔记及回查、局部采纳和根范围检查意识。不存在必须推翻整个底座的证据。

最确定的工程方向：将任务运行/等待完成视为同一受控任务生命周期；真实纠偏到达应让当前完成提议失效并恢复任务，不等待重复LLM完成审查；过期completion命令不应作为新审议继续处理。需处理匹配、消费和并发竞态，不靠自然语言分类或自动批准。具体实现尚未授权。

方法方向仍独立：让监察者的判断理由可受挑战、先验证会改变修改方向的因果前提；减少先写长记录后再重看造成的认识滞后。不能靠每个领域再补提示词，也不能仅增加调用或固定更频繁提醒就宣称解决。

本轮未证明medium足够或high必要；成功请求平均41.91秒包含网络/服务/生成，一个连接失败重试122.7秒，初始化还运行全套测试。medium比较应保持同一任务/机制，不把换档掩盖工程缺口。
