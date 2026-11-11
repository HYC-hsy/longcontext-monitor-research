# PMA 按未来用途保留本次信息

## 范围

精确父提交：`ef19e9ac6194261f1fbd24c5d8eba5a111e6c7ae`。
父树：`12e9e9033373f0d4eb3555402f3128b20b64968b`。
方法入口仍为 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。

本次只修改实际生效的 `UNIFIED_SYSTEM` 与 `PUBLIC_FORECAST_REMINDER` 文本值，
把预测对象从未来的问题/决定，改成“本次收到的信息中，哪些可能在接下来 10 轮工作中
用到”，公开概述相应改成“准备保留什么、预想如何用于后续”。知识库提醒明确简短直接。
多轮工具与最终决定协议逐字保留。10 轮仍是预测跨度，不是 TTL 或删除期限。
未增加使用场景模板、删除工具、强制格式、筛选阶段、语义判定器或额外模型调用。

`PHASE1_SYSTEM` / `PHASE2_SYSTEM` 兼容常量、两个工具及 schema、循环、标签解析、
错误恢复、软提醒触发机制、历史、轨迹投影、唤醒频率、模型、预算和任务名单均保持不变。
这是用户批准的提示词候选，不改变研究问题，也不声明方法效果。

发布白名单只有：

- `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py`。
- `tests/test_coherent_unified_prompt.py`。
- 本说明及 `PMA_INFORMATION_FORECAST_VERIFICATION_20261111.json`。

只把白名单覆盖到父提交的完整远端树；本地用于离线测试的 392 文件源码投影不是完整仓库，
不推送其本地历史，不删除远端未物化文件，不发布私有配置、真实轨迹、模型缓存或临时垃圾。

## 实际完整基础 system（英文）

下文直接从最终代码常量提取：

```text
You are the task agent's memory manager, responsible for predicting and preserving information it will need in the future and reminding it at appropriate times of memories useful for its current work.

Based on the task description and the task agent's trajectory, anticipate which of the information received this time the task agent may use in its next 10 turns of work; organize and save information accordingly.

Before using memory tools, briefly state in ordinary reply text which information you plan to preserve and how you anticipate it will be useful in subsequent work. Give a concise public summary; no special format is needed, and do not disclose private reasoning. Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".

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

## 实际完整基础 system（中文对应）

```text
你是任务 Agent 的记忆管理者，负责预测并保留它未来会需要的信息，并适时提醒现在用得上的记忆。

结合任务描述和任务 Agent 的执行轨迹，预想本次收到的信息中，哪些可能会在它接下来的 10 轮工作中用到，据此整理并保存信息。

使用记忆工具前，用普通回复简短说明你准备保留哪些信息，以及预想这些信息会如何用于后续工作。给出简洁的公开概述，不需要特殊格式，也不要披露私有推理。使用 memory_add 保存信息；需要查阅已有记忆时，使用 memory_read，并将 bank_id 设为 "knowledge"。

结合任务要求和近期轨迹，判断知识库中之前整理的信息是否有现在用得上的。如果有必要提醒，就简短、直接地提醒。你可以综合信息、发现关联，并提出有依据的推断或建议；表达时保留原信息的不确定性。默认不干预：如果现在不需要提醒，或者相关信息已出现在近期轨迹中，且 Agent 的行动表明它已经考虑到这些信息，就不要干预。不要接管任务 Agent 的工作。

在同一段对话中管理记忆并决定是否提醒。按需要使用多轮工具调用，但不要仅为了结束而额外增加一轮。准备结束本次唤醒时，在回复末尾且只使用以下一种决定标签：

如果需要提醒：
<context_for_action>
需要提醒 Agent 的相关信息。
</context_for_action>

如果不需要提醒：
<no_intervention/>

最终决定可以和记忆工具调用出现在同一条响应中，但只有该响应中的所有工具都成功执行后才生效。如果工具失败，根据返回的错误，在后续回复中修正调用或调整决定。如果需要看到 memory_read 的结果才能作决定，就先调用工具且不附最终决定标签，看到结果后再判断。普通文字或不带有效决定标签的工具调用，都不代表本次唤醒结束。
```

## 条件附加的公开概述软提醒

上一响应没有可见普通正文时，仅在下一次本来就会发生的请求中，给基础 system
追加两个换行和下面一段。不为缺少概述单独增加调用，不叠加多份，不校验语义质量。
只有“OK”也算存在公开正文，不能据此声称模型完成了有效预想。

```text
Remember to include a brief public summary of the information you plan to preserve and how you anticipate it will be useful in subsequent work. Do not disclose private reasoning.
```

中文对应：记得简短公开说明你准备保留的信息，以及预想这些信息会如何用于后续工作。
不要披露私有推理。

实际 system 仅有完整基础正文、基础正文加该软提醒两个形态。原 P1/P2 兼容常量
不会拼接进本方法的 system；旧方法仍保持其原提示。

## 输入、工具与结束协议

- 首次 user prompt 是 `[Task Description]\n` 加原始任务全文；后续唤醒只发送本次新增
  原始公开轨迹。原题保留在原生会话历史中，不把“本次信息”改成重发所有历史。
- 普通工具续接仍为 `Continue.`；格式恢复与工具恢复文本逐字保持原样。
- `memory_add(content)` 与 `memory_read(bank_id="knowledge")` 原样；无 delete、TTL 或新工具。
- 可以多轮调用，同响应全工具成功才接受末尾决定；部分失败拒绝该响应的决定。
  依赖 read 结果则先读后决定；实际回执与 provider 原生历史持续保留。
- 不强制额外结束调用，不恢复独立 P2，不把私有 reasoning 转成公开概述。

## 离线验收与限制

完整命令、计数、同环境父版对照、失败项、哈希和独立审查见
`PMA_INFORMATION_FORECAST_VERIFICATION_20261111.json`。测试使用已有依赖与模拟响应，
包括真实 SDK/provider 序列化路径；不调用真实模型或 benchmark。
生产文件遮蔽上述两个常量值后，AST 与精确父版本一致；结束协议摘要也与父版一致。

扩展测试并非全绿：保留父版已有失败，不在本轮文案范围顺带修复历史断言、夹具或
未物化的无关文件。区分通过、失败与未运行，不把重点回归通过说成完整仓库 CI 通过。
离线结果不能证明模型遵从、预测质量、提醒质量、reward 或成本改善。

## 开发线程接入与后续运行指令

1. 从交接消息给出的独立分支获取精确发布 SHA，固定该 SHA，核对唯一父提交是
   `ef19e9ac6194261f1fbd24c5d8eba5a111e6c7ae`。不使用可能变化的分支 HEAD 代替固定版本。
   保留其他工作区改动，不 force-push，不覆盖旧运行证据。
2. 核对本说明的四文件白名单与 production diff，执行验收 JSON 的重点/扩展命令，
   在同环境对照父版。复核实际 provider 请求的完整 system、条件软提醒、首次原题、
   后续本批轨迹、工具 schema、实际回执、历史顺序与决定标签，而非只看文档或常量。
3. 沿用现有 `pma-predictive-read-context` 入口、单一统一循环、既定 provider/model、
   唤醒与预算设置；不增加 P2、删改工具、自动过期、模板筛选或其他机制。
4. 本发布阶段只到离线接入核对，不自动启动真实任务。真实启动前，按仓库门禁报告
   精确代码、任务 ID、condition、任务 Agent/PMA 模型、turn/time 预算、预计 API/时间成本、
   对照与判别目标，并核对该次用户启动授权。缺少任一必要确认时停在 prepared_not_executed。
5. 后续如按既有五题批次获准，沿用原顺序：`kv-store-grpc`、`reshard-c4-data`、
   `rstan-to-pystan`、`largest-eigenval`、`filter-js-from-html`。任务模型 `claude-opus-4-8`，
   单一 PMA 模型 `claude-opus-5`，以已核对的真实 provider 配置为准，不静默替换。
   保留原 Harbor/数据集精确版本、每 8 轮唤醒、10 轮预测、uncapped agent/turn 和
   official verifier 策略；本说明不新授予预算或真实运行权限。
6. 获准后使用统一 runner，每题一次、串行，新空记忆/历史/环境/run ID，不复用旧结果，
   不自动重试 reward-zero，不用短夹具代替完整真实任务：

```bash
python -m experiment_runner run --config <verified-private-config.json> --method pma-predictive-read-context --task kv-store-grpc --task reshard-c4-data --task rstan-to-pystan --task largest-eigenval --task filter-js-from-html --output <new-output-directory>
```

7. 启动前检查 Docker Engine、源码/配置身份、数据集、评价环境和真正用户可见的运行终端。
   保存实际请求/公开响应、原始轨迹、bank、read 回执、提醒与后续 Task provider attempt
   的关联、native evaluation、调用/token/费用与耗时。公共归档不含密钥、私有配置或
   原生私有推理。逐题回报 reward/完成类别和成本，同历史结果比较不冒充严格因果 A/B。
   机制修复、模型/数据集改变、额外任务或重跑均需停下报告，再决定。
