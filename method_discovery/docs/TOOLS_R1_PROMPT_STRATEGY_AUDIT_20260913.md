# 工具实验运行中的提示词审计（只读，不改变该分支）

用户要求趁后台运行审计提示词。工具实验tools-t23-20260913-r1继续运行，未修改运行代码或注入人工纠偏。此审计不代表用户已批准策略候选。

## 实际可见面

源码主入口：GenericAgent-main/monitor_agent_core/agent.py，MONITOR_SYSTEM_PROMPT、review中的callback模式、decision_context附加说明、工具schema。
runtime.py：turn-zero初始化、普通唤醒、root handoff提示。loop.py：无工具回复后的续接、普通工具结果后的续接。
working_context.py：每次请求当前工作笔记的解释文字。decision_context.py：当前synopsis、上次纠偏、组合工具结果文字。
agent.py的CONTINUATION_MODE_PROMPT和_prepare_continuation：压缩前记忆交接；provider.py负责装配、压缩和恢复。

已从当前trial `fyn-2.2.0-roadmap__7evXeR8/agent/monitor/monitor_private/audit/dialogue.jsonl` 的review_context读取实际system/wake/tools，核对与源代码一致。
当前启用active_working_context、decision_context；未启用tool_feedback/grounded/advice_revision/feedback_focus/inquiry/live_awareness。不能把这些未启用候选的提示当成当前行为原因。
实际callback路径覆盖REVIEW_MODE_PROMPT，说明intervene不结束review、随后可继续调查。不能只看默认REVIEW_MODE_PROMPT就断言实际仍在串行单次纠偏。

## 已保留的正确原则

单一持续身份、原任务优先、自然可修订笔记、synopsis导航而非证明、关注causal intent及测试作为可执行任务解释、公开证据纠偏、继续观察后续理解和行动、局部释放不等于根完成、不验证每一个unknown。没有证据表明这些原则在迁移时整体丢失。

## 发现与假设分开

1. **证据充分性指导不够可操作（文本事实+行为对应，因果尚未判定）。** 文本已有“不充分证据”“局部成功不是根完成”，不是完全没写。但没有帮助模型区分编译可行、具体行为支持、修改影响范围覆盖。旧Claude分支最后go build成功便allow；本分支早期笔记多次COMPLETE(Build verified)。改进方向是说明一条证据能支持什么，而非强制跑某套测试或加字段。
2. **反完美主义的约束与必要调查的依据不对称（假设）。** “不要验证所有unknown”“不要重开有充分支持的工作”“更多阅读仅在改变决策时有用”均合理，但后者可能循环论证：模型已确信完成，就觉得无需调查能推翻自己的依据。应围绕核心任务结论可能被何种可获得证据推翻来选择检查，不按未知数量穷举。不能据本轮直接认定删除这些约束会更好。
3. **测试被提及，但不是清楚的调查对象（文本事实）。** 当前说“changed tests as executable interpretations”，没有要求机械读所有测试，这应保留自由。但未说明没有新测试不等于没有测试风险、现存测试实现也可能被接口修改影响。旧分支主动排除_test.go，是模型选择，不是工具限制；可探索通用的“修改影响现存依赖/验证依据”指导，不加Fyne或特定文件规则。
4. **局部纠偏后的成功定义仍模糊（假设）。** “reasonably resolved”允许合理静默，但模型会从一个补改跳到“所有干预成功”；它已有区分局部与全局的文字，却未稳定落实。候选应强调观察是否回应原争议，允许理解恢复时静默，同时不将局部理解恢复升级成根完成；不要求每次填写repair表。
5. **普通结果续接有协议表述歧义（代码事实，行为影响未知）。** loop.py普通工具后反复发送“finish with one control action”，而实际callback模式intervene不结束review，可在一次review多次干预。最高层system已澄清，但下层文字不够一致。后续可改为遵循当前review模式的中性续接，不增强结束压力；不能宣称当前模型因此提前静默。
6. **工作笔记可能放大早期误判（机制交互，不全是提示问题）。** 每次可见工作笔记，包装已明确“不是验证真相、可能过期”，但模型自己写COMPLETE后可不断沿用。不可只靠再加一句“要怀疑摘要”声称解决，须观察其是否主动检验支撑当前结论的原始材料。工具本轮仍需单独验收。

## 后续候选取向（待讨论）

优先将策略组织为一个连贯判断：当前准备相信/放行什么结论；手上证据是否真的覆盖该结论；若关键处仍不确定，哪项最小观察能改变判断；据此纠偏或合理静默。这里只是语义指导，不要求模型输出固定四字段或每轮仪式性检查。
保留即时干预、持续跟进和自由工具，避免新增另一串禁令、目标任务专用样例或逐项机械审批。先等工具实验完成，审计出哪些改善/缺陷仍存在，再固定策略实验的最小改动。
