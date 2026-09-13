# PMA two-phase R1 live

用户明确批准启动；commit8bed014；源码/harness摘要预检匹配。
run: clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r1
trial: fyn-2.2.0-roadmap__oT4kbYf
runner session: 27268
manifest: method_discovery/artifacts/pma_two_phase_20260913/fyne_r1_manifest.json
同Fyne2.2、两方独立Claude Opus4.8、500turn/10000秒、无网络Unix推理隔离，native仅事后。
18:42监察初始化，18:43确认任务Agent已执行、下一次wake已开始，无人工干预。
比较原PMA维护R1；输入映射和第二阶段一起变化，不能单独归因第二阶段。

## 结束与有效性边界

19:31 主动停止，非模型服务失败、非预算超时、非任务成功。agent_execution 为
10:41:02.273800Z—11:31:37.882462Z，50分35.61秒；最后产生第90轮。
发现连续中断验证的调度阻塞后，向本题容器已核实的监察子进程166和任务进程153发送TERM。
wrapper125/child143/round_end_seen=false 是本次主动停止的后果，不另计为上游故障。
未执行native verifier，无最终分数，不可与旧R1的2/7或无PMA版本4/7直接比较。
失败工作区快照已保存2793文件、110177368字节；本题容器已由runner清理。

## 实际观察

- 完整作者两阶段成功执行27次：17次no_intervention、10次reminder，未见已完成cycle报错。
  第28次唤醒未完成即人工停止，不能当作no-op。
- 原监察者保留独立调查、判断和干预能力，共发出5次干预；PMA提醒不会自动变成任务输入。
- 明确局部正例：第45轮任务把NewAllStrings误实现为字符串允许列表。
  第二阶段指出应组合多个validator；监察者明确引用此线索、查证并第四次纠偏；
  后续删除string.go，新增all.go的validator组合实现。证明链路可促成纠偏，
  但没有无第二阶段的同步反事实，不能断言原监察者必然漏检，也没有最终评分确认总体提升。
- 提醒并非全有价值：出现Metadata旧错误已经修复却再次提醒；监察者识别为旧状态。
  一部分线索只是重述patch失败反馈或编译修复信息。
- 旧认知风险仍可见：多次以文件检查声称七目标功能全部完成，把编译问题当作唯一尾项。
  尚无最终测试支持这一全局结论；本轮没有进入最终allow_complete，不能称已错误放行。

## 停止依据：观察调度干扰证据生成

output.txt的Stopped出现在62、65、68、71、75、82、87、88、89轮。
其中75轮批量修改被中断，后续改为逐段file_patch；82轮go build被中断。
87–89轮连续尝试编译均被中断，任务89/90轮明确表示build被user/system终止。
runtime_receipts对应：review_silent(from_turn=86,next_wake_turn=87)，之后
87→88、88→89、89→90，每次review_wake均cancellation_requested。
agentmain.begin_monitor_correction会设置工具停止信号并取消当前响应。
事实支持：为了尽快观察编译结果而逐轮唤醒，与“醒来即取消”相撞，反而阻止获取结果。
不据此推导必须废除混合同步控制；应先审计唤醒、取消、恢复和观察结果之间的接线。
本轮未在运行中修改代码或人工纠偏；停止前全部任务干预来自监察者。

## 成本

PMA完成的27个cycle累计1411.94秒（23分31.94秒），是调用墙钟累计，
不能直接解释为相对基线增加了同等任务wall time。

|调用组|已归档调用|input|output|cache read|cache creation|
|---|---:|---:|---:|---:|---:|
|PMA维护|27|356739|31652|1451|20554|
|PMA比较|27|361166|33139|1517|18679|
|主监察审议|77|230053|52430|834369|2838198|
|任务Agent|90|126375|35128|1612583|152455|

以上四组互斥；usage已完成归档口径不包含停止时未结算请求，不代表供应商最终账单。
美元成本未获得，不根据日卡额度倒推。原始任务用量见research_events.jsonl。

## 产物与下一步

产物根目录：long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/
clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r1/fyn-2.2.0-roadmap__oT4kbYf/。
关键证据：agent/output.txt、agent/monitor/runtime_receipts.jsonl、
agent/monitor/monitor_private/audit/dialogue.jsonl和provider_usage.jsonl、
agent/failure_workspace/、result.json。

下一阶段先审计调度阻塞与PMA线索作用，暂不添加新机制、不晋级候选、不自动重跑。
