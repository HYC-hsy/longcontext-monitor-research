# PMA 连贯融合提示词

## 范围与基线

精确父提交：`352280922aa2b3746bad857452d471e465a5b4a6`。
方法入口仍为 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。

本次唯一生产改动是 `read_context_predictive_memory_agent.py` 中实际发送的
`UNIFIED_SYSTEM` 文案：从两个角色段落加协议的拼接，改成连贯的单一记忆管理职责。
`PHASE1_SYSTEM` 和导入的 `PHASE2_SYSTEM` 作为兼容常量保持原样；它们不再被拼接成
该方法的实际 system。旧双阶段方法、P2 逻辑、工具 schema、循环、标签解析、错误恢复、
公开摘要软提醒、历史、轨迹投影、唤醒频率、模型参数、任务批次和运行配置都没有修改。
没有增加使用场景筛选、事实/推测分栏、语义 gate 或新机制。

文件范围：

- 生产：`method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py`。
- 测试：`tests/test_coherent_unified_prompt.py` 新增精确文案、父版本 AST 不变量和实际双 provider 请求测试。
- 测试：`tests/test_simple_predictive_prompts.py` 将旧的拼接断言换成独立统一正文断言；原 P1、P2 全文断言仍保留。
- 本说明及 `PMA_COHERENT_PROMPT_VERIFICATION_20261111.json`。

只允许将这些明确文件覆盖到父提交的完整远端树。测试用本地源码投影不是完整仓库，
其本地 Git 历史不得推送。私有配置、真实轨迹、模型响应缓存和测试生成垃圾均不发布。

## 实际完整基础 system（英文）

以下直接从最终 Python 常量提取，不是摘要或另拟版本：

```text
You are the task agent's memory manager, responsible for preserving information it may need next and reminding it at appropriate times when that information can help its current work.

Based on the task description and the task agent's trajectory, anticipate the problems it may encounter, the decisions it may need to make, and the information it will need over the next 10 turns; organize and save information accordingly. At the same time, consider the task requirements and recent trajectory to decide whether any information already in memory needs to be brought to the agent's attention now.

Before using memory tools, briefly state in ordinary reply text the problems or decisions you anticipate and the information you plan to preserve for them. Give a concise public summary; no special format is needed, and do not disclose private reasoning. Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".

When giving a reminder, you may synthesize information, identify connections, and offer grounded inferences or suggestions; preserve the information's original uncertainty when expressing them. Default to no intervention: do not intervene if no reminder is needed now, or if the relevant information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account. Do not take over the task agent's work.

Manage memory and decide whether to give a reminder in this same conversation. Use as many tool rounds as needed, but do not add a round just to finish. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If a reminder is needed:
<context_for_action>
Relevant information to bring to the agent's attention.
</context_for_action>

If no reminder is needed:
<no_intervention/>

You may include the final decision in the same response as memory tools, but it takes effect only after every tool in that response succeeds. If a tool fails, use its returned error to correct the call or revise your decision in a later reply. If a memory_read result is needed to make your decision, call the tool without a final decision tag, then decide after seeing its result. Ordinary text or a tool call without a valid decision tag does not finish the wake.
```

## 实际完整基础 system（中文对应）

```text
你是任务 Agent 的记忆管理者，负责保留它接下来可能需要的信息，并在这些信息有助于当前工作时适时提醒它。

结合任务描述和任务 Agent 的执行轨迹，预想未来 10 轮中它可能遇到的问题、需要作出的决定，以及届时所需的信息，据此整理并保存信息。同时，结合任务要求和近期轨迹，判断已有记忆中是否有现在需要提醒 Agent 的信息。

使用记忆工具前，用普通回复简短说明你预想的问题或决定，以及准备为此保留的信息。给出简洁的公开概述，不需要特殊格式，也不要披露私有推理。使用 memory_add 保存信息；需要查阅已有记忆时，使用 memory_read，并将 bank_id 设为 "knowledge"。

提醒时，你可以综合信息、发现关联，并提出有依据的推断或建议；表达时保留原信息的不确定性。默认不干预：如果现在不需要提醒，或者相关信息已出现在近期轨迹中，且 Agent 的行动表明它已经考虑到这些信息，就不要干预。不要接管任务 Agent 的工作。

在同一段对话中管理记忆并决定是否提醒。按需要使用多轮工具调用，但不要仅为了结束而额外增加一轮。准备结束本次唤醒时，在回复末尾且只使用以下一种决定标签：

如果需要提醒：
<context_for_action>
需要提醒 Agent 的相关信息。
</context_for_action>

如果不需要提醒：
<no_intervention/>

最终决定可以和记忆工具调用出现在同一条响应中，但只有该响应中的所有工具都成功执行后才生效。如果工具失败，根据返回的错误，在后续回复中修正调用或调整决定。如果需要看到 memory_read 的结果才能作决定，就先调用工具且不附最终决定标签，看到结果后再判断。普通文字或不带有效决定标签的工具调用，都不代表本次唤醒结束。
```

## 条件附加 system 与动态 prompt

保留已有软提醒。上一条响应没有可见普通正文时，仅在下一次本来就会发生的请求的
基础 system 后面附加两个换行和下文；不会因为摘要缺失单独增加一次调用，也不会叠加多份：

```text
Remember to include a brief public summary of the upcoming problems or decisions you anticipate and the information you plan to preserve. Do not disclose private reasoning.
```

对应中文：记得简短公开说明你预想的后续问题或决定，以及准备为此保留的信息。
不要披露私有推理。

因此，实际 system 仅有上面的完整基础正文，或基础正文加这一段两个形态。
不把原 P1/P2 常量、任务文本、工具回执或私有 thinking 拼到 system 中。

动态 user prompt 保持原样：首次是 `[Task Description]\n` 加原始任务全文；
后续唤醒是本次新增原始公开轨迹；成功工具但尚未决定时是 `Continue.`。
格式或工具恢复分别使用现有文本，不把这些 user prompt 误称为 system：

```text
No valid final decision was received. Continue managing memory if needed, or end with exactly one nonempty <context_for_action>...</context_for_action> or <no_intervention/>. Do not repeat successful memory writes.
```

```text
One or more memory tools failed. The decision in that response was not accepted. Review the actual tool receipts, correct the failed calls if needed, and decide again. Do not repeat successful memory writes.
```

对应中文：未收到有效最终决定时，按需继续管理记忆，或以唯一非空提醒标签/不干预标签
结束，不重复已经成功的记忆写入。工具失败时，同响应决定未被接受；检查真实回执，
按需修正失败调用并再次决定，不重复已经成功的写入。恢复次数、错误分类及失败停止逻辑
全都保持父版本原样。

## 离线验收

精确命令、计数、共享失败和哈希见 `PMA_COHERENT_PROMPT_VERIFICATION_20261111.json`。
测试输入源投影的 389 个文件逐一匹配父提交 Git blob；测试仅使用现有依赖和模拟 provider。
排除 `UNIFIED_SYSTEM` 赋值右侧后，整个生产文件 AST 与父提交完全一致。

新增测试不只检查默认字符串，还检查真实 OpenAI SDK MockTransport 请求及 Harbor/LiteLLM
到 Anthropic 的实际序列化请求，包含完整 system、条件软提醒、原任务、原始新增轨迹、
`Continue.`、两个原工具、read 回执、跨 wake 历史，以及无额外 P2。
已有回归覆盖同响应全工具成功后接受标签、部分失败拒绝标签、read 依赖先读后决定、
格式恢复、有界错误恢复、不重放成功写入、长工具链和 worker 生命周期。

针对性回归 **262 passed**。独立审查另复跑 **110 passed**。
候选扩展 **447 passed / 140 subtests / 12 failed**；精确父版本扩展
**443 passed / 140 subtests / 12 failed**。3 个 Pydantic ReadOnly 警告保留。

扩展测试并非全绿。与同环境精确父版本相比，保留相同的 12 个既有失败，无新增失败。
这些失败涉及旧断言、未设置 PMA transport 的旧夹具、投影未包含的历史脚本/依赖。
不得跳过或掩盖这些失败，也不在本次只改文案的范围中顺带修复它们。
测试通过只证明工程契约和接线，不证明模型会遵从新文案、预测/提醒质量提高、成本下降或 reward 改善。
本次真实模型调用 0，真实 benchmark 任务 0，未执行 Docker/native 新认证。

## 交开发线程的指令

1. 从本分支取得父提交为 `352280922aa2b3746bad857452d471e465a5b4a6` 的已核对发布
   commit，使用交接消息给出的完整 SHA 固定工作树。不要用之后可能变化的 branch HEAD
   替代该 SHA。保留其他未提交改动，不 force-push，不覆盖历史。
2. 核对相对父提交的变更白名单。只应有上述一个生产文案文件、两个测试和两份说明/验收文件。
   保留 `pma-predictive-read-context` 入口及既定模型、provider、轨迹、唤醒设置、任务批次和预算。
   不另加新阶段、工具、筛选、标签、配置开关或 P2。
3. 使用已有依赖运行验收 JSON 中的 focused/extended 命令；在相同环境运行精确父版本作对照。
   区分通过、新失败、共享既有失败和未运行项目。新 AST 测试必须通过。
4. 从实际发送路径核对完整基础 system，以及缺少普通公开正文后下一请求的软提醒形态。
   同时核对原始任务/新增轨迹 user prompt、tool schema、回执、调用顺序和结束协议；不要
   仅凭常量或文档断言已生效。不要将私有 thinking 转成公开回复。
5. 离线接入复核后，为后续五题完整真实比较准备 manifest，但先执行仓库启动门禁，
   向用户报告确切 commit、任务、condition、模型、预算、预计费用与判别目标，并取得
   针对本次真实启动的必要确认。没有确认就停在 prepared_not_executed；本发布不自动运行。
6. 确认后沿用原五题顺序，每题一次、串行：`kv-store-grpc`、`reshard-c4-data`、
   `rstan-to-pystan`、`largest-eigenval`、`filter-js-from-html`。Task 模型为
   `claude-opus-4-8`，单一 PMA 模型为 `claude-opus-5`，通过实际 provider 配置核对，
   不静默替换模型。保持同一数据集/Harbor 的既定精确版本、每 8 轮唤醒及 10 轮预测，
   保留已有 uncapped agent/turn 和 official verifier 策略，不新增限额或改变任务批次。
   PMA 只有本分支的统一循环，不再运行额外 P2。
7. 使用统一 runner，不改用旧独立 launcher。每题用新空记忆、新历史、新环境、新 run ID，
   不复用旧结果，不重试 reward-zero 结果，不以短夹具代替完整真实任务：

```bash
python -m experiment_runner run --config <verified-private-config.json> --method pma-predictive-read-context --task kv-store-grpc --task reshard-c4-data --task rstan-to-pystan --task largest-eigenval --task filter-js-from-html --output <new-output-directory>
```

8. 启动前核对 Docker Engine、源码/配置身份、数据集与评价环境，以及真正用户可见的
   运行终端。保留实际 Task/PMA 请求和公开响应、原始轨迹、bank、增查回执、提醒与随后
   真实 Task provider attempt 的关联、native evaluation 和成本/token 证据。逐题评价并
   仅清理本题拥有的资源。公共归档不含密钥、私有配置或原生私有推理。
9. 回报每题 reward、完成/错误类别、调用/token/可得费用及耗时，并与相应旧五题结果逐题
   对照。不能把单次历史比较说成严格因果 A/B，不根据工程测试声称新提示效果成立。
   任何超出已确认范围的机制修复、模型/数据集变化或重新运行，都需停下报告再决定。
