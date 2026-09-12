# 文献机制迁移 Fyne R1：真实适配诊断

## 本轮范围与终止

用户批准本条真实启动，重点判断改动是否适配、有效或多余，不要求完整跑分。运行配置来自 `artifacts/literature_transfer_20260913/fyne_r1_ready_manifest.json`，实现版本 `3c80e13`；Fyne 2.2 / Opus4.8 / GPT-5.6-sol high，500轮、10000秒，两个新候选开启，PMA与live-awareness关闭。源码/镜像预检通过，隔离未变。未修改运行中策略、未追加人工纠偏。

运行约北京时间02:17至02:48（UTC 2026-09-12 18:17至18:48）；最后task turn65，公开cursor117，提出完成但未获批准。由于监察请求反复协议失败提前停止，**无最终native评分，不算完整成功/失败任务分数**。

runner PID3304及其子进程已定向终止；本条main容器b1b8158d425f、gateway922377a065e7和本条OTel ce317546caa4已停止但未删除；两个原PMA gateway未动。完整工作区仍在停止的main容器，关键三个公开源文件另行docker cp保存；日志绑定宿主保留。没有自动重跑。

## 适配与机制判断

|检查项|实际观察|能支持的判断|
|---|---|---|
|新工具可见性|初始化系统提示与工具目录均包含review_context/task_control|开关不是漏转发；模型确实可用|
|决策视图|4次工具调用均返回成功，steps依次8/12/16/20|真实接线通；尚不能证明独立行为增益|
|信息负担|context字段字符数47360/109072/112300/143191；三次连续扩大窗口，随后又读原题与原始日志|没有形成“小而决策相关”的稳定使用方式；存在重复输入风险|
|检索边界|query只对private Markdown做BM25；原题、working和近期事件整体拼接；working可能再作为检索命中重复出现|这不是对整个任务证据的query-conditioned检索，不能把PMA检索复用称为完整记忆机制实现|
|纠偏后视图|4次均未传after_correction|新建的纠偏后观察能力没有在本轮被实际使用|
|混合暂停|模型task_control调用0，9次intervene；后台wait产生的resume是释放兜底，不是模型主动暂停|未验证暂停行为效果，也不能据零使用判定机制必然无用|
|旧监察能力|117次file_read、4次code_run、3次file_write、14次wait；实际读实现和测试、指出假完成|旧能力没有完全断，但不能声称无退化；无同配置对照|

### 正向行为与未解决问题

前期纠偏指出ToolbarAction.SetIcon只赋值、Menu.Refresh空壳、接口签名与构建缺失。后续任务公开行为修正了Entry字段、Toolbar构造、testApp.Metadata以及SetSystemTrayIcon参数等；这构成提醒后行为响应，不证明最终质量或新组件独立贡献。

高价值反例：原题Target3第93行明确要求NewSprintf的Set反向解析并写回源。监察者多次提醒，但task55又公开决定按测试要求把Set改回no-op，task65仍称read-only binding已完成。停止时保存的sprintf.go:110-113确实只return nil。json.go:111-126也确认Font/Icon仍不消费JSON资源而只取default。监察者的continuation note明确知道这些未完成，说明不是完全没记住；关键缺口是认识没有及时转成针对再次偏移的行动。

监察者也可能有判断不准确之处：仅凭Go JSON struct tag大小写不能单独断言输入不兼容；它对default/current-theme fallback的措辞需进一步核对，不能把每条提醒当正确oracle。本文仅用题干明确的Set以及资源未加载两项作为核实锚点。

## 工程阻塞：协议一致性校验

完成边界期间，progress记录至少4个`response_text_contract`事件：delta_characters=1、final_characters=0、mismatch=true，最终output包含reasoning/function_call，无最终message文本。provider.py的`has_final and bool(text) and not final_text.startswith(text)`据此抛RetryableProviderError，整次响应不进入工具执行；一个批次三次耗尽后又进入transport recovery。

HTTP200与response.completed说明不能简单归因为URL不通。日志没有保存那个字符的原始值，**尚不能断言就是空白，也不能确定所有重试同因**。确定的是文本一致性校验与工具调用返回发生冲突，导致重复失败。此轮没有关闭校验或强行接受工具；应另行补最小fixture核对最终工具一致性与非正文碎片边界，不能为了通过就丢掉真正矛盾检测。

任务此时已提出完成，在既有completion gate等待；并非task_control暂停，也不是普通工具边界同步监察。协议故障遮蔽了后续完成判断，不能据此说混合控制失败。

## 成本与证据口径

- 监察成功记录usage：118条，输入15,495,019、输出11,567 tokens。
- 含被协议拒绝但已返回usage的可见完成响应：122条，输入16,022,901、输出15,105；不含无usage/被中止请求，非完整账单。
- 任务64条usage：未缓存输入80,570，cache creation111,511，cache read1,269,488，输出78,273；输入口径含缓存总计1,461,569。
- 日卡无法换算实际美元；不得以零新增模型种类声称低成本。视图响应字符数是工具返回体，不等于增量计费token。

## 下一步（未实施）

1. 先对照流式最终工具返回的失败协议做确定性定位，避免下一轮重复付费重试。
2. 审计决策视图为何连续扩窗仍未行动：查询作用域过窄、返回动作载荷过大、私人记忆仅一份working、重复材料是否真的被消费；不要盲目加必用工具规则。
3. 将“明确知道Set要求且看到再次改回no-op”作为时效诊断锚点，区分调查惯性、决策依据不稳和服务延迟；暂停0次留作未验证，不自动强制触发。

原始路径：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-literature-transfer-20260913-r1/fyn-2.2.0-roadmap__moZMPPE/agent/`。重点`monitor/monitor_private/audit/dialogue.jsonl`、`progress.jsonl`、`continuations.jsonl`、`monitor/task_evidence/public_events.jsonl`及原题。

派生统计：`method_discovery/artifacts/literature_transfer_20260913/r1_observation_metrics.json`；可用同目录`audit_r1.py`重算。关键源文件副本在`r1_public_files/`，来自停止的本条容器，不是参考答案。结论是**适配部分成立、增益未成立、暂停未验证，并有确定协议阻塞**；不接受/冻结候选，不自动扩大实验。
