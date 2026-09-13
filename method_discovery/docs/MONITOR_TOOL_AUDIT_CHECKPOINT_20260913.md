# 监察工具审计与后台状态 checkpoint

## 范围与裁决

用户要求保存本轮讨论与工具审计；本轮只读审计并记录，不修改工具、提示词或调度，不启动新实验。
当前工具不是越少越好，也不要求所有工具处于相同抽象层：材料调查应通用，运行控制应有可靠专用接口。
PMA 固定维护—更新—判断的流程值得参考，但其整体效果不构成“限制模型自由本身有效”的因果证据。

## 原始人工证据定位

- 会话：`C:/Users/hsy/.codex/sessions/2026/08/15/rollout-2026-08-15T17-17-42-01a004b6-782e-75e0-8664-b43eef4c1586.jsonl`。
- 人工 Fyne 时段：UTC 2026-09-06 17:00–18:20（北京时间 9 月 7 日 01:00–02:20），覆盖准备、运行和收尾，不是纯监察成本窗口。
- 顶层调用 133 / 返回 133，call_id 无缺配对；exec 98、wait 2、sleep 33。exec 文本中包含 exec_command 114、write_stdin 5、apply_patch 29 次，不能与顶层相加计算调用数。
- 含原始命令、补丁与返回；工具当时截断的输出仍有截断。没有由此证明最早 FBR 记录同样完整。
- 行号锚点：107062 最新日志尾部与生产 diff；107276 测试具体行；107289 测试断言及最新日志；107254 指出非空颜色断言可被默认实现通过。
- 人工实际使用通用 shell、文件写入、进程输出查询、等待。先看最新进展，再精读相关测试、实现与 diff；纠偏后检查实际反应。并非永远即时，也不是 token 级订阅。
- 人工实时记录：`PHASE1_MANUAL_FYNE_R1_LIVE_20260907.md`；结果：`PHASE1_MANUAL_FYNE_R1_RESULT_20260907.md`。

## 自动证据与限制

R2 根目录：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-literature-adaptation-20260913-r2/fyn-2.2.0-roadmap__KntCVxo/agent/monitor/monitor_private/audit/`。
完整 progress.jsonl 的 tool_started：file_read 35、code_run 27、wait 4、intervene 4、file_write 1。review_context/file_patch 为零。
provider_history.json 仅保留 62 个工具调用（完整进度为 71），不得据保留 history 声称完整行为覆盖。
保留结果中，一次 file_read(start=253,count=240) 实际返回 38 行原始事件，序列化结果约 124693 字符，不是 token 数。
保留调用显示多次大段原始事件加 synopsis 加总体 diff；有两次直接运行 go test ./data/binding（一次编译失败，一次成功），但未见与人工相当的定点读取新增测试断言。后者是保留片段的发现，不是全轨迹绝对不存在。
R2 因服务协议异常终止，无完整效果结论；与人工时长、版本和先验不一致，只用于行为诊断。

## 逐工具判断

| 工具 | 判断 | 证据及后续方向 |
|---|---|---|
| file_read | 保留，优先改善 | JSONL 行数不约束信息量；尾部读取不应绑在独立 live_awareness 机制开关。考虑可续读的输出预算，不剥夺完整证据访问。 |
| file_write | 保留 | 支持自然笔记；本轮只调用一次，不能直接判定工具无效或必须每轮强制写。 |
| file_patch | 保留 | 精确局部修改与整文件写入互补，未使用不等于不必要。 |
| code_run | 保留，考虑增量输出 | 当前等待脚本退出才返回，头尾截断且执行器不自动归档完整 stdout；与人工可查询运行中会话有能力差距。未证明本轮慢由长脚本造成。 |
| review_context | 优先评估是否值得保留/重设计 | 本轮零调用。query 只检索任务/私人笔记，不检索行为；steps 是事件条目不是完整轮；组合多个截断视图，语义不够直观。不能因引用作者代码就默认有效。 |
| intervene | 保留 | 工程保障用户式输入及中断，不让模型每次实现队列。 |
| wait | 保留，考虑节奏表达 | 当前只按任务轮数等待，人工还按时间等待；不是据此恢复逐轮强制审批。 |
| allow_complete | 保留 | 明确根完成控制；无在线 checker。 |

当前本轮配置可见上述 8 工具。read_with_sources、feedback_focus、inquiry 未启用。
实现入口：monitor_agent_core/agent.py、workspace.py、process_runner.py、decision_context.py。
建议优先改善读取/续读/最新信息获取，再评估组合检索；不立即增加测试专用工具或强制每轮填表。模型调查重点、记忆维护、模型响应延迟和调度需分别判断，不能全部归咎于工具。

## 后台实际状态

用户随后要求查看并监视后台。检查 `method_discovery/artifacts/wake_control_20260913/background_status.jsonl` 与 connectivity.log：
- run-id：clean-monitor-fyn-2.2.0-roadmap-wake-control-20260913-r1。
- stopped_before_task / connectivity_check_failed / returncode=1；没有 runner_started。
- task Claude Opus4.8 隔离工具往返通过，约 6.223 秒。
- monitor GPT-5.6-sol high 流式预检约 105.853 秒后返回 ProviderError / invalid_prompt，服务称提示被策略标记；没有证据确定是探针内容、模型还是中转原因。
- 包装进程 PID 18264 已不存在；docker ps 无运行容器。当前没有任务可持续监察。
- 因真实任务未启动，无法判断本轮 wake-control 调度改动的行为效果；不是跑题失败或方法失效。
- 不擅自修改提示以绕过服务拒绝、不自动重跑或复用旧 run-id；恢复/重启另行明确。
