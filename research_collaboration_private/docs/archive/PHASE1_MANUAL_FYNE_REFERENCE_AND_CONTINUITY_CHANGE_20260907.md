# 人工监察参考案例与认识续接候选

## 授权与当前定位

2026-09-07 用户认可人工 Fyne 复盘后，授权实现：基础观察/回执修复，再尝试最小认识续接机制；真实启动前停止。
这是五阶段路线下由阶段1诊断产生的候选实现，不表示原因已完全锁定或方法已接受。研究问题仍为表示遗漏与错误闭合。
本文件是以后回看本次人工监察的入口，不能用它替代原始轨迹。

## 永久参考入口

- 实时决策：`PHASE1_MANUAL_FYNE_R1_LIVE_20260907.md`。
- 完整结果、配置、用量及比较限制：`PHASE1_MANUAL_FYNE_R1_RESULT_20260907.md`。
- 自动 r6 差距：`PHASE1_R6_MONITOR_CAPABILITY_AUDIT_20260907.md`。
- 人工入口实现：`PHASE1_MANUAL_MONITOR_ENTRY_READY_20260907.md`。
- manifest：`method_discovery/artifacts/phase1_20260907/manual_fyne_r1_manifest.json`。

原始产物根目录 P：
`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-phase1-manual-20260907-r1/fyn-2.2.0-roadmap__Fk7n6ZM/`。

- `P/agent/output.txt`：任务公开说明、工具参数及结果；按 turn 与下表关键字定位。
- `P/agent/manual_completion/interventions/archive/001.txt` 至 `016.txt`：人工实际输入，不是事后重写示范。
- `P/agent/manual_completion/interventions/receipts.jsonl`：投递记录，不能代替行为采纳证据。
- `P/agent/research_events.jsonl`：运行控制、终止与调用用量。
- `P/result.json`、`P/verifier/test-stdout.txt`：结束后评价，禁止作为后续同次在线监察输入。

## 以后带着什么问题回看

|片段|原始锚点|实际判断与行为|设计启发及边界|
|---|---|---|---|
|最早纠偏|001；turn26–37；NewAllStrings、SetMainMenu|对照原题 API 与实际菜单更新路径，任务修正|摘要作导航、原代码作依据；消息送达时错误文件已写，不能声称总在写前阻止|
|提醒被误解|007/008；turn119–123之后；0000|合法透明色反例澄清 error 与颜色值的区别|跟踪实际理解，不重复同一句；人工前次措辞也有歧义|
|原因对但恢复错|009；turn140–154；repository、paths-only|认可环境诊断，但阻止删除 URI 能力；恢复正常测试环境|因果解释和恢复动作需分别判断|
|合理调查时静默|011；turn175–193；Sscanf、waitForItems|先区分测试同步与实现问题，允许自主验证；原队列/setter未改|不把失败直接提升为生产缺陷，不把持续关注做成持续打断|
|局部释放与根范围|012/013；turn194–219；Metadata|绑定局部通过后回到默认值与覆盖，阻止无必要根接口扩张|既不无限纠缠，又不丢原要求|
|测试判别力|014；turn232–242；Refresh|原断言 noop 也能过；改为观察实际调用，局部通过后退出|测试是可执行任务解释，不是仅看 PASS|
|有界停止|015/016；turn243–256；HEAD~20、7229e889|准确起始版本复现旧失败后停止追查；最后只修报告|不是所有未知都验证，也不是接受无依据 pre-existing 声明|

人工实际通过 Docker exec 主动 tail 实时 output，通常隔25–40秒，疑点处打开测试/代码/diff；不是逐 token 订阅。
没有直接替任务改代码。一次复杂 shell 引号错误产生巨量无关输出，应作为自身工具使用失误保留。
连续性主要来自同一对话历史与按需回查；运行笔记没有每轮重新读取。不能拿本案例证明非线性记忆优于线性 History。

最终256轮、约60分46秒任务时间、native7/7、1.0；16次普通干预、3次完成继续、1次允许。
人工提前了解旧运行失败，提供了专业解题建议，自身监察 token 未完整计量；仅是诊断性能力参考，不是公平效果/成本对照。

## 本次代码改动

### 步骤1：观察与反馈（独立于记忆候选）

- `monitor_agent_core/agent.py`：code_run 不再在执行前复制全工作区；给出实时 evidence/workspace/private 路径，执行仍在 private 目录。
- file_read 原本即可读取实时挂载，不重写它；code_run 仍为通用本地能力，不宣称硬隔离，不授权任务文件写入。
- code_run 仍在脚本结束时返回输出，没有新增后台任务句柄；提示清楚标注，不能声称长脚本中途持续收到输出。
- `runtime.py`：初始化不再强制先 wait；干预回调成功、失败以及迟到完成回执写入私有反馈，下次审议续入同一 History。读取失败/审议失败不提前消费反馈游标。
- 回执只证明交接层事实；实际理解与行为仍由公开轨迹核验。不增加逐轮审批。

### 步骤2：最小认识续接候选

- 提示模型自主组织 `monitor/working.md`，在认识实质变化时更新，不要求每次醒来填表。
- 持续 History 保留；不会把 wait/intervene 当成语义问题已结束，也未引入 repair ID 或确定性匹配。
- `provider.py` 达到既有压缩阈值时，先由同一模型基于尚未删除的 History 与已有笔记生成自然语言续接，再执行原工具协议完整的历史清理；续接写入 History、working.md 与独立版本归档。
- 整理调用没有工具权限，不能在维护响应里执行干预。失败或空输出时不删除历史，异常向现有 review 故障路径报告。
- 新调用用量记录 `purpose=pre_compaction_continuation`，耗时进 request/progress 记录；预计增加压缩时成本，未证明净降本。
- `model_config.monitor_semantic_continuity=false` 可关闭压缩前整理；自然笔记建议仍在，故它是压缩整理的局部消融，不是整个机制关闭。
- 不保证整个无限长 repair 对话原文永远驻留；近期历史沿用旧保护，超长过程通过可修订认识承接。是否丢关键细节需真实验证。

## 验证与下一门禁

本轮只执行无 API 的真实文件/子进程与 fake-provider/进程回归。检查实时源更新可读、无快照成本、同会话续接、压缩失败保留历史、用量记录、回执反馈及阻塞监察不冻结归档。
首次回归62项通过；最终扩大到77项，全部通过（5.65秒）。命令在 GenericAgent-main 下执行：
`D:\python\envs\ga_bench\python.exe -m pytest tests/test_monitor_agent.py tests/test_monitor_provider.py tests/test_clean_monitor_runtime.py tests/test_monitor_handoff_recovery.py tests/test_monitor_agent_workspace.py tests/test_monitor_live_progress.py tests/test_manual_completion_boundary.py tests/test_research_agent_loop.py -q`。
`git diff --check` 通过，仅有已有文件行尾转换提示。新增验证写入现有 test_monitor_agent、test_clean_monitor_runtime、test_monitor_handoff_recovery。
每个代码步骤均小于600增删行；没有改变任务模型、预算、隐藏信息边界或启动真实分支。

下一真实分支仍需用户单独确认。建议同 Fyne、同任务/监察模型和预算，区别基础修复与认识续接的影响；重点看错误修复扩张、真实采纳、局部释放、根范围保持和重复读取，而不是笔记好看与否。
