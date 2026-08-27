# M2-C Fyne-2.2 R2：显式语义作用关系门禁（2026-08-27）

## 裁决

M2-C 在共同真实任务 `roadmapbench:fyn-2.2.0-roadmap` 上通过了首轮结构性门禁：它没有复现 M2-A 的 anchor-only revision pollution，并把公开证据对根 obligation 的影响记录为少量、可追溯、可重验证的语义作用关系。运行因用户计划关机而在 Target 3 初期安全停止，无自然终局和 native verifier，因此本报告不声明最终任务效果提升，也不冻结 C 为 M2 最终方法。

## 候选定义与边界

- 父版本：冻结的 M1-C 主动重建实现（commit `6128acc` 加行为中性修复）。
- 候选开关：`GA_M2_SEMANTIC_IMPACT_ENABLED=1`。
- A/B/C 三个候选开关互斥；不开启任何 M2 开关时仍运行 M1 行为。
- 在线信息仅包括公开任务、Agent 行为、工具结果、文件和测试；未使用 native verifier、隐藏测试或 gold answer。
- C 只允许监察者提出 `cause public_evidence -> target root_obligation -> effect`，确定性内核验证对象类型、公开 provenance、局部关系和 effect 类型；内核不判断语义真假，也不能据此建立 completion。

## R1 工程反例与修复

R1 的 turn 10 中，监察者根据公开编译失败正确提出 contest，但验证器要求提案锚点与归档锚点存在字面字符串交集。语义等价的转述因此被拒绝，使 C 退化为复制内部字符串的格式门槛。这是实现过约束，不能用于评价方法 C。

修复后：提案与原因对象都必须具有公开 provenance，但不再要求锚点逐字相交；影响范围由显式 cause-target 关系或 evidence 的 root link 限定。该修复允许自然语言引用不同粒度的同一公开事件，同时保留局部作用域约束。

## R2 真实轨迹事实

- 运行时间：2026-08-27 20:48 至约 21:47（Asia/Shanghai），约 58 分钟。
- 监察决策：38 次；最后决策为 `SILENT`，Agent 已从通过聚焦验证的 Target 2 转入 Target 3 探索。
- 接受的 semantic impact：8 条。
- 安全停止时 pending semantic impact：0 条。
- 8 条影响均含具体 public evidence、目标 obligation、effect、理由和公开锚点；未发现只因锚点措辞刷新产生的版本。
- Target 1 metadata repair 完成 `HOLD -> Agent uptake -> focused evidence -> RELEASE`。
- Target 2 theme repair 中，监察者发现 API 类型、fallback、短颜色、Fonts/Icons、URI、`boldItalic` 以及测试 oracle/fixture 冲突；Agent 分步修复后，聚焦测试与 package build 通过，监察者释放局部 repair，但保留根任务未完成。
- 未观察到无限 HOLD、已成立证据后的持续纠缠、根任务误关闭或明显能动性压制。

## 与 M2-A 的共同任务比较

M2-A 在同一 Fyne 2.2 任务的早期运行中产生 37 条 revision，其中 31 条（83.8%）没有 proposition、epistemic state 或支持关系变化，只改变自然语言 source anchor。C 没有对 projection 的普通序列化差异自动版本化；它只在监察者明确声明、且内核验证局部证据关系时写入影响。因此当前证据支持：

> C 避免了 A 的表面差异修订污染，并能在真实 repair/release 循环中维护可重验证的 contested obligation。

当前证据不支持：

- C 已提高最终 native verifier；
- 纠偏收益完全独立于 M1 监察者能力；
- C 已优于尚未完成共同任务筛选的 D；
- 单题结果已证明跨任务泛化。

## 成本快照

来自 `research_events.jsonl` 的 provider usage：

| 调用类型 | 调用数 | input tokens | output tokens | cache creation | cache read |
|---|---:|---:|---:|---:|---:|
| Task Agent | 40 | 51,977 | 0 | 68,497 | 737,021 |
| Monitor（含主动检查） | 61 | 1,068,374 | 105,340 | 0 | 0 |

中转服务未提供可靠美元价格映射，故不伪造 USD 成本。该快照只记录贯穿成本；本轮没有等预算终局，不能据此归因 C 的效果或与 A 做最终成本效益比较。

## 限制与下一门禁

- Harbor `result.json` 因安全提前停止仍保留 running 元数据；它不是完成结果。
- 没有运行 native verifier，不能把 Target 1/2 的局部测试通过等同于整题成功。
- C 作为可回退候选检查点保留，不作为默认开启配置。
- 下一步应在相同 Fyne 2.2、模型、预算、turn/time 上限和在线边界下实现并运行 M2-D；完成 A/B/C/D 的共同任务筛选后，才能选择暂定优胜者并轮换其他 `method_dev` 任务。

## 原始产物

- R2 run root：`long_context_bench/output/m2_real_tasks/m2a_first_gate/m2c_semantic_impact/fyn-2.2.0-roadmap-r2/`
- R2 trial：`fyn-2.2.0-roadmap__xUo6UUS`
- 关键状态：`agent/m0_monitor/m1_workspace.json`
- 决策轨迹：`agent/m0_monitor/decision_0001.json` 至 `decision_0038.json`
- 公开轨迹：`agent/m0_monitor/public_trajectory.jsonl`
- 成本事件：`agent/research_events.jsonl`
