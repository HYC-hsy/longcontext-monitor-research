# PMA 与 Clean：历史容量、纠偏时机和内容审计

## 范围与结论

本轮只读检查源码、已存真实轨迹与调用统计；无模型调用、无新任务、无生产代码修改。PMA 是外部基线和机制来源，Clean 是研究主体。当前证据不能裁决两者整体优劣：PMA R2 是 FBR/Terminus2/Sonnet4.5+Opus4.6/50轮，Clean 本轮是 Fyne/GA/Opus4.8+GPT-5.6-sol high/500轮。不同题、模型、预算和调度不可直接排名。

核心判断：Clean 提供了更广的调查与干预能力，但尚未把这些能力组织成低延迟、容量可持续的决策过程。PMA 缩短了每次判断的信息路径，并用同步等待保持步骤边界上的新鲜度；这不等于它实现了并发意图级纠偏。

## 1. 历史容量：PMA 避开了我们此次的失败形态

|维度|PMA 原生实现|当前 Clean|
|---|---|---|
|主要输入|原任务＋最近8步公开轨迹＋当前 memory bank|持续调查 History＋可检索原始轨迹/文件＋自然 working.md；本轮另加临时最新笔记视图|
|跨调用延续|显式 bank 的更新；不累积整个监察调查对话|同会话工具调用、返回、判断持续累积，超限时归档与语义交接|
|容量控制|滑动窗口；bank 可删除修改；超过50条且启用 BM25 时按两类各取20条|大工具结果归档；仅允许退休较旧已完成 review，保护最新两个 review 及整个当前调查|
|边界|条目长度和原任务并无严格 token 上限；不能宣称永不超限|当前调查可以很长，使受保护尾部本身过大，压缩无法回收|

源码纠正：memory_agent.py 的说明写到共享会话，但实际 `_call_llm_phase1/2` 均未传 `message_history`；作者 external/harbor 的 LiteLLM.call 每次创建消息列表。当前审查的原生路径通过更新后的 bank 把 phase1 结果交给 phase2，不能依据注释宣称完整 phase1 对话持续进入 phase2。

Clean 具体故障链：

1. `provider.py:_compact_with_continuation` 使用 `boundaries[:-2]`，保护近期完整 review 和当前调查。
2. 可回收量达不到 soft limit 与 target 的差时 defer，即使整体已接近/超过容量。
3. `_compact_history` 仍超限便抛出 `history remains over capacity`，不再正常审议。
4. `complete` 在压缩之前追加 wake 输入；失败后运行时再次唤醒继续追加。末四次记录 874879、881592、888305、895018，形成无效增长。

这不是“没有压缩”，而是压缩保护单位过粗、容量失败恢复不能前进。临时 working context 在压缩之后加入、请求结束移除，不能直接归因于笔记副本堆积；其对行为长度的间接影响仍未有配对证据。

## 2. 时机：PMA 的及时性有同步等待代价

原生 PMA 初始化先运行；普通执行步骤完成后累计轨迹，固定 trigger interval=1，通过 `await _trigger_memory_agent` 等待两阶段记忆调用，然后下一任务推理消费提醒。完成提议走另一个分支，并非所有完成提议都先经过这次 memory trigger。

因此它主要纠正“刚完成步骤对下一步的影响”，不是在工具执行之前读到错误意图便强行打断。任务不在它判断期间推进，自然不存在同等形式的并发追赶问题。不能把这种新鲜度当成免费收益，也不应因此改回串行审批。

Clean 本轮9次 intervene、6次 wait，wait 多为1–3轮，并非固定20轮造成迟缓。9次提醒时间（北京时间）：23:18:25、23:21:48、23:28:33、23:34:06、23:40:19、23:46:16、23:56:35、00:08:08、00:27:31。相邻提醒间隔不等于检测延迟，但足以说明不能用“仍在调用工具”冒充实时跟踪。另有24条 request_finished retryable_error；模型等待、重试与调查均占时间，尚未分离各自因果贡献。

应分别度量：最新行为何时公开、何时读到、何时形成/提交提醒、何时任务消费、消费后如何行动。短 wait 只控制下一次观察机会，不保证醒来后及时重读最新意图。真正需要解决的是调查过程中保持对当前修复进展的感知，而不是机械提高提醒频率。

## 3. 内容：PMA 的任务较窄，Clean 的调查更广但更易扩散

PMA phase1 更新 status/knowledge/procedural，强调精确要求、约束、失败经验和删除过期条目；phase2 消费更新后的 bank 与近期行为，选择有用的信息而非倾倒全库。提示要求在遗忘约束、重复失败、当前方案与已有信息矛盾时提醒；已可见的信息、无具体缺口或不确定时默认不提醒。最终是一次性软提示，包装为需要核验的观察，不是硬命令。

这些是提示目标，不是行为保证。真实 FBR R2 中：

- step46 针对 MIME 变量遮蔽给出具体建议，下一任务 episode45 改名并编译，形成可追踪的修复链；任务本来也看到了编译错误，不能据此证明提醒有净因果收益。
- step28 虽看得到原始 CORS 要求，却加入 credentials 例外；step30 将其标记完成，错误解释还能被写成经验。PMA 并未解决我们研究的 unsupported closure。

Clean 本轮并非无有效行为：持续追踪 Bytes 缺失，拒绝用 limitations 文档代替实现，00:08 的提醒识别出菜单测试计数恒0、指针比较无法证明刷新行为、测试编码了未满足要求。但此前多次是跨多个功能的宽清单；23:46 的建议还留了“记录不可避免的 API 限制”的出口，23:56 又要纠正“写限制文档不等于实现”。这里有建议本身的可误解性，不全是任务 Agent 不听话。

更强的工具只能提供调查可能性，不能保证模型挑中了最能区分正确/错误解释的证据，也不能保证形成建议前一直知道任务最新在做什么。

## 4. 数量与结果边界

- Clean：任务执行89分12秒，263轮；81 file_read、48 code_run、2 file_write、9 intervene、6 wait，无 allow_complete。容量故障后按已授权严重失败停止，无 native verifier 结果；不能记作0分，也不能接受候选。
- Clean 成功 model_output 所报 input 20,921,774/output 26,865；不含独立维护和未记录失败用量，不是完整账单。1次成功压缩交接，11份历史归档。
- PMA R2：48任务调用、47记忆触发/94记忆调用、11次提醒全部送达，42分43秒，6/7阶段、加权0.875。记忆 input 1,387,932/output 8,631；不是同条件成本优越性的证明。

## 5. 建议：借鉴什么，不照搬什么

确定值得修的工程项：容量失败后不能重复添加相同性质唤醒而无法恢复；持续调查必须存在协议完整且可续接的历史退休路径，不能把“未结束”理解成全部原文永不退出活跃上下文。修复应保留当前疑问、已发纠偏、后续反应与根任务，原文仍可检索；不是直接删除近期记忆。实现前还需确定切分点与交接验收。

值得单独判别的机制方向：借鉴 PMA 的短信息路径，让活跃认识承担当前判断，旧调查保留为按需证据；保留同一监察者和通用工具，不直接换成每轮无历史的 PMA 调用。尤其要区分“为了理解旧问题查材料”和“确认刚纠偏后的最新反应”，防止前者长期占据注意力。

未确定：保留多长局部对话、何种信号促成认识更新/重新观察、是否增加第一层公开信息。不能把这些一起堆入一次改动后归因；也不能保证短上下文必定改善智力。下一步先提出相干容量/续接修复设计，再决定一个最小的信息时效候选；本报告不授权实现或真实重跑。

## 原始证据入口

- Clean run：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-active-working-20260912-r1/fyn-2.2.0-roadmap__gmZxpLe/`；使用 agent/monitor/monitor_private/audit 下 dialogue.jsonl、progress.jsonl、history_transforms.jsonl，任务 output.txt 与 result.json。
- PMA run：`bench_runtime/pma_linux_controller/native_fbr_20260912_r2/work/trial/trajectory_memory.json`；配套 task episode 输入与结果见 `PMA_NATIVE_FBR_R2_AUDIT_20260912.md`。
- PMA 源码：`some_research/research_library/02_direct_methods/repositories/yifannnwu__proactive-memory-agent/`，commit `89e5c0d6aadfe531a1aee42fd290d48be89973dd`；memory_enabled_agent.py、memory/memory_agent.py、external/harbor/src/harbor/llms/lite_llm.py。
- Clean 源码：`GenericAgent-main/monitor_agent_core/provider.py` 的 complete/_compact_history/_compact_with_continuation；working_context.py、runtime.py。当前运行与源码身份见 ACTIVE_WORKING_REAL_GATE_20260912.md。
- 人工比较沿用已核对 Fyne 011/014/015 的证据，见 PMA_TO_CLEAN_MONITOR_ALIGNMENT_AUDIT_20260912.md；本轮不宣称重新逐条读取全部人工 FBR。人工工具轮询与模型决策也有延迟，不以理想化“瞬时反应”作为已测基线。
