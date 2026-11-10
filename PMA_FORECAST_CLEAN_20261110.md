# P1 预测提示重整：只保留角色、预测主句和工具说明

## 版本与范围

- 仓库：`HYC-hsy/longcontext-monitor-research`。
- 新独立分支：`pma-forecast-clean-20261110`。
- 真实工程父提交：`4964b7dc88135ba2ab527d4aa9bb521cd7a2cb8a`，树为 `c2b8546cd7581976cedad15b40bcf3a7449d39cf`。
- 从 4964 重新形成最小版本，不继承 `dd31718c9fa42d8b429f5f178021a176a746cc38` 的 Responses 摘要开关、字段投影、审计新增代码或开关测试。旧分支不删除、不改写。
- 本文取代旧文档中对本版本 P1 提示的描述。旧文档作为历史版本记录保留，不是本版本运行输入。
- 方法仍为 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。

## 完整 P1 系统提示

实际英文常量：

```text
You are a memory manager for the task agent.

Based on the task description and the task agent's trajectory, first anticipate the problems the task agent may encounter or the decisions it may need to make over the next 10 turns, and what information it will need then; organize and save that information accordingly.

Use memory_add to save information. When you need to look up information already saved, use memory_read with bank_id="knowledge".
```

完整中文对照：

```text
你是任务 Agent 的记忆管理者。

根据任务描述和任务 Agent 的执行轨迹，先预想任务 Agent 在接下来 10 轮中可能遇到的问题或需要做出的决定，以及届时会需要哪些信息；然后据此整理并保存这些信息。

使用 memory_add 保存信息。需要查阅已经保存的信息时，使用 memory_read，并将 bank_id 设为 "knowledge"。
```

没有额外公开解释段，没有精简、准确性或保真度附加要求，没有预测输出格式、解析门禁、专门思考工具或额外模型阶段。

## P1 的工具与动态输入

- `memory_add`：`Save information in the knowledge memory bank.`
  - 中文：将信息保存到 knowledge 记忆库。
  - 必填字符串参数 `content`：`Information to save.`，即“要保存的信息”。
- `memory_read`：`Read all information currently saved in the knowledge memory bank.`
  - 中文：读取 knowledge 记忆库当前保存的全部信息。
  - 必填字符串参数 `bank_id`，唯一允许值为 `knowledge`。说明为 `Memory bank to read. Use knowledge.`，即“要读取的记忆库，使用 knowledge”。
- 两工具继续拒绝额外参数；参数、工具数量和执行逻辑均不变。
- 仅覆盖 read-context 独立深拷贝的 add 工具说明，去掉旧的未来 10 轮筛选说法，避免与新预测主句重复。其他候选的共享工具说明不变。
- 首次用户输入仍为 `[Task Description]\n{原始任务全文}`；后续为原有新增轨迹；已有条件续轮仍使用 `Continue.`（继续）。未增加或重写动态输入。

## P2 完整中文对照（未改）

以下翻译对应父版保留的 P2 system，不进入模型请求：

```text
你通过在适当时机提醒任务 Agent 注意记忆中的相关信息，帮助它完成任务。

结合任务要求和任务 Agent 最近的执行轨迹查看记忆库，判断其中是否有信息能够帮助它当前的工作。你可以综合信息、识别联系，并提出有依据的推断或建议；表达时保留信息原本的不确定性。

默认不干预。如果当前不需要提醒，或者相关信息已经出现在近期轨迹中，并且任务 Agent 的行动表明它已经考虑到了这些信息，就不要干预。不要接管任务 Agent 的工作。

需要提醒时，输出：
<context_for_action>
需要提请任务 Agent 注意的相关信息。
</context_for_action>

否则，输出：
<no_intervention/>
```

P2 动态输入仍包含当前步数、刚更新的完整记忆库、原任务与近期轨迹，以及是否需要现在提醒的原有请求。P2 不带工具。

## 保持不变的实现

仅一个生产文件改动：

`method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py`

该文件只替换 `PHASE1_SYSTEM`，并覆盖本变体的 `memory_add` 描述。去除这两处文本变化后，AST 与 4964 相同。

下列文件逐字保持父版：`responses_memory_llm.py`、`pma_model_profile.py`、`worker_main.py`、`predictive_memory_agent.py`、`context_predictive_memory_agent.py`、`ga_context_history.py`、Harbor `lite_llm.py` 和 GA 源码。

因此未改 P2、W8 唤醒/观察窗、模型与预算、工具执行、add-only 直接进入 P2、read/error 条件续轮、GA 历史裁剪配置及原生历史续接。父版已有工具回执审计保留。

Responses 的 reasoning item（含已有不透明状态）仍按父版在各自阶段原样续接；公开 message/function_call 继续从当前可见历史重建，以服从历史裁剪，并不是所有 item 都逐字回放。Claude 的 thinking/signature/redacted blocks 沿原有同阶段路径保留。不解码、不公开私有状态，不从私有状态合成正文。

## 离线验证

- 定向：**33 passed**。
- 完整选定回归：**157 passed、15 subtests passed、5 failed**。
- 同环境干净 4964 对照：**154 passed、15 subtests passed、相同 5 failed**。
- 5 个旧失败均来自 `test_continuous_integrity_repairs.py`：4 个旧 AST 夹具漏加载 `_history_bytes`，1 个旧来源清单断言漏掉已有 Responses 适配器。未降低断言或借本次任务修改旧测试。
- 新增 3 个测试仅覆盖既有原生历史：OpenAI 实际 SDK + MockTransport 的 P1/P2 隔离、reasoning 原样续接、工具 ID/参数/回执配对及私有数据不进审计；可见历史裁剪后 reasoning 不变；Claude 带签名及 redacted blocks 的同阶段续接。
- 既有测试继续覆盖 Claude/LiteLLM 请求转换、两工具及错误恢复、add-only/read 轮次、P2、完整提示传递、正文为空和审计。
- `compileall`、`git diff --check` 和上述 AST 对照通过。Python 源码与测试中没有新增摘要开关或投影字段残留。

本地仅准备测试所需的固定提交文件投影：先重新读取真实远端父提交及其 Git tree 指针，再验证 967 个树对象和 340 份文件，另补齐并核验 12 份既有测试依赖。发布以真实完整远端树为基础，只覆盖本轮文件，不发布本地投影祖先或替换仓库其他内容。

复现命令（需仓库测试依赖）：

```bash
STAGE=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013
export PYTHONPATH="$STAGE/vendor/pma_89e5c0d/src:$STAGE/vendor/pma_89e5c0d/external/harbor/src:$STAGE:GenericAgent-main:experiment_runner:.:$PYTHONPATH"
export LITELLM_LOCAL_MODEL_COST_MAP=True
python -m pytest -q -p no:cacheprovider tests/test_predictive_native_history.py tests/test_simple_predictive_prompts.py tests/test_predictive_visible_basis.py tests/test_predictive_memory_read_integration.py
python -m pytest -q -p no:cacheprovider tests "$STAGE/test_model4_transport.py" experiment_runner/test_context_predictive.py
```

测试环境：Python 3.12、pytest 9.2.0、OpenAI 3.46.0、LiteLLM 1.108.1；导入本仓库 Harbor 源码并安装 Harbor 0.1.42 分发元数据。provider 测试阻断外部网络，使用合成响应。

## 局限与停止点

没有运行真实模型、Docker 任务或真实网关实验，没有修改用户现有开发线程或实际 profile；未验证全仓库、Windows 或模型对新语义的遵从。离线通过只证明接线与既有机制未发现新增回归，不证明预测或任务效果提高。

不再要求公开解释，因此不保证每轮有可读分析。没有新增 summary 请求，保留原生续接不等于向用户展示内部思考。原版本已有的审计失败与非事务性限制仍然存在。

本轮仅在新独立分支保存版本，不合并、不部署、不启动下一阶段实验。
