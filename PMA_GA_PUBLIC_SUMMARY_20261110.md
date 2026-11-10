# P1 预测提示、原生历史与公开摘要记录

## 范围与交付状态

- 固定工程父提交：`4964b7dc88135ba2ab527d4aa9bb521cd7a2cb8a`。
- 仓库：`HYC-hsy/longcontext-monitor-research`。
- 方法仍为 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。
- 本阶段完成离线实现与审查，独立交付分支为 `pma-ga-public-summary-20261110`。发布必须以真实 4964 为父提交，不能使用本地投影的 Git 祖先；远端提交状态与确切 SHA 以交付核验结果为准。
- 没有真实模型调用，没有用户线程或任务数据，没有修改实际模型 profile。测试中的密钥、签名、加密数据和摘要均为合成夹具。

## 完整 P1 提示

```text
You organize information from the task execution.

Based on the task description and the task agent's trajectory, first anticipate the problems the task agent may encounter or the decisions it may need to make over the next 10 turns, and what information it will need then; organize and save that information accordingly.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".

Briefly explain your forecast and the information you chose to save or look up. If no action is needed, briefly say why. Give a short explanation for the user, not private internal reasoning.
```

主句对应用户选择的“根据任务描述和任务 Agent 的轨迹，先预想任务 Agent 在接下来 10 轮中可能遇到的问题或需要做出的决定，以及届时会需要哪些信息；然后据此整理并保存这些信息”。公开说明没有固定 XML/JSON 格式，没有解析门禁，没有要求与工具调用必须同回复。没有说明时不补问、不阻止保存、不增加模型轮次。

read-context 独立深拷贝的 `memory_add` 描述改为 `Save information in the knowledge memory bank.`，移除旧筛选提示，参数和执行不变；其他候选的原 schema 不变。

## 复用 GA 的内容与不复制的内容

以下为父提交源行：

- `GenericAgent-main/llmcore.py:1521` 将 provider 原生响应块保存在同一会话历史中。
- `read_context_predictive_memory_agent.py:176–184` 已保留 P1 原生 thinking blocks / Responses items，`:109–120` 负责回传。
- `context_predictive_memory_agent.py:56–66` 已单独保留 P2 响应；`ga_context_history.py:190–204` 回传对应原生状态。
- `GenericAgent-main/ga.py:591–599` 从公开正文读取 summary，或记录工具动作短述。
- `GenericAgent-main/llmcore.py:1748–1756` 有从 thinking 首行合成正文 summary 的历史逻辑。本次没有调用、移植或仿造这段逻辑。

原生状态与公开摘要是两件事。thinking/signature、redacted blocks 和 Responses reasoning items 仍按现有接口在各自阶段内原样续接；不转换为普通正文、不解码签名或加密数据。新的公开摘要字段仅用于审计，没有单独拼入任何 prompt，更没有将 P1 摘要自动放入 P2。provider 原生 reasoning item 原本包含的 summary 随该 item 在同阶段原样回传，未额外复制。

GA 源码、历史函数、P2 提示和实现、W8、首次调用、预算、模型、调度、read/error 续轮与 add-only 行为均未改变。P1 可执行 AST 除提示字符串和工具描述外与父版一致。

## 正式公开摘要的最小支持

`ResponsesMemoryLLM` 仅接受 Responses API 明确的 `output[type="reasoning"].summary[type="summary_text"].text`。其他类型、错误类型文本、`reasoning_content`、thinking、signature、encrypted_content 不作为公开摘要来源。

可选 profile 字段：

```json
{"request_public_summary": true}
```

该字段默认省略或为 `false`，默认请求与父版一致。仅显式设为 `true` 时，在现有 Responses 请求中增加 `reasoning.summary="auto"`。布尔值以外的值被拒绝；该开关不支持 Claude/Messages 路由，不能无声忽略后声称已开启。未修改任何真实 profile，也未修改模型名称、effort、max_tokens 或 encrypted_content 请求配置。

实际调用后，`memory_response.jsonl` 的 `public_reasoning_summary` 仅包含：

- `request_status`：`requested` 或 `not_requested`。
- `result_status`：`returned` 或 `not_returned`。
- `source`：`openai.responses.reasoning.summary_text`，未映射适配器为 `null`。
- `texts`：仅白名单内实际返回的公开摘要文本，缺失时为空数组。

未请求也可能收到 provider 主动返回的正式摘要，所以请求状态与结果状态分开。空或缺失摘要不触发任何恢复调用。正文仍记录在原有 `content` 中；摘要不会被伪装成正文或已执行的 memory 操作。

不支持参数而返回 HTTP 错误时，原失败路径照常中止；不会删除参数重试以伪造成功。失败调用只有原有 transport 错误记录，不会捏造 summary/response 记录。开关开启不等于已验证网关支持。

## Provider 与网关边界

截至本次查阅，OpenAI 官方文档描述 `reasoning.summary="auto"` 和 `summary_text`，支持依模型而异。当前文档说明无状态模式默认包含 encrypted_content，因此没有把缺少 `include` 当作 bug，也没有添加该参数。

- https://developers.openai.com/api/docs/guides/reasoning

Anthropic 官方文档描述支持模型的 `thinking: {"type":"adaptive","display":"summarized"}`，以及 Opus5 默认 omitted 的行为。但本项目固定网关的映射、透传和返回来源尚未实测。本次不请求 Claude display、不把普通 thinking_blocks 的文本改称公开摘要。Claude 没有已映射的正式摘要时，仅记录自然公开正文和摘要未返回状态。

- https://platform.claude.com/docs/en/build-with-claude/thinking

合成接口通过不能证明实际网关支持、模型遵循提示、每轮都有可读分析或实验效果改善。未来真实调用必须沿用项目独立启动确认与预算要求，不得因本次实现自动启动。

## 改动文件

生产代码位于 `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/`：

1. `vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py`：预测提示、自然公开说明、read-context 的工具描述。
2. `responses_memory_llm.py`：默认关闭的显式摘要请求、正式 summary_text 白名单投影。
3. `pma_model_profile.py`：开关类型和支持路由校验。
4. `worker_main.py`：在现有响应审计内记录经过字段白名单投影的公开摘要及状态。

测试：新增 `tests/test_predictive_public_summary.py`；更新 `tests/test_simple_predictive_prompts.py`、`tests/test_predictive_memory_read.py` 的提示合同。生产代码加测试共 265 行增删，低于单步 600 行限制。

## 离线验收

- 独立审查没有可操作问题；独立重跑的针对性检查：**44 passed**。
- 本版完整选定回归范围：**168 passed、15 subtests passed、5 failed**。
- 未修改 4964 投影在同环境重跑：**154 passed、15 subtests passed、相同 5 failed**。
- 新增 14 项用例覆盖：默认/显式摘要请求、返回/缺失、白名单、真实 SDK HTTP 请求解析、P1/P2 独立续接、签名和 redacted block 原样回传、裁剪下原生 reasoning item 不变、日志排除私有数据、不支持的请求明确失败。
- 5 项既有失败均在 `test_continuous_integrity_repairs.py`：4 项 AST 测试装载遗漏 `_history_bytes`；1 项旧 source-files 断言未包含已有 Responses 适配器。没有修改这些测试或降低断言，不能声称完整全绿。

针对性命令：

```bash
python -m pytest -q -p no:cacheprovider tests/test_predictive_public_summary.py tests/test_simple_predictive_prompts.py tests/test_predictive_visible_basis.py tests/test_predictive_memory_read_integration.py
```

回归命令：

```bash
STAGE=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
python -m pytest -q -p no:cacheprovider tests "$STAGE/test_model4_transport.py" experiment_runner/test_context_predictive.py
```

测试路径需包含当前仓库、GA、stage、vendor memory_agent 和 vendor Harbor。实测使用 Python 3.12、pytest 9.2.0、OpenAI SDK 3.46.0、LiteLLM 1.108.1 与现有 Harbor 分发元数据；`LITELLM_LOCAL_MODEL_COST_MAP=True` 使用本地价格表。新增接口测试禁止外部网络连接，全部响应由合成 transport 提供。
