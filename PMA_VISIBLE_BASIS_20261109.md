# P1 可见整理依据：最小改动版

基线固定为 `98b166aa747da9f5b7e9f0f9d677c25d77d3611a`。
方法仍为 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。
本版不包含此前 think 多轮补丁，也不是在它上面继续叠加。

## 核查结论与范围

GA 的公开行动说明、模型的私有推理、工具循环是三件不同的事。
GA 的提示和工作历史使用公开 summary，但 P1 不需要复刻该标签。
GA 某些兼容路径从 thinking 合成 summary，本版不采用该做法。
P1 原有 Claude adaptive / GPT high reasoning 设置保持原样；公开正文为空不表示没有推理。

98b 的 `worker_main.install_transport_audit` 已记录每次响应的公开 `content`
和原生 `tool_calls`。核心缺口可用同一次响应中的简短自然说明补足，无须增加模型调用。
另一个确定的日志缺口是：成功 add-only 后直接进入 P2，其工具回执可能要到下次 P1
请求才写入历史日志；最后一次唤醒没有下一次时，缺少直接对应 call ID 的持久回执。

因此生产代码只改两处：

1. `read_context_predictive_memory_agent.py` 的 `PHASE1_SYSTEM` 追加一段公开说明要求。
   除该字符串外，P1 文件 AST 与固定基线一致。
2. `worker_main.py` 复用既有审计写入函数，在实际 `_record_p1_response` 返回或异常时，
   立即保存它刚产生的原生工具回执。通过 `call_sequence` 和 `tool_use_id` 对齐请求、
   公开说明、工具调用和实际结果。不执行额外工具，不向模型注入日志。

P2、两个工具及其参数、原题与原轨迹输入、初始调用、每 8 个新步骤的唤醒、8 步观察窗、
未来 10 轮的信息选择目标、GA 的 30000 / 0.6 / 5 历史配置均未改动。
成功 add-only 仍直接进入 P2。读取或错误后的条件续轮沿用基线，不强制每次写入后再调模型。

## 本次完整 P1 system 提示

```text
You organize information from the task execution.

Based on the task description and the task agent's trajectory, organize and save information expected to be useful within the next 10 turns. When organizing information, preserve its original meaning and degree of certainty.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".

In the same response as your tool calls, briefly explain in ordinary text what you are saving or looking up and why it is useful. If no action is needed, briefly say why. Give only a short explanation for the user, not private internal reasoning.
```

对应中文翻译：

> 你负责整理任务执行中的信息。
>
> 根据任务描述和任务 Agent 的执行轨迹，整理并保存预计在未来 10 轮内有用的信息。
> 整理时保留信息原本的含义和确定程度。
>
> 使用 memory_add 保存信息。需要查阅已经保存的信息时，使用 memory_read，
> 并将 bank_id 设为 "knowledge"。
>
> 在调用工具的同一次回复中，用普通文字简短说明你要保存或查阅什么，以及它为什么有用。
> 如果不需要采取行动，也简短说明原因。只给用户一段简短说明，不输出私有内部推理。

没有 `<summary>` 标签、固定字段、专门思考工具或强制结束格式。
动态输入仍是原有首次 `[Task Description]` 加完整原题、后续原轨迹，以及已有工具续轮的
`Continue.`。P2 system 逐字保持基线，不追加公开说明要求。

## 如何查看，如何解释缺失

运行后的 `host_private/archive/` 中：

- `memory_payload.jsonl`：每次实际请求，包括完整 system/prompt 和允许归档的历史。
- `memory_response.jsonl`：该次实际公开正文、原生工具 ID/参数。按 `call_sequence` 对齐。
- **新增** `memory_tool_results.jsonl`：当次实际生成的 `tool_result`，包括对应
  `tool_use_id`、success/error、memory_id，以及实际 read 快照。
- `memory_transport.jsonl`：原有传输状态。传输完成不能替代工具执行成功。

`content` 为空/null 时就是“未提供公开说明”，不补写、不从私有字段提取、也不为此重试。
正文存在仅表示模型说过这些话，不证明说明正确或信息选择有效。
`recording_error_type` 非空表示响应记录/执行阶段发生异常；没有工具回执时不能反推成功。
工具的 `success=false` 是实际错误，不可把“我将保存”当作保存成功。
P2 失败或取消时，已经执行的 add 和它的回执仍保留。

这些是运行时逐次落盘的**归档记录，不是新建实时聊天前端**。现有归档查看方式需同时读取
新增回执文件；本轮没有改旧归档导出器或自动把日志上传到公开位置。
归档可能含原任务和知识库原文，仍属私有运行材料。对外分享须沿用既有脱敏流程，不能直接
公开整个目录。provider 私有 reasoning、签名、加密块不作为公开依据写入这些记录。

## 验证

没有调用真实模型，没有运行 Docker 真实任务，没有更改模型/窗口/评价配置。

- 本轮定向：**18 passed**，其中 15 个新增测试和 3 个既有提示测试。
- 扩展核心回归：**154 passed、15 subtests passed、5 failed**。
- 同环境固定基线对照：**139 passed、15 subtests passed、相同 5 failed**。
- 5 个既存失败均在 `test_continuous_integrity_repairs.py`：4 个 AST 抽取夹具漏加载
  基线已有的 `_history_bytes`；另 1 个来源清单断言漏掉基线已有的
  `responses_memory_llm.py`。本轮没有改这些旧测试，不声称全库绿灯。
- P1 AST 除 system 字符串外一致；改动差异与 Python 编译检查通过。
- 更广的 runner/evaluation 试跑曾受稀疏材料缺项和旧 profile fixture 影响，
  不作为本轮通过的验收范围；完整仓库、Windows 和真实任务未验证。

新增测试覆盖：Claude 的实际 LiteLLM/Anthropic 请求响应转换，OpenAI 的实际 SDK
序列化和 MockTransport；正文与工具同响应、空正文、不行动、原有 read/add 续轮、
混合成功/失败调用、非法调用、传输失败、P2 失败/取消、审计写入失败。
合成 provider 回应只证明接线与归档，不证明真实模型遵从提示。

在已有项目测试依赖的环境中复现（需安装 Harbor 分发元数据及 LiteLLM/OpenAI 依赖）：

```bash
STAGE=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$STAGE/vendor/pma_89e5c0d/src:$STAGE/vendor/pma_89e5c0d/external/harbor/src:$STAGE:GenericAgent-main:experiment_runner:.:$PYTHONPATH"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q tests/test_predictive_visible_basis.py tests/test_simple_predictive_prompts.py
python -m pytest -q tests "$STAGE/test_model4_transport.py" experiment_runner/test_context_predictive.py
python -m compileall -q tests/test_predictive_visible_basis.py tests/test_simple_predictive_prompts.py "$STAGE/worker_main.py" "$STAGE/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py"
```

`LITELLM_LOCAL_MODEL_COST_MAP=True` 是离线测试的明确前提，避免 LiteLLM 初始化下载价格表；
新增测试另阻断网络连接，只允许本地 MockTransport，不依赖别的测试预热缓存。

## 已知限制与停止点

- 提示不能保证模型每次提供公开说明；旧日志缺失的说明无法补造。
- 公开说明会增加输出 token 和后续历史文本，虽然没有新增调用，也不是零成本变化。
- 新回执日志沿用既有审计的 fail-closed 策略。若磁盘写入失败，可能在 add 已成功后
  终止 P1，不进入 P2；不会自动重做该 add。不能绝对声称所有异常行为不变。
- 进程在实际写 bank 后、持久回执前崩溃，仍可能留下未知状态；这不是事务性审计系统。
- 不是完整内部思维展示，也不保证整理质量或任务收益。未合并主分支；任何真实启动仍需
  单独确认，不能把本工程提交当作实验授权。
