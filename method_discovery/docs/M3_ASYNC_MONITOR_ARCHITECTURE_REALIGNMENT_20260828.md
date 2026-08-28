# M3 并发监察架构纠偏

Date: 2026-08-28
Status: implemented and deterministically verified; awaiting complete real-task launch gate

## 裁决

M3-B Fyne 2.2 的 r1/r2 运行暴露了架构偏移：`ga.py` 在每个普通工具边界同步调用
`monitor.review()`，使任务 Agent 必须等待本应静默的监察判断。r2 在第 26 轮任务 Agent
正常完成后，监察 provider 请求从 `2026-08-28T14:27:08.860136+00:00` 起永久阻塞，
整道任务无法进入第 27 轮。线程 Timer 调用 `response.close()` 未能中断真实 SSE 读取。

这两条运行因此是工程无效运行，不能用于裁决 M3-A/M3-B 的方法优劣。

用户重新确认的架构是：任务 Agent 默认持续执行；同一持续监察者并发消费公开事件、
主动检索并维护状态；只有形成真实纠偏时才模拟用户输入，在下一安全可中断点、下一次
任务模型推理前注入。普通 SILENT、监察检查、API 延迟、超时、崩溃或重启均不得阻塞任务。

## 本次实现

- 普通 `post_model_pre_tool` 与 `post_tool_pre_next_llm` 边界只追加到原始归档；任务侧不调用监察模型，也不向模型推送完整 packet。
- 独立监察循环维护自己的归档游标。新事实仅产生无语义内容的唤醒视图（数量、范围和边界类型）；具体意图、工具结果、测试、diff 和历史必须由监察者主动调用工具重建。
- 监察者运行在可由操作系统终止的独立 spawn 进程中；永久阻塞达到 deadline 后终止并从
  外部 checkpoint/归档重建，不再依赖跨线程关闭 socket。
- 只有非空监察消息进入高优先级干预队列；SILENT 不产生输入，也不产生等待。
- 干预在下一次任务模型调用前注入，并保留 source request/turn telemetry 关联。
- 明确的根任务完成提议仍是受控高风险边界，但有有界 fail-open；它不会恢复普通逐轮审批。
- 子进程显式继承同一实验 identity 和 JSONL 事件路径，避免并发化后丢失监察证据。

## 确定性证据

- 永久阻塞 worker：边界发布立即返回，真实 `agent_runner_loop` 仍进入下一轮并完成。
- watchdog：阻塞超过时限后终止并重建 worker，任务侧轮询保持非阻塞。
- 正常干预：监察消息只在形成后进入下一轮任务输入；消费后不会重复注入。
- 意图可见性：任务模型公开 tool intent 后立即发布 `post_model_pre_tool`，无需等待工具结束。
- 主动获取：确定性测试证明具体意图不会出现在首次唤醒提示中，只有监察者自主请求 `read_recent_delta` 后才进入后续审议。
- GenericAgent 全测试：257 passed。
- Harbor/ultralong 相关测试：59 passed。

## 尚未声明

本次只证明调度语义、故障隔离和干预送达的工程性质；尚未运行完整真实任务，因此不能声明：

- 并发监察在 Fyne 2.2 上已恢复 M0/M2-C 能力；
- 实际 provider 卡流时的容器级全部产物已经完整验证；
- M3-B 的 decision-value 机制优于 M3-A；
- 当前事件频率与积压策略已经达到最终成本或延迟最优。

下一次真实启动必须继续使用共同任务 Fyne 2.2，并在启动门禁中显式检查：任务 Agent 是否在
监察调用期间继续产生事件、干预延迟、队列积压、worker 重启、完成边界时延，以及既有纠偏
能力是否退化。
