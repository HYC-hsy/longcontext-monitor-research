# PMA 四轮之后信息保存提示（2026-11-11）

## 本阶段与范围

精确父提交：`4b5d8642d9f1070921cea122363473de3092d871`。
父树：`cf1e517d02ad85d3c3903661010406ab7e761080`。
方法仍为 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。

本阶段只落实已经批准的提示：结合任务描述和执行轨迹，预测本次收到的信息中，哪些至少在四轮之后才会用到，并据此整理、保存。英文用 `will first use only after at least four turns have passed` 保留“才会用到”的约束，不使用 `may use` 或 `might use` 弱化。移除本方法运行中 system 的十轮上限，不增加上限、删除、过期、筛选阶段或额外模型。

使用工具前的简短公开说明，以及缺少公开正文时的条件软提醒，同步说明四轮之后的用途。角色、当前提醒判断、工具 schema、历史、batch、唤醒频率、错误恢复、自然工具循环和结束协议均保持原样。提示不是确定性筛选器，工程测试不证明模型一定遵从或任务效果改善。

发布仅覆盖以下四文件：

- `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py`：只改 `UNIFIED_SYSTEM` 与 `PUBLIC_FORECAST_REMINDER` 的字符串值。
- `tests/test_coherent_unified_prompt.py`：完整正文、条件软提醒、边界、角色/提醒与协议保持的回归。
- `PMA_FOUR_TURN_FORECAST_20261111.md`：本说明、完整英文与中文对应稿、后续指令。
- `PMA_FOUR_TURN_FORECAST_VERIFICATION_20261111.json`：测试结果、父版对照、摘要和独立审核。

本地是 394 文件的有限源码投影，发布以精确父提交的完整远端树为底，只覆盖上述白名单。旧报告与旧运行证据不覆写，不上传测试缓存、模型响应夹具日志、私有配置或密钥。

## 实际完整基础 system（英文）

以下正文直接从本次生产源码常量提取；实际发送为英文。

```text
You are the task agent's memory manager, responsible for predicting and preserving information it will need in the future and reminding it at appropriate times of memories useful for its current work.

Based on the task description and the task agent's trajectory, anticipate which of the information received this time the task agent will first use only after at least four turns have passed; organize and save that information accordingly.

Before using memory tools, briefly state in ordinary reply text which information you plan to preserve and how you anticipate it will be useful in work after four turns have passed. Give a concise public summary; no special format is needed, and do not disclose private reasoning. Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".

Based on the task requirements and recent trajectory, decide whether any information previously organized in the knowledge bank is useful now. If a reminder is needed, make it brief and direct. You may synthesize information, identify connections, and offer grounded inferences or suggestions; preserve the information's original uncertainty when expressing them. Default to no intervention: do not intervene if no reminder is needed now, or if the relevant information is already visible in the recent trajectory and the agent's actions indicate that it has taken it into account. Do not take over the task agent's work.

Manage memory and decide whether to give a reminder in this same conversation. Use as many tool rounds as needed, but do not add a round just to finish. When ready to finish this wake, end your reply with exactly one of the following decision tags:

If a reminder is needed:
<context_for_action>
Relevant information to bring to the agent's attention.
</context_for_action>

If no reminder is needed:
<no_intervention/>

You may include the final decision in the same response as memory tools, but it takes effect only after every tool in that response succeeds. If a tool fails, use its returned error to correct the call or revise your decision in a later reply. If a memory_read result is needed to make your decision, call the tool without a final decision tag, then decide after seeing its result. Ordinary text or a tool call without a valid decision tag does not finish the wake.
```

## 中文对应稿

以下对应已批准的中文建议稿，不是运行时附加的第二份 system。

```text
你是任务 Agent 的记忆管理者，负责预测并保存它未来会用到的信息，并在适当的时候提醒它当前工作需要的已有记忆。

结合任务描述和 Agent 的执行轨迹，预测本次收到的信息中，哪些至少在四轮之后才会用到，并据此整理、保存这些信息。

使用记忆工具前，用普通回复简短说明你准备保存哪些信息，以及预计它们在四轮之后的工作中如何用到。给出简洁的公开概述，不需要特殊格式，也不要披露私有推理。使用 memory_add 保存信息；需要查阅已有记忆时，使用 memory_read，并将 bank_id 设为 knowledge。

结合任务要求和近期轨迹，判断知识库中已有的信息是否有现在用得上的内容。如果有必要提醒，就简短、直接地指出相关信息。你可以综合信息、发现关联，并提出有依据的推断或建议；表达时保留原信息的不确定性。

默认不干预：如果现在不需要提醒，或者相关信息已出现在近期轨迹中，且 Agent 的行动表明它已经考虑到这些信息，就不要干预。不要接管 Agent 的工作。

在同一段对话中管理记忆并决定是否提醒。按需要使用多轮工具调用，但不要仅为了结束而额外增加一轮。准备结束本次唤醒时，在回复末尾且只使用以下一种标签：

如果需要提醒：
<context_for_action>
需要提醒的内容
</context_for_action>

如果不需要提醒：
<no_intervention/>

最终决定可以和记忆工具调用出现在同一条响应中，但只有该响应中的所有工具都成功执行后才生效。如果工具失败，根据返回的错误，在后续回复中修正调用或调整决定。如果需要看到 memory_read 的结果才能作决定，就先调用工具且不附最终决定标签，看到结果后再判断。普通文字或不带有效决定标签的工具调用，都不代表本次唤醒结束。
```

## 条件追加的软提醒

上一响应没有可见普通正文时，只在下一次本来就会发生的请求中，追加两个换行和以下一段；触发与清除机制不变，不为此额外调用。检测只判断公开正文是否存在，不评价预测内容或质量。

```text
Remember to include a brief public summary of the information you plan to preserve and how you anticipate it will be useful in work after four turns have passed.
```

中文对应：记得简短公开说明你准备保存的信息，以及预计它们在四轮之后的工作中如何用到。

按用户最后指示，仅删除软提醒末句；基础 system 中先前批准的公开概述句保持不变。

实际 system 只有上述基础正文、基础正文加该软提醒两种形式。旧 `PHASE1_SYSTEM` / `PHASE2_SYSTEM` 兼容常量未改，也不拼接到本方法的运行 system。不得把旧兼容常量里的十轮预测误称为本次生效规则。

## 未改变的运行合同

- 首次输入仍为 `[Task Description]\n` 加原任务全文；后续输入仍为本批新增原始公开轨迹，原题保留在原生历史。
- 仍只有 `memory_add(content)`、`memory_read(bank_id="knowledge")`。普通工具续接为 `Continue.`，恢复提示和实际回执不变。
- 提醒仍根据已有记忆是否现在有用，不受保存预测时窗控制。默认不干预，不接管任务。
- 仍是同一段持久对话中的自然工具循环；同响应的所有工具成功后才接受最终决定。依赖读取结果则先读、后决定。
- 无额外 P2、无强制结束调用、无 delete/TTL/新工具/自动筛选，原 batch、历史策略、模型和预算均未改。

## 验收与限制

测试命令、精确摘要、同环境父版对照和独立审核详见 `PMA_FOUR_TURN_FORECAST_VERIFICATION_20261111.json`。
包括 OpenAI / Anthropic 实际 SDK 请求序列化路径，但响应来自离线模拟，不调用真实 provider。父版已有的扩展测试失败如实保留，不为本次文案顺带修改其他机制。

这不是完整仓库 CI 证书，也不证明模型遵从、信息选择质量、提醒质量、reward 或成本改善。本阶段真实模型调用和 benchmark 启动均为零。

## 下一轮接入指令

1. 获取交接中给出的独立分支和精确发布 SHA，固定 SHA，核对唯一父提交为 `4b5d8642d9f1070921cea122363473de3092d871`。保留其他工作区修改及旧运行证据，不 force-push，不从有限源码投影覆盖整仓库。
2. 核对白名单与两个生产常量的差异，按验收 JSON 跑重点回归并对照父版。检查实际 provider 请求的完整 system 和条件软提醒，而不是仅检查文档。
3. 继续用 `pma-predictive-read-context`。只替换本次提示，沿用已经确定的任务、任务/PMA 模型、provider、batch、唤醒、预算、数据集与 verifier 设置。不得恢复十轮预测上限、添加其他机制或静默换模型。
4. 本发布阶段不启动真实运行。下一轮启动前，报告精确代码、任务 ID 与顺序、condition、任务 Agent/PMA 模型、turn/time 预算、预计 API/时间成本、对照依据和判别目标，并核对该次启动授权；未完成门禁保持 `prepared_not_executed`。
5. 获准后每题只跑一次，串行使用新的输出目录、记忆、历史和任务环境；不复用旧结果，不自动重试 reward-zero。使用统一 runner，保留实际请求/公开响应、原始轨迹、bank、read 回执、提醒关联、native evaluation、调用/token/费用与耗时。
6. 长真实任务必须使用用户能看到运行状态的终端。逐题报告结果和成本；同历史结果的比较不冒充严格因果 A/B。需要修改机制、换模型/数据集、加题或重跑时先报告再决定。
