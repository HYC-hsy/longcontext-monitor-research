# 工具优化 T2/T3 完成报告

用户授权连续完成全部已确定工具优化，在真实运行前停止。前一步T1见TOOL_T1_READING_IMPLEMENTATION_20260913.md（9f9150b）。本轮不修改判断策略、系统监察原则、原任务、模型、benchmark、记忆组织或wake/intervene/wait控制语义。

## 实施与文件

T2（4831b5c）：decision_context.py新增明确的latest/forward选择、显式after_cursor、next_read及read_from_start、跳过与剩余条数。include_context=false只返回行为视图，模型可避免重复附带任务/笔记。保留默认latest和原作者BM25/格式化代码；未声称连续模式获得效果提升。agent.py只补充工具schema与工具说明；workspace.py共享写入改为同目录临时文件+fsync+os.replace，失败保留原文件并清理临时文件。精确编辑不增加ID或模糊匹配。

T3：process_runner.py将旧同步执行替换为AnalysisSessions；agent.py保持一个code_run工具，通过code启动、session_id读取增量、cancel终止该命令。短命令通常直接完成，默认等待1秒，最多等待5秒后返回；总执行timeout仍默认60秒、最大300秒。每次最多读12000原始输出字节，UTF-8字符边界可续接，完整输出与提交脚本位于audit/commands/<session>/。不再只保留头尾、丢失中间输出。stdout/stderr合流，与旧工具一致。

runtime.py仅一处接线：将已有实验stop_event传入MonitorAgent，停止实验时分析命令也停止。不会以分析session代替task控制信号。原来的每次初始化/唤醒暂停、首次纠偏后恢复、局部跟进并行保持不变。HOST_CONTRACT补充独立宿主的工具生命周期说明。

测试文件：test_monitor_decision_context、test_monitor_atomic_write、test_monitor_analysis_sessions、test_monitor_agent；7份worker替身测试同步接受stop_event参数并在直接调用worker时提供该事件。未降低原有控制断言，未为旧测试恢复生产兼容层。

## 验证与失败处理

- T2+原子写入针对性测试：30 passed。
- T3针对性：22 passed，1个Linux专属测试在Windows跳过。
- 初轮累计11失败：worker测试替身不接受新stop_event，或手造worker配置没有该事件；不是实际生产配置缺失。补齐后发现另2个手造配置仍缺事件，再补齐。
- 最终累计 `tests/test_monitor*.py`，排除退役test_monitor_semantic_files.py：293 passed，1 skipped，16.94秒。包含provider协议、源码独立性、打包、完成握手、纠偏调度与历史续接回归。
- 无网络python:3.12-slim一次性容器，直接装载本地process_runner：实际shell后台子进程、增量输出、取消及进程组清理通过；另一个短Python命令通过。没有API、没有启动benchmark。
- 增量测试验证Unicode大输出拼接无遗漏、短命令归档、超时/取消/宿主停止、会话跨review保留、未知会话错误与原子替换失败不损坏原文件。
- diff --check通过；各代码步骤新增+删除均不足600行。未提交既有.gitignore变动、密钥或运行垃圾。

## 没有改的工具及边界

- intervene、wait、allow_complete接口不改；未引入按时间唤醒新策略、测试完成硬门槛或证据必填表单。
- file_write/file_patch仅共享原子写入；小段编辑仍由模型自己选择，未强制笔记格式。
- code_run会话能跨review，不能跨进程恢复；历史中旧句柄返回明确错误，已归档output仍可file_read。脚本缓冲未flush的输出无法凭空提前看到；Python使用-u。
- Linux进程组清理覆盖本次实验平台。Windows父进程已退出后故意分离的后代不承诺硬隔离；通用code_run本就不是安全沙箱。
- review_context仍是有界预览，完整证据通过原始文件访问。latest明确报告跳过，forward可逐页覆盖；没有第三层语义索引。
- 代码通过不证明方法更好；默认预算、工具调用是否自然、会话能力是否实际有用及判断退化需真实运行裁决。

## 下一次启动

尚未启动真实任务。旧manifest绑定旧source hash，不能直接复用。下一次应新run-id、重新生成并校验manifest，保持Fyne2.2与任务/监察Claude配置、500turn/10000秒、无网络隔离不变；用户确认后才启动。
判别目标仅工具可用性、连续证据覆盖、调用绕路与输出成本、调度无回归。后续策略问题另议，不把本轮工具改造当作已经修复错误闭合。
