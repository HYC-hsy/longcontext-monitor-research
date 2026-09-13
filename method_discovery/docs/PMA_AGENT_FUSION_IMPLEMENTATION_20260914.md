# PMA 与自主监察内部融合

## 范围与回退

用户批准先融合再按真实弊端优化。本轮不启动 API 或真实任务。
旧版本标签 `pre-pma-agent-fusion-20260914` 指向 f923736；原工作区无本轮前遗留已跟踪代码差异，仅用户 .gitignore 修改未触碰。
服务于可修订任务状态和持续纠偏，不改变研究问题、无 checker 或评价协议。

## 实际接线

`MonitorAgent.review -> FusedPMA.review -> author MemoryAgent.process`。
作者 process 调用两次 transport，每次内部用已有 run_review 工具循环执行该阶段。
第一阶段：原题+最近8轮+bank，自主调查、作者 bank 操作、明确结束维护。
第二阶段：作者重新构造更新后的 bank 输入，自主调查、可原地调用同一 bank 操作修订，再判断。
context_for_action 由作者解析器解析后直接进入现有 intervene 控制；提交后同一阶段继续观察。
no_intervention 不代表完成，模型用 wait 选择 follow/patrol，或对有效根提议 allow_complete。
没有第三次独立主监察 review；两阶段同一 provider History，不清空再恢复。

## 复用边界（不可宣称原样复现）

原样调用 vendor MemoryAgent.process、_build_phase1_prompt、_build_phase2_prompt、
_format_memory_bank、_execute_tool_calls、_parse_phase2_response、BANK_TOOLS 和 UniversalMemory。
vendor 源码未修改。旧 JudgmentMemoryAgent 提示重写不在新运行路径。
本地必要适配：多轮工具调用、维护结束文本标记、直接投递、持续控制、同会话和失败传播。
作者 process 的 returned result.operations 不包含已经即时执行的操作；完整操作另有 pma_bank_operation 审计。
作者返回的 no_intervention 占位不代表全周期无干预；实际消息以 pma_direct_intervention/投递回执为准。

## 认识载体

原题文件仍权威。bank 是主要持久认识；局部调查在持续 History；原始事件与工具输出外部归档。
不再初始化独立 task_model，旧 monitor_task_model=true 明确失败，避免旧 manifest 误跑。
不强制建立 working.md；概览改指向 bank。通用私有文件工具保留，模型可建辅助材料。
压缩仍采用已有协议完整的历史整理，使用 bank 作为既有认识，续接进入 History 和审计，不再自动另写 working.md。
不再将最近4个监察回执和上次纠偏额外拼进 PMA 输入；同会话保留实际调查并允许原始检索。
最近8轮时间与来源映射仍是本地适配，非作者原始终端字节等价。

## 控制和工程边界

维护阶段没有任务控制工具；结束维护后进入判断阶段。模型判断自由，不强制逐目标检查。
判断阶段没有额外 intervene 工具：作者 context_for_action 格式直接发送，通过现有 dispatch 复用去重、回执、强制中断和恢复。
wait/follow/patrol、completion 世代检查沿用现有控制。首次初始化/巡逻唤醒暂停、纠偏后并行未改。
两阶段共享现有 max_review_turns 调用预算，不各自无限扩张；每阶段 usage 标记独立。
bank 操作即时执行并返回作者操作结果；失败返回错误让模型修订，不把删除未知 ID 当成功。
模型/存储故障不转成静默；作者 process 内部捕获的异常由 adapter 再抛出。
之前成功提交的记忆在后续模型故障时保留，不假装整个 review 原子回滚。

## 验证

主要套件：99 passed, 19 skipped（4.79秒）。跳过是旧三段式/独立 task_model 候选的历史契约，明确不计通过。
新增11项覆盖：阶段内读工具、先维护后判断、作者记忆即时执行、第二阶段修订与下一次唤醒、直接投递后持续观察、阶段控制权限、两个阶段异常、共享预算、旧配置拒绝、真实 provider 序列化/回执/用量、根完成与任务隔离、概览不再要求重复笔记。
作者源码身份、近期8轮映射、原始来源测试仍运行；并非以跳过方式消除这些保障。
此前基础77项通过亦包含一般 review、follow、完成中断生命周期、provider 和核心独立性。
测试是确定性模型响应/工程验证，不代表模型会有效使用流程或提高成绩。
补充控制调度、宿主契约、工作区、交接恢复与进度套件：30 passed（7.18秒）。总计本轮两个最终套件129通过、19历史测试跳过；非全仓测试通过声明。

## 下一门禁

使用新的 run-id 和重新生成的 manifest；prepare_pma_memory_run 已更新候选说明并关闭旧 task_model。
正式启动须用户确认。建议保持 Fyne、双方 Opus4.8、500轮/10000秒及无网络隔离；记录两个阶段的调查内容、bank更新、干预/采纳和费用，与R6作发现性比较。
不能假设作者固定 bank 格式已适合自主监察；后续仅依据真实限制再演化。
