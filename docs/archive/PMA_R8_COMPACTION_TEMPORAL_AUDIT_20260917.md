# R8 压缩与错误完成判断：时序审计

日期：2026-09-17。第一步仅审计历史，不改实现、不调用模型、不启动实验。

## 结论

R8 的“目标已完成，剩余只是局部修复”叙述在唯一一次语义压缩之前已经出现，并成功写入 PMA status。压缩续接笔记沿用了这种收窄，不能解释其最初形成。最终 comparison 输入仍包含关键行为要求，故本例不能归因为这些要求被压缩删除、再也不可见。

更准确的结论不是“压缩无害”，而是：**已有要求未被充分用于调查与根完成判断，是比压缩导致首次遗漏更直接的下一步研究对象。** 压缩是否强化错误、改变注意分配，仍需对照；本审计不能给出无压缩时的结果。

## 证据位置与方法

run: `clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r8`

trial 根目录：

`E:/LongContext/long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r8/fyn-2.2.0-roadmap__FrLR3d6`

下文 D 指该目录下 `agent/monitor/monitor_private/audit/dialogue.jsonl` 的一基行号；其余 audit 文件也在该目录。时间统一为 2026-09-14 UTC+08:00。

逐条提取 model_output、bank 操作及成功回执，避免将任务 Agent 的声明、工具返回中嵌套的文字误认为监察者自己的判断。交叉检查 continuations、progress、history_transforms、压缩前完整 provider history 和最终 comparison 的 wake_context。不是根据关键词命中总量判断原因。

## 时间线

| 时间 | 原始证据 | 观察 |
|---|---|---|
| 初始化 | D24 及后续 bank 回执 | 保存七个目标，Target 3 包含源变化自动更新、Set 使用 fmt.Sscanf、Bytes/URI 处理等要求。 |
| 00:57:21.940 | D158–160 | 监察者写入“Completed Targets 1-4”，以文件/API 添加概括各目标；刚读取的是 synopsis（D154–155，start=41，lines=10）。D160 确认 status 更新成功，不是未提交草稿。 |
| 01:00:45.549 | D213 | 写入“✅T1-6 complete”，包含 NewAllStrings。 |
| 01:01 左右 | D224、230 | 同一次 review 的判断阶段识别 NewAllStrings 实际是字符串匹配器，不是 validator chainer，并纠偏。说明维护中的完成标签已经过早，且当时仍有纠错能力。 |
| 01:02:03.102 | D250–252 | 写入“after completing all 7 targets”，同时列出尚未修好的 validation、JSON 与 build 问题。是“主体已做完，只剩这些问题”的叙述，不是正式 allow_complete。D252 成功写入 bank。 |
| 01:02:52.815 | D275 | 待办进一步收缩到 testApp.Metadata 和 meta.go driver 创建等编译问题。 |
| 01:03:14.535 | progress: continuation_started | 唯一一次语义压缩的续接生成开始。 |
| 01:03:31.334 | continuations L1 | 续接笔记开头“All 7 targets implemented but build failing on two issues”；Remaining Work 为两处修复与 build。仍保留 SetMetadata 疑问，并非所有未知全部消失。 |
| 01:04–01:06 | D306–374 | 压缩后开始核查第一次根完成提议，发现 FromJSON 参数类型和 desktop.App 方法/签名不符，最终成功干预。不能说压缩后模型只会接受完成。 |
| 01:07:33.204 | D396 | 最后 comparison 的 wake_context 仍明确提供 Target 3 自动更新与反向 Set 的行为要求。 |
| 01:07:59.156 | D410 | 实际复查只有 FromJSON 签名、desktop/app.go、go build ./...。 |
| 01:08:15.738 | D419–420 | “两处 API 修好、build 通过”后，称“The implementation now meets all requirements”，调用 allow_complete。这是明确的局部证据向全局完成扩张。 |

## 压缩实际做了什么

`history_transforms.jsonl` 两条记录分别是工具大结果归档与语义压缩，不是两次语义压缩：

- 工具结果归档：98 items，710719 → 689598，归档两项结果。
- 语义压缩：98 → 54 items，689598 → 417405；移除前 45 条消息并插入一条续接，保留后 53 条消息。日志大小字段叫 characters，但该变换声明 size_unit=utf8_bytes，不当 token 数。
- 压缩前快照：`history/f785db5bc5324a4abe798d3b28d71b9e.json`。
- 快照零基 index 48 是“Targets 1–4 complete”的监察者工具调用，index 81 是“all 7 targets”调用，index 97 是含原任务及更新 bank 的当前输入。这三项都在 cut=45 后的保留尾部中。
- index 97 同时包含 `Set() uses fmt.Sscanf`、`When any source binding changes` 与 `Set(str string)`。D396 又重新提供相关 bank 内容。因此证据不仅是“最终磁盘 bank 还在”，而是关键要求确实进入后续模型输入。

代码阅读辅助核对：`monitor_agent_core/agent.py::_prepare_continuation` 用同一模型、现有 history 与 bank 生成自然续接；PMA 开启时不写 working.md。`provider.py::_compact_with_continuation` 先归档，再生成笔记，再以笔记加保留尾部替换 history。实际运行是否发生及裁剪规模以上述 R8 归档为准，不用当前源码存在替代运行证据。

## 能排除和不能排除什么

能排除的窄解释：

1. “七个目标已实现”的叙述第一次由本次语义压缩产生。
2. 最终遗漏 Sprintf 行为检查只是因为相关要求已从所有可见输入中消失。
3. 压缩后完全不能再发现新问题。

仍不能确定：

1. 压缩是否进一步强化完成倾向、削弱调查连续性或增加遗漏概率。
2. 过早 status 是否因果性地主导最终判断。时间顺序和内容一致性支持该假设，但同一次轨迹不是干预对照。
3. 模型究竟“没用要求”还是“用了但错误评估证据”。输入可见、工具选择和公开结论可观察，隐含认知不可直接测量。
4. 不压缩是否会得到更好结果，以及 PMA 融合结构是否导致此问题。需控制实验，不从本次审计推出。

## 对下一步的影响

- 不优先修改压缩；保留其为后续独立候选。
- 下一步仍先独立修协议摩擦，不同时改记忆结构、提示判断原则与调度。
- 后续最小机制对比聚焦：要求已有且可见时，如何避免把进度记录当满足证据，以及如何让实际检查覆盖当前决定的范围。
- 根完成必须区别于局部纠偏验收；关注实际调查与错误放行，不把更详细的笔记或更多 basis 引用当效果证明。
- 不据此删除已存在的 follow 控制，也不把修好 A 后遗漏 B 标为 A 的 relapse。

## 本步验收

- [x] 核对首次完成叙述、bank 落盘、压缩生成、裁剪与最终放行顺序。
- [x] 区分任务方声明与监察者自己的写入/判断。
- [x] 检查压缩前快照及压缩后实际输入，而非只检查最终 bank。
- [x] 明确事实、推断、待实验项。
- 本步仅新增此审计文档；无生产代码、配置或运行状态改动。
