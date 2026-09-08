# 完成生命周期 Fyne R1：第二次超时审计

本轮只读取真实日志、检查代码、执行17项无API回归并记录结论；没有修改执行代码、换模型、重跑或读取native评价。

## 审计对象

run：clean-monitor-fyn-2.2.0-roadmap-phase1-completion-lifecycle-20260908-r1；trial f7DBnyo；主动停止于37轮、约18分钟。
产物根P：long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-phase1-completion-lifecycle-20260908-r1/fyn-2.2.0-roadmap__f7DBnyo/agent/。
主要证据：P/research_events.jsonl、monitor/runtime_receipts.jsonl、monitor/task_evidence/public_events.jsonl、monitor_private/audit/progress.jsonl、provider_history.json。

## 1. 修复路径确实工作，未复现上一轮故障

08:23:34.291 UTC任务2轮提出范围确认。08:27:59.241监察普通intervene进入任务邮箱，同一时刻等待结束为CONTINUE/INTERRUPTED；resumed_completion_requests包含旧请求。任务3轮开始实际实施。
之后只有一次新的普通review（08:33:47.048），没有为已失效的范围确认请求再开completion review。日志没有迟到completion重复投递，也没有错误批准。
这支持“真实纠偏解除等待、过期排队请求被跳过”的修复，不支持所有并发竞态都已由单次真实轨迹证明。17项runtime/live-intervention/lifecycle测试复跑通过。

## 2. 第二次300秒几乎全是请求及重试，不是长工具或已发消息被挡

35轮提议：08:34:13.299；超时：08:39:13.311。
将progress中request_started/finished区间裁剪到这300秒，约299.649秒在请求及重试内部；tool_finished耗时对应区间合计0.307秒，其余为调度/日志开销。请求耗时包括网络、服务、生成和重试等待，不能进一步称为纯模型思考。

|时间段（UTC）|实际内容|
|---|---|
|08:34:13–08:34:14|此前普通review的首个请求结束，读取工具返回|
|08:34:14–08:34:38|请求可恢复错误，约24秒|
|08:34:38–08:35:45|重试成功，约67秒，随后短工具读取|
|08:35:45–08:37:48|另一个请求ConnectionError，约123秒|
|08:37:48–08:39:13|重试仍在进行，完成等待先到期|
|08:39:51|该重试最终成功（总122.91秒），模型又调了3个短code_run并继续请求|

没有第二条intervene；无review_failed/retries_exhausted。停止前请求仍可恢复且恢复过，不能描述成“监察者崩溃”。TIMEOUT只证明等待期限耗尽，不能直接判方法认知失败。

## 3. 自动恢复没有给任务新语义信息

runtime.py仍在超时后返回“The completion audit timed out. Continue the task.”，不带新的缺陷或下一步依据。36轮Task Agent再次将TASK FULLY COMPLETED写入checkpoint，列文件、git状态和再编译；37轮再次宣布完成。
这与“没有新的决策依据却让任务继续”一致，不需要推断任务故意不配合。只有一次超时后的重复提议，尚不足以声称已形成必然无限循环。
超时继续原本是避免任务永远冻结的兜底，不能简单删除，也不能靠重复更严厉提醒代替。需要明确：服务仍在重试时等待是否延续、不可恢复时如何结束、以及重试会不会被误当作需要任务修复的语义事件。属于待决策的完成等待/恢复策略，不是当前消息转交代码再次坏掉。

## 4. 真实任务存在错误闭合，但尚不能裁决监察者会怎样纠正

任务33轮执行go build ./... | head和go test -c ./... | head；后者输出多个cannot write test binary ... for multiple packages，工具仍给出管道exit_code=0。且编译测试不等于执行行为测试。34/35轮仍据此报告全部完成。实现报告中的NewStringWithFormat也不同于原任务NewSprintf，须按源码核验而不能只凭报告判最终产物。

第一审议完整history显示：监察者正确恢复七项目标，并主动读取后续原始事件；在08:27:08写working.md时已认为任务应直接开始，51秒后才实际intervene。后续08:31:51的笔记仍写Targets3–7未开始，08:33:46才wait。存在观察时点落后于实时执行的迹象；有持续history，不是每次重新开线程。

第二审议完整history没有保存。provider_history.json只有第一审议17条；源码agent.review仅在finally导出history。主动docker stop可能直接终止进程，无法保证finally运行；实时progress只保存工具名称/id/耗时，不保存参数和结果。因此无法完整重建它第二次读了哪些断言、形成了哪种判断。不应声称它已看清问题但不提醒，或把上一轮的同步死锁误判移植成本轮事实。
这是实际审计/异常恢复能力缺口，而非模型没有记忆：内存history曾到521869字符，但未结束审议在磁盘不可重建。工具和模型参数/结果的增量持久记录应与模型上下文注入分开考虑，不需要额外语义schema或更多prompt。

## 5. 对停止方式及实验结论的修正

我按此前“异常时停止”的约定，在第二次超时后停止了；这保留了控制问题证据，却截断了一个仍在恢复并继续调用工具的监察过程。因此本轮只能评价启动/交付路径与当前延迟，不能作为候选无效、能力退化或最终任务不可能完成的证据。
若后续目标是完整效果验证，需要事先把可恢复接口重试、一次completion等待超时、不可恢复故障和真实严重错误干预区分为不同停止条件；否则反复在同类可恢复状态停止，会一直拿不到方法效果。调整停止门禁需先说明并取得用户认可，不自行增加预算或永不停止。

## 用量与下一步建议

监察progress可得输入483917、输出3228，11成功请求、4可恢复错误尝试；有空usage/未完成调用，不是完整计费。
任务37条provider_usage：input_tokens48223、output_tokens21880、cache_creation_input_tokens57719、cache_read_input_tokens698692。原样分别列字段，不把缓存token和input重复相加宣称总成本；中转实际计费未知。

建议顺序：保留已验证控制修复；补齐未结束审议的增量可审计记录；明确完成等待与可恢复上游异常的处理/停止原则；随后完整真实验证，再评价认知改造。medium对照可以是后续选择，但本轮不能证明换medium就足够，也不能拿high请求慢当作已定位的唯一根因。
