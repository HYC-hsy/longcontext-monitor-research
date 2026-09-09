# 候选 U：Fyne R1 真实运行结果与恢复点

## 运行与停止

- Run: `clean-monitor-fyn-2.2.0-roadmap-phase1-grounded-u-20260908-r1`
- Trial: `fyn-2.2.0-roadmap__pVASD8q`；配置及源码摘要见同目录 LIVE 报告和 manifest。
- 2026-09-08约21:14至22:59 CST，约105分钟，最后公开任务轮419；预算500轮/10000秒。
- Claude Opus4.8任务模型、GPT-5.6-sol high监察者；没有人工向任务补充纠偏，没有在线隐藏评价。
- 观察者因持续低收益收尾循环提前停止；宣布停止时约97分钟/398轮，最终归档419轮，不能把前者当最终时长。
- 精确任务容器停止成功。runner随后自行退出1；最终docker ps为空。没有删除轨迹或镜像。
- runner报protocol round/wrapper未完成等错误是主动停止后的结果，不是把一次中转错误误判成任务失败。无完整native成绩，不宣称任务通过或候选有效。

## 本次想判别什么，实际得到什么

U允许模型读自己的自然笔记时一并取回链接原文，减轻把旧认识直接当依据的问题。模型拥有普通file_read/code_run，U是可选能力，不是强制门控。

实际351次工具调用：file_read151、file_write2、code_run112、wait56、intervene28、allow_complete1、read_with_sources1。调用数不是成功送达数。

唯一U调用时间1788873354.303，读`monitor/working.md`及原题174行、最初公开事件2行，约0.07秒完成。之后一直使用普通读取/代码工具，没有第二次U调用。因此本轮证明工具真实接通，但不能证明持续恢复依据的机制有效，更不能把28次纠偏的收益归因于U。

后续压缩笔记把虚拟路径`task/...#L...`改为Linux绝对路径加`:行号`。当前U不支持后者；这是后续使用的接口风险，但本轮没有再次调用，不能声称该风险已经导致实际工具失败或解释了不调用。

## 保留的能力证据与未闭合问题

时间锚点为UTC epoch，可在dialogue/public_events/runtime_receipts中定位。

| 观察 | 证据锚点与限定 |
|---|---|
| 发现具体实现遗漏 | 1788873462前后App.Metadata实现缺失；1788873600 URI资源Content占位；1788873627 NewSprintf类型/写入能力遗漏。任务后续有相应修改。 |
| 主动审查测试而非只看通过 | nil-driver托盘测试的defer参数提前求值替换了全局app；1788875506监察者识别真实fixture原因，任务后来修正并获得局部通过。观察者没有把自己看到的答案输入任务。 |
| 有持续跟踪，也有重复打断 | 1788875531在任务准备正确修复时再次提醒，随后1788875565又指出补丁被取消；需要审计提醒实际价值和时效，不能把所有intervene视为收益。 |
| 根要求仍能被重新发现，但较晚 | 1788877074才明确指出DataChanged需保留最后通知对应的错误；任务301以后修改并补测试，说明此前局部完成不等于完整覆盖。 |
| 旧观察未及时撤回 | 1788877685仍提早期base.Init问题，任务此前已修；同条消息中也有有价值的缓存测试序列要求。不能把整条简单标成全对或全错。 |
| 完成生命周期仍错位 | 1788876489普通review调用allow_complete返回“No root completion is pending”；随后真实completion返回“no completion approval was issued”。需核对认知中的完成与运行时pending是否一致。 |
| 后段未收敛 | 1788878620、1788879059继续纠正多份报告中的no-regression/full-suite/deadlock-safe声明、历史示例及测试计数；最后419轮仍在改这类文档。风险声明有真实依据，但反复扩展报告并不等于推进主要任务。 |

早期部分测试判别力不足：MenuRefresh_AllWindows主要验证不崩溃；ToolbarSetIcon只看item数量。后来托盘计数及错误缓存序列更具体。尚未逐项重审全部测试，不能宣称测试质量已全面恢复。

本轮部分解析失败不应写入未成功解析值的提醒发生在首次压缩之前，并有`err != nil && n == 0`分支依据。不能沿用上轮结论把所有partial-mutation讨论归为压缩生成的额外要求。

## 工程异常与成本

- 58个review_context，181个model_output；187条provider_usage包含维护调用，勿与model_output用量相加。
- 10次completion提议和决策：4次INTERRUPTED、3次MONITOR_CORRECTION、3次TIMEOUT；没有最终接受。
- 一次`Empty continuation; keeping original history`异常（1788875848），随后同历史恢复；不是永久停机。
- 有多次ChunkedEncodingError及长重试。1788877285起请求失败后再请求，到1788877685才输出提醒，造成数分钟观察滞后。延迟同时含服务/网络与模型计算，不能全部归因high。

已归档provider报告用量（未完成调用可能不含在内，不是最终账单）：

| 对象 | usage记录 | 输入 | 输出 | 缓存说明 |
|---|---:|---:|---:|---|
| 监察者 |187|24,000,208|50,053|输入中cached_tokens=11,162,112，不重复相加|
| 任务Agent |408|587,901|171,110|另有cache_creation=746,815、cache_read=7,660,169；Anthropic分列口径|

任务输入按上述分列合计8,994,885。监任务口径不可只比较587,901与24,000,208。中转日卡计价不明，未换算美元；本轮没有证明降本。

## 改动与验证

启动前补齐`GA_MONITOR_GROUNDED_CONTEXT`从manifest经Harbor到GA adapter的传递，避免核心实现存在但真实入口未启用。涉及`ga_monitor_adapter.py`、`adapters/harbor_ga_agent.py`、`scripts/run_ultralong_m12_proofs.py`及`tests/test_monitor_grounded_context.py`；新增`method_discovery/prepare_grounded_u_run.py`用于准备/小连通探测，不自动启动。

相关测试21+91=112项通过；两模型升级权限后最小连通成功（5.65s/3.42s）。运行期间未改策略源码。工程通过与方法有效分开。

## 下一停止点

先审计“为什么恢复原文只在初始化发生”，以及过期纠偏、完成生命周期和报告修订如何相互作用。不要未经证据直接强制每轮读来源，也不要立刻堆叠W/R。U尚无独立增益证据，也无充分淘汰证据；真实重跑需新授权。

原始目录：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-phase1-grounded-u-20260908-r1/fyn-2.2.0-roadmap__pVASD8q/`。
关键原始文件：`agent/output.txt`、`agent/research_events.jsonl`、`agent/monitor/task_evidence/`、`agent/monitor/runtime_receipts.jsonl`和`agent/monitor/monitor_private/audit/`。长路径读取用Windows扩展前缀。
