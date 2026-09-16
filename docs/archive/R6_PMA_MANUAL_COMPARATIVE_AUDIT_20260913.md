# R6、原生 PMA 与人工监察：判断依据审计

## 范围与比较边界

本轮只读源码和已存原始运行材料，不改生产机制、不调用模型、不启动实验。
R6：Fyne 2.2 / GA / 双 Opus4.8，68轮、23分30秒、1/7，reward 0.090909。
原生 PMA FBR R2：FBR / Terminus2 / Sonnet4.5任务+Opus4.6记忆，48次任务调用、42分43秒、6/7、reward 0.875。
人工 Fyne：256轮、约60分46秒、7/7；人工提前知道部分旧失败，成本未完整计量。
三者不是公平配对，不能据分数推出复杂化导致退化或 PMA 的净贡献。人工仅作行为参考。

## 原始证据定位

R6 根目录：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r6/fyn-2.2.0-roadmap__BojTscC/`。
下文 D 指 `agent/monitor/monitor_private/audit/dialogue.jsonl`，行号为物理 JSONL 行。
原生 PMA：`bench_runtime/pma_linux_controller/native_fbr_20260912_r2/work/trial/trajectory_memory.json` 的 steps，及 agent/episode-45/response.txt。
人工根与完整协议见 `PHASE1_MANUAL_FYNE_REFERENCE_AND_CONTINUITY_CHANGE_20260907.md`；本轮重新读取 archive/001、011、012、014 的实际干预。

## 已确认的断裂

1. **目标记住了，但检查标准被降级。** R6 task_model.md 保留源变化通知、Set 双向解析、菜单刷新传播、全部 App 实现等行为要求。D316 对 JSON 和绑定只执行 ls；菜单仅 grep 字段和 Refresh 方法。D321 对 OnTapped 只 grep 名称。最终 D342 把这些结果及 build 提升为全部完成。不能简单解释为缺原任务或工具能力。
2. **表示本身也并不完美。** task_model 的 JSON 核心描述重点是颜色，未完整列出字体、图标、尺寸覆盖；还自行写出 “Not required: ... specific rendering behavior”。这不是逐字原任务。此概括可能错误收窄关注，但不能仅凭该句断定它导致某项失败。原任务仍可读且完成边界有原文。
3. **局部线索被持续强化，其他功能停留在文件创建记录。** D133/184 围绕 Metadata 方法；D215/247/290 持续聚焦 Target6 与旧 Metadata 核验争议。D290 仍明确说 Targets2–5 未近期检查；随后主监察并未验证绑定/主题行为，而采用名称盘点。不是所有 bank 状态都直接写完成，最后的过度推断主要由主监察作出。
4. **工程保存来源不等于模型理解证据边界。** D333 使用 `timeout 30 go build ./... 2>&1 | grep -E "error|cannot|undefined" | head -10 || echo "Build successful"`。无 pipefail 时管道退出码不能证明 go build 成功；D339 是这个管道的 exit0/空输出，D342 却解释为 build 成功。任务自己的输出另称 build 成功，因此不能据此断言本轮真的编译失败；能确定的是监察自查证明方式无效。
5. **有恢复过的工程异常。** D246 尝试 memory_delete("status")，返回 ID not found，维护回滚并重试；D247 成功。这修正此前“没有工程异常”的笼统说法。不能将最终失败全部归因于此，因为之后仍正常维护、工具调查、allow_complete。

## 与纯 PMA 的真实差别

原生每步维护+比较、最新8步、bank、直接向任务发提醒；本地在这些步骤后再加入持久主监察、工具调查、工作笔记与根完成裁决。
本地仍调用作者 process，但 JudgmentMemoryAgent 重写两阶段 user prompt，adapt 修改 system/工具描述；观察额外包含近期监察工具回执和上次纠偏；R6 再加入 task_model。
因此不是“原生 PMA 原封不动加能力”的等价系统。作者执行循环复用不等于作者输入、职责、行为原样保持。

原生 Step46 指出 mime 变量遮蔽包，episode45 改名并 build，信息链具体短且有后续动作。不能排除任务自己也会修。
原生 Step28 同样在保留字面 wildcard 要求时引入 NOT AllowCredentials 例外，记忆和建议共同强化错误；它不是已解决证据失真的答案。原生6/7的成功不能反证此失败机制。

## 与人工的差别

- 001：不是查 Refresh 名称，而是比较 canvas.Content 与 canvas.buildMenu 是否相同刷新路径。
- 011：不是读到 Set/Get 就认为响应正确；区分返回值与 DataChanged 通知，并用直接 fmt.Sscanf 控制检查测试 oracle。
- 012：不是 App 接口 stub 编译就算完成，而是实际默认值、重复覆盖、真实实现行为。
- 014：指出指针/数量在 Refresh 前已变，空 Refresh 也能通过；建议记录真实 SetMainMenu 调用，重置初始化计数再测。

人工把问题组织成“什么行为会区分这个实现与一个有同名空壳的实现”，并非每项都必须复杂测试。它也保留局部释放和返回根任务，不无限检查 UNKNOWN。
本轮重读的是人工干预原件，而非重新遍历全部 Codex 原始工具会话；不声称完全复原人工内部思考或逐工具成本。

## 结论与尚未证明的假设

已确定：R6 修好了任务模型接线，但未解决要求到有效检查的转换；弱证据经主监察被提升为强完成结论。存更多信息和重复强调原任务不足以保证这个转换。
有根据但未隔离的假设：bank、working notes、task_model、多阶段提示和调查 History 构成多个不一致的认识副本；最新局部疑点获得更多重复曝光，导致选择性检查。不能声称已测得注意力因果或上下文长度是主因。
应保留：自然任务模型、通用原始证据工具、具体局部纠偏及核验能力。
下一设计宜围绕“原行为要求—能区分正确/错误的观察—实际证据—允许结论”这一条认识链，先厘清现有 PMA 维护与主监察的责任和重复表示，避免直接再叠新模型/新工具/字段或单题规则。此处是设计方向，不是已验证机制，不授权自动实施。
