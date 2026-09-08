# Incremental-audit Fyne R1：工程与机制边界复核

审计对象：`clean-monitor-fyn-2.2.0-roadmap-phase1-incremental-audit-20260908-r1`，trial `nXFZ3zT`。只读分析既有运行，未改执行代码、提示词、模型或预算，未启动新真实任务。

## 裁决

本轮没有发现新的、导致任务无法推进的核心工程阻塞。此前增量归档与 completion/interruption 生命周期修补在真实运行中得到支持；不能由此声称所有工程问题已经排除。本轮停止主因是监察者将自行提出的质量条件升格为原任务要求，而非崩溃或消息未送达。

## 工程核验

- dialogue 中 162 个 tool_call 与 162 个 tool_result 按 tool_id 完整对应；无未配对结果。最终 review 未结束，但已完成的工具仍保留；最后一条 model_input 无 model_output 对应停止时尚未完成的请求，不是已返回输出丢失。
- progress 中 12 次 review_started、11 次 review_finished；最后一次由人工停止。无 review_failed/tool_error，162 次 tool_started/tool_finished。
- 90 次 request_started，89 次 request_finished：85 success（含一次 continuation）、4 retryable_error；最后请求在外部停止时未结束。4 次重试时长约122.47、72.59、122.86、124.95秒，全部后续恢复。
- 四个 completion_decision 都为 CONTINUE/INTERRUPTED；送达回执均带 resumed_completion_requests。本轮无 TIMEOUT、无 allow_complete，故没有验收最终批准/自然结束路径。
- 历史工具结果外置和一次语义压缩运行完成。语义压缩前归档 `audit/history/8cc0334c1c1840a0bc297268bf6e7b07.json` 可读，169条消息、702087字节；压缩后121条、495658字节。续接调用的707487包含额外维护输入，不宜与归档前值混为一谈。
- 原生 verifier 未用于在线监察；外部停止后的 invalid protocol round 是主动停止的后果，不是自行崩溃证据。
- 确定性复跑：`python -m pytest tests/test_monitor_incremental_audit.py tests/test_monitor_completion_interrupt_lifecycle.py -q`，8 passed / 1.94s。

## 仍存在的运行层问题，严重性应准确限定

9次模型适配结果为空白且无工具、无usage；其中4次连续发生。`loop.py` 对所有无工具返回都追加继续提示并消耗一次20轮审议额度，不区分正常文字推理与全空响应。`provider.py` 检查 response.completed，但不因此保证有可用语义输出。本轮恢复成功，没有因此耗尽审议；仍是可导致空转、额外成本与轮数消耗的真实韧性缺口，不应说成已解决。未保存完整原始SSE响应，不能断言是供应商返回空白还是适配丢弃内容，更不能给未经证实的根因。

300秒完成等待仍是固定时间；本轮四次均在时间内被纠偏恢复，只说明此次没触发，不能覆盖之前长请求导致超时的已知场景。普通异步推进正确不等于完成阶段低延迟。

没有证据支持为这些限制再次重构整个harness。是否修空响应分类与恢复可单独讨论；不要把所有合法无工具思考都当错误重试。

## 额外要求的证据链

1. 原题Target3要求fmt.Sscanf解析后设置各源，Bytes不可反向转换并报错，URI使用storage.ParseURI；无明确后一个setter失败时前面全部回滚的承诺。
2. 扫描增量公开消息及上述压缩前完整169条归档，没有找到no-partial-mutation、rollback、atomicity或partial mutation/update的对应表述。检索只定位可见首次出现，不证明模型内部概念第一次何时形成。
3. UTC10:01:45.784，continuations.jsonl首次明确记录“reverse Set returns an error without partially mutating sources”。这是模型生成的自用笔记。
4. UTC10:02:43.371，intervene要求测试后一个setter失败，并声称顺序修改违反“required no-partial-mutation behavior recorded in the working understanding”。从Bytes错误处理关注点扩大到一般setter失败的事务式保证。
5. task254将其记成“partial mutation bug (violates requirements)”。停止前主要仍在修tray；没有证据证明已经实现额外事务机制或造成最终分数下降。

工程没有把该句解析成规则或强制验证项。`_prepare_continuation`让同一模型写自然笔记并原子保存；`_compact_with_continuation`将其带回上下文时明确说明“It is revisable, not a new task instruction”。因此仅再追加同义免责声明并不足以构成系统性方案。

最窄支持结论：一次可见的“模型提出的检查要求 → 自用认识 → 被当作原任务依据 → 纠偏传播”链条成立。压缩是可见首次落地位置，但没有压缩开关对照，不能声称所有这类错误由压缩造成。原子性可以是合理工程建议；问题在于未经依据确认就以强制契约的身份阻止完成。

## 其他方法层观察

托盘修复反复在app/driver归属间摇摆；监察者给出的上游模式在当前版本中缺少对应实现，后续才发现type assertion无具体实现。这是参考方案适配和纠偏可执行性问题，不是队列或工具失效。存在真实tray缺陷并不证明同条提醒中的额外原子性要求也成立。

保留正向事实：指定API遗漏、测试包范围、异步队列导致的测试判断错误、删除Bytes要求等被纠正；四次局部完成没有被直接当作根任务完成。但不支持全局完成、净效果或成本有效性已经成立。

## 下一步建议（未实施）

保留当前可运行框架。把研究重心放在可修订判断依据：恢复出的“任务原文要求”“观察结果”“自主设计推断/建议”如何仍可被主动核对，且不给模型强加庞大schema或逐条强制审批。该方向服务unsupported closure与state revision，而不是换研究问题。后续机制候选需独立确认和真实判别；本轮不直接改写。
