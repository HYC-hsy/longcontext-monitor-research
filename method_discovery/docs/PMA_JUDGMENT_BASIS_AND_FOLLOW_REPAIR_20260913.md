# PMA判断依据适配与跟进等待修复

## 授权、边界与证据

用户批准最小实现：保留PMA两阶段流程，调整维护/判断重心，并修复两项工程问题。
父版本24083b8（运行实现8bed014）。本次未启动真实任务或调用模型API。
原始依据为PMA_TWO_PHASE_R1_LIVE_20260913.md对应oT4kbYf轨迹：
87–89轮wait(1)后编译被取消；dialogue第414行工具结果含直接echo的全目标完成，
下一PMA维护输入收录该输出却未收录产生它的命令。
人工经验重新读取Fk7n6ZM的011和014干预：检验测试预期与判别力，而不是把PASS当证明。

## 改动

1. agent.py、runtime.py：现有wait增加mode=follow|patrol，默认follow。
   follow结束本次模型审议并让任务继续，保留并发跟进；达到after_turns再次观察但不取消。
   patrol明确离开局部调查，下一次醒来仍按原裁决先停止再审议。
   两者都释放已有屏障；intervene仍即时中断并恢复；完成待答时仍禁止wait死等。
   调度尊重follow的after_turns，不以close_watch绕过轮数。没有新增暂停工具。
   公开意图仍可触发跟进观察；没有把全部唤醒改成只看工具完成之后。
   patrol本身仍可能取消当前工具，这是保留的用户裁决，不宣称所有取消已消失。

2. pma_observation.py：以review_id+tool_id连接监察工具调用和结果，附各自原始行号。
   命令与输出各保留3000字符窗口，长内容显式截断、原档仍可读取。
   不匹配时显式unknown，不根据文本相似性猜测，不让模型手填ID。
   仍只取最近4个检查结果；总输入可能增加最多约12k字符，不宣称免费。
   该修复防止来源丢失，不保证模型不会误信echo；语义可信度仍需模型判断。

3. 新pma_judgment.py、pma_memory.py：适配层调整两阶段system与status工具说明。
   维护原要求、判断依据及重要未排除解释；比较近期行为是否支持或挑战判断。
   不强制schema、不要求每条事实生成反例、不要求验证所有UNKNOWN。
   替换原第二阶段“与记忆一致即可不提醒”的冲突措辞，不改变输出协议。
   仍执行作者MemoryAgent.process、原bank操作、检索、更新后比较；vendor文件零改动。
   这是PMA流程上的判断依据适配，不是原提示原样复现，也不是新增第三阶段。

## 验证

ga_bench环境pytest以下9组：test_monitor_follow_wait、test_monitor_correction_schedule、
test_monitor_pma_memory、test_monitor_pma_two_phase、test_monitor_agent、
test_monitor_core_independence、test_monitor_completion_interrupt_lifecycle、
test_monitor_host_contract、test_monitor_decision_context。
首轮32通过、1失败：旧history测试精确比较wait旧字段；更新其契约，不恢复旧取消语义。
扩大回归73通过（12.37秒）；清理原提示冲突措辞后，一项旧提示精确断言失败，
改为核对适配后完整提示；最终73通过（11.08秒）。新增测试使用真实子进程等待输入，3次跟进均不取消，
随后完成输出，并验证patrol重新安装屏障。该测试使用实际worker、模拟模型与宿主取消，
不是完整Docker/GA真实实验。证据测试覆盖跨review重复ID与缺失匹配；PMA调用仍通过作者process。
本阶段代码总改动小于600行，分为控制、来源/提示、回归验证步骤。

## 尚待真实验证

模型会否正确选择follow/patrol；判断依据维护是否减少错误闭合而不造成无限验证；
双阶段开销仍存在，未加其他成本机制。工程与记忆适配同时变化，下一轮不能独立归因。
不晋级候选、不冻结方法；启动前必须生成新run-id和新源码摘要并取得确认。
