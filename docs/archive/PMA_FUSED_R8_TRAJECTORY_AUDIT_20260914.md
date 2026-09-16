# PMA 融合 R8：轨迹审计

日期：2026-09-14。只读审计；未修改生产代码、未启动新任务。

## 对象与结论

- run：`clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r8`
- trial：`fyn-2.2.0-roadmap__FrLR3d6`
- 源码 commit：`2a2cc9e`；启动记录：`PMA_FUSED_R8_LIVE_20260914.md`。
- 产物根目录：`E:/LongContext/long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r8/fyn-2.2.0-roadmap__FrLR3d6`。
- 正常结束，任务执行约 16 分 16 秒，最终 Turn 82；10 次 review，最终 allow_complete。
- 事后原生评价 2/7 phases，reward 0.18181818：toolbar、desktop 通过。
- 工具式第二阶段退出已能完成一次完整运行；两次实际纠偏均有后续修复证据。但两阶段角色切换仍有工具拒绝，根任务完成仍被局部修复替代。不能接受为可靠完整完成控制。

## 1. 有效的行为

第一次纠偏指出 NewAllStrings 被实现成字符串匹配器，而任务要求组合多个 validator。后续 Agent 改为 validator chainer；事后 validation 子测试通过。

第一次完成提议时，监察者运行 build 并检查源码签名，发现 FromJSON 使用 []byte 而不是 string，以及 desktop.App 缺少 SetSystemTrayIcon、SetSystemTrayMenu 参数类型错误。第二次实际纠偏后 Agent 修改这些签名；监察者复查签名、desktop 接口与 build，最终 desktop phase 通过。

这证明本例中“调查—明确纠偏—Agent 修复—复查”可发生，不是所有纠偏都无效。但 validation 子测试通过不等于整个 phase 6 通过，FromJSON 签名修复也不等于 JSON theme 行为完整。

## 2. 确定的阶段接线摩擦

证据：`agent/monitor/monitor_private/audit/dialogue.jsonl`。

- L337 调用 intervene 已明确指出 JSON 与 desktop 问题。
- L338 返回 `Tool unavailable in this phase`。
- L348、L353 再次调用，同样被拒绝。
- L364 才切至 comparison；L369 调用、L370 submitted=true。
- 第一次尝试至实际提交约 57.7 秒。这里是完成边界，不能把这段时间描述成任务继续跑了若干轮。
- 全程另有 6 次 wait 因仍在 maintenance 被拒绝；合计 9 次阶段不可用错误。

源码依据：`monitor_agent_core/pma_fused.py` 的 FusedTransport.call 在 maintenance 移除 wait/intervene/allow_complete；dispatch 对不可用工具只返回通用错误。维护阶段必须输出 `<maintenance_complete/>` 才进入判断阶段，但共用持续 History 和监察身份，模型多次直接沿用其控制动作。

因此 R7 的修复解决了第二阶段无动作退出耗尽问题，却未彻底解决第一阶段和持续监察职责的衔接。不是服务异常，也不是纠偏内容本身无法生成。

L342 还在尚未成功提交时保存了 “completion claim REJECTED”。可以理解为自身判断拒绝，但它没有清楚区分判断和已执行控制；不能把这条记忆当投递凭据。

## 3. 核心效果问题：局部复查替代根完成判断

最后一次主要检查（D410，随后轮询结果）仅为：

1. grep FromJSON 签名；
2. cat desktop/app.go；
3. go build ./... 并输出 BUILD SUCCESS/FAILED。

随后模型称这两个 API 问题均已修复、实现满足全部要求，D420 allow_complete。

实际范围只是“先前提醒中的 API 问题已修复，生产编译通过”。它没有建立由这几项检查推到七个目标全部成立的依据。

全程 17 次 file_read 都指向原任务、synopsis、公开事件或 overview，未直接读取测试文件。8 次 code_run 中两次是运行会话轮询；其余包括 find、build、grep 与接口 cat，没有主动运行测试或展开测试断言。原始事件和自动观察输入可能含 Agent 的代码/测试片段，因此不能说它绝对没见过测试内容；可以确认没有主动检查测试实现、没有围绕行为要求执行判别检查。

事后评价暴露：

- app_test.go 的 dummyApp、theme/icons_test.go 的 themedApp 未实现 Metadata，导致多个测试包无法编译。go build 不会覆盖这些测试代码。
- Sprintf 转换存在 unsupported binding type，反向 Set 返回 cannot set value on a sprintf binding。
- 多个 phase 被同一个测试编译问题阻塞，不能把五个失败 phase 当成五个独立功能失败。

以上原生评价仅用于结束后诊断；并非在线监察者可用的答案或 checker。

## 4. 不是简单的“没有记忆”

最终 pma_memory.json 仍保留七个目标。Target 3 明确保留 NewSprintf、通知、Set 使用 fmt.Sscanf、URI 转换等行为要求。它们并未全部消失，而是没有进入最终检查选择。

同时 `audit/continuations.jsonl` 的唯一压缩笔记写了 “All 7 targets implemented”，把 Remaining Work 收缩到 testApp.Metadata、driver 构造问题和 build；保留 SetMetadata 疑问，但未把完整行为要求展开为待判断内容。

因此有两层观察：持久 bank 中要求仍在；近期认知摘要/进度叙述却把任务收束为局部剩余修复。后续实际检查顺着局部问题走。压缩可能强化这种收窄，但没有无压缩对照，不能认定它是唯一原因。

## 5. 成本与效率

`audit/provider_usage.jsonl` 的 69 条模型用量记录：

| 阶段标签 | 记录数 | 普通 input | cache creation input | cache read input | output |
|---|---:|---:|---:|---:|---:|
| maintenance | 49 | 41,985 | 4,090,811 | 1,128,564 | 4,457 |
| comparison | 20 | 18,654 | 2,420,309 | 149,426 | 1,844 |

这是 provider 报告的分类累计 token，不是唯一上下文大小，也不是美元账单；阶段标签可能覆盖阶段内的续接/压缩调用。本报告未重新汇总任务 Agent 成本，不能据此计算双方总费用。大量 cache creation 值表明不能仅凭 wall time 缩短就宣称降本。切换 system 和长 History 是否造成缓存复用差，需要另行核对请求缓存结构，当前不作确定因果结论。

## 6. 下一步建议（未实施）

1. 先处理两阶段动作衔接，使维护阶段已经形成的控制意图能自然进入判断，而非在不允许的工具上重复碰壁；不新增第三 reviewer，不静默把未提交当已提交。
2. 方法问题仍是“依据什么选择检查、何时从局部回到根要求”，不是再重复加一句要看测试。应围绕 bank 中已有而未被用于判断的行为要求研究输入/记忆消费方式，并保留调查自由。
3. 修复后同题比较时分别看：协议拒绝是否消失、行为证据是否实际被查验、局部成功是否仍导致全局误放行、成本是否下降。不能只看总分。

R6 同题为 1/7；R8 为 2/7，可报告探索性差异但不能把单次涨分归因于某一机制。纯 PMA 曾得 6/7 的运行是 FBR，不是本题，不用于同题横比。
