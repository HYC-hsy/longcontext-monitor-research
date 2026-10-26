# PMA 证据审核器 v1：中文交接与接口契约

本组件只审核当轮记忆写入/删除是否受到当时可见证据支持，不判断任务是否完成，
不改正式记忆、不触发返工或三角色运行。本轮修复只有离线 fake 工程验收；既有首轮真实输出保留为开发诊断，
不是本轮修复的真实模型效果结果、人工 gold 或留出集对照。

## 稳定接入点

```python
from pma_evidence_review.review import review
from pma_evidence_review.location import locate
from pma_evidence_review.transport import CapturedTransport

# packet 由可信宿主从当轮现有对象投影，先校验并冻结；不传最终全量 bank。
# client 是现有异步 llm.call(prompt=..., system=..., tools=None) 客户端。
transport = CapturedTransport(client, private_capture_directory, fake=False)
report = await review(packet, transport, locator=locate)
```

这是未来接线示意，本轮没有执行。必须显式传 `locator=locate`；省略定位器时，含引文
的结果会报告 `locator_unavailable`，不会默认为已定位。现有定位算法保持不变。

`review` 的消费契约是 packet、transport 和 locator；它不读归档、不选择 SQLite/HTML、
不读最终 bank。`inputs.build(repo, sample)` 只是已公开归档的一个适配器。
未来宿主可以从当轮 maintenance prompt/manifest、维护前可见快照、按序操作与 revision/
receipt/tombstone 投影成同一个 packet，继续复用同一提示、解析器、定位器和报告。
本轮没有实现或启用在线调用点，也不保证工程契约通过就意味着语义有效。

## 输入字段与身份

- `schema=pma-evidence-review-input-v1`；`cycle_id/step/call_sequence` 为当轮身份。
- `maintenance_prompt`：实际当时可见正文；`manifest` 为现有来源清单与可见区间。
- `original_task`、`sources`：只从该正文/manifest 提取，区分命令、回执、Agent 自述、
  派生记忆。公共 source handle 和 visibility_ref 使用现有协议公式校验。
- `memory_before`：维护前可见的 `{memory_id, revision_id, category, content}` 快照。
- `operations`：按 `op_index` 排序的本轮动作；每项有 `action/memory_id/revision_id/
  category/content/content_sha256/success/before/binding_status/review_scope`。
  删除的 content 表示被删历史内容，审核对象是删除的理由，不是把旧问题当作事实。
- `replay_status/limitations/truncation`：显式记录脱敏、遗漏、缺失或降级。

两个哈希职责不同：

1. `request_sha256` 只绑定 maintenance 正文；`original_request_sha256` 是原 manifest
   记录值。`exact_public_prompt` 只表示这个旧提示精确匹配，不表示任意操作都可信。
2. `review_input_sha256 = inputs.review_input_identity(packet)` 绑定规范化的完整模型
   材料及周期/manifest 身份，包含操作与 before。使用 UTF-8、排序键、紧凑 JSON，
   禁止 NaN；哈希本身不参与计算。`inputs.validate(packet)` 必须通过才能导出或调用。

可信构建方先形成 packet，再计算完整哈希、执行 validate、保存；审核消费端只验证，
不得为了让失败输入通过而自动重算。旧输入缺少完整哈希时应重新构建。
修改写入内容即使重新冻结，也成为不同审核输入；完整哈希是内容身份，不是签名或
历史真实性证明。操作 `before` 必须匹配初始快照或同周期较早写入；删除正文和 revision
必须匹配当时最新目标，不能靠重算哈希替换删除对象。同周期连续更新/更新后删除受支持，
但尚未产生的未来 revision 不可用。

归档适配器额外验证根 INDEX 的 slot INDEX 哈希、所读文件 gzip 大小/哈希及解压哈希。
不读取评价文件；最终 bank 仅用作按精确历史 ID 查询的档案，不进入模型材料。

## 输出与消费原则

`report` 含两个输入哈希、`claims/coverage/results/errors/limitations`。
每个结果关联 `claim_index/op_index/memory_id/revision_id/action`，保留原 claim 片段、
类型、条件、依赖与来源坐标。语义值为 supported/contradicted/insufficient；解析失败、
调用错误、缺项、无法定位等为独立工程状态，verdict 为 null。原响应在 capture 中保存。
计划/假设/问题为非事实类型；空/不完整抽取不是“没有问题”。没有总体支持率门槛或自动写入。
调用方应保留输入身份与逐项工程状态，不能只取 supported 数量决定关闭 gap。

## 可复制离线运行

在固定提交的仓库根目录，使用已有 Python >=3.10（本次使用已安装的 3.11.15）：

```bash
python3.11 -m pip install --target .review-deps -r pma_evidence_review/requirements.txt
export PYTHONPATH="$PWD/.review-deps${PYTHONPATH:+:$PYTHONPATH}"
export PYTHONDONTWRITEBYTECODE=1
python3.11 -m unittest discover -s pma_evidence_review/tests -v
python3.11 -m pma_evidence_review build --sample sqlite --out /tmp/sqlite-review-v2.json
python3.11 -m pma_evidence_review build --sample html --out /tmp/html-review-v2.json
python3.11 -m pma_evidence_review validate --input /tmp/sqlite-review-v2.json
python3.11 -m pma_evidence_review export --input /tmp/sqlite-review-v2.json --out /tmp/sqlite-request-v2.json
```

输出路径必须是新文件。完整 synthetic fake 命令见 README；最小核心接口回归在
`tests/test_identity.py::test_core_consumes_packet_without_archive_adapter`。
SQLite C14（54 来源/3 操作）与 HTML C2（12 来源/4 操作）都是开发样本，不是留出集。
标签单独存于评价侧，按完整审核输入哈希关联，不进入 packet。普通审核与候选比较须
使用相同可见材料并预先说明抽取是否共享；目前未执行此类语义对照。

未来真实调用前确认输入、既有模型和执行范围，记录实际资源消耗与重试行为；只采用
用户明确指定或现有模型必需的限制，不强制新增调用数、token、时间或费用上限。
真实模型、在线接入、整理者返工、Task 和官方评价仍分别需要相应授权。

## 2026-10-26 来源边界修复（本轮只做离线验证）

稳定 packet、`review(packet, transport, locator=locate)`、模型客户端和原定位算法不变。
旧 `review_input_sha256` 继续标识完整冻结输入；新 `audit_request_sha256` 标识实际发送的
`{system,prompt,tools}` 按 UTF-8、sort_keys、紧凑 JSON 序列化后的 SHA256，报告保存每次
请求的摘要，capture 同步记录。`evidence_policy=source-use-v2.1` 区分新协议。不要覆盖旧运行。

请求边界变化：

| 区域 | 修复前 | 修复后 |
| --- | --- | --- |
| 抽取正文 | 整包材料 | 仅 operations（含删除 before）；任务/历史快照另列解释上下文 |
| 核验 Source Documents | 整包材料，包括待审操作 | 仅 packet.sources 中按用途允许的可见切片 |
| 待审操作 | 同时是证据 | 放在 Claim 的 audit_target_not_evidence 区域 |
| maintenance_prompt | 完整进入模型材料 | 仅保留在归档/输入身份中，不进入请求 |
| 引用定位 | 全来源匹配字符串 | 先解析请求文档身份，再限制原定位器的搜索范围 |

抽取新增内部 `evidence_scope`，第一阶段无需增加字段：execution 只用 tool_observation；
attempt 只用 tool_command；static_behavior 可用 tool_command/tool_observation；
requirement 只用 task_instruction；historical_record 只用 memory_derived；
agent_statement 只用 agent_report。缺少 scope 的旧抽取结果默认 execution，并记录
scope_origin=conservative_default。batch 按 scope 分组，调用次数可能随用途组数变化。
命令中的代码可以支持狭义静态行为；回执可以支持其实际报告的文件创建等观察。
“要求是什么”和“曾记录什么”仍可审核，但不能用这两种用途偷换执行或缺口解决断言。

每条 evidence 对应 citations 中一项，含零基 document_index、source_id、role、
visibility_ref、原来源 start/end。索引绑定到实际请求内的文档，不能任意使用全局序号。
兼容上游单个 document_index 的情况仅限一条引文且该文档内文字唯一；多引文须逐条索引。
字段若提供必须一致。缺身份不做自动跨来源猜测，重复文字不随意选角色。
显式区间必须落在可见切片内且逐字匹配；严格引用拒绝不会改变原定位器的模糊诊断能力。
新增工程状态包含 citation_missing、citation_count_mismatch、citation_unknown_document、
citation_wrong_source_id/role/visibility_ref、citation_outside_visible_range、
citation_text_mismatch、citation_ambiguous_or_unmatched、citation_first_document_conflict、
citation_use_not_permitted。locator 缺失现在是 locator_unavailable。
工程失败时正式 verdict=null，保留 model_verdict；解析失败看原始响应捕获，不冒充语义不足。

工程强约束是对象分区、来源身份/角色/范围、一对一引用与无空证据通过。
主张用途、抽取完整性、条件保留及“证据是否真的支持这项主张”仍依赖模型判断。
尤其静态代码与执行结果、局部成功与跨会话推广、删除理由是否充分，不能由定位保证。
本轮不声称已解决这些语义错误，没有新真实调用、gold、准确率或效果提升结论。
原诊断包仅用于旧输入哈希与新请求构造回归，两份样本仍是开发样本。

从仓库根目录复制执行（使用当前 Python 3.10+；原部署依赖 regex==2024.11.6）：

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review build --repo . --sample sqlite --out /tmp/pma-v2-sqlite-input.json
python -m pma_evidence_review validate --input /tmp/pma-v2-sqlite-input.json
python -m pma_evidence_review export --input /tmp/pma-v2-sqlite-input.json --out /tmp/pma-v2-extract.json
```

导出核验请求时追加 `--extraction-response` 指向保存的抽取 JSON。旧抽取可检查工程路径，
但默认用途不代表重新抽取过。fake 命令仍接收原始响应字符串数组；SUPPORTED 示例须包含
`evidence:["原文"]` 与对应 citations，或单引文 document_index。完整合成可运行示例在
`tests/test_source_boundary.py`，包含捕获的最终请求、文件创建和静态代码正例。
CLI 使用新输出路径且拒绝覆盖，测试禁止网络连接（保留 Windows asyncio 本地 socketpair 例外）。

未来真实实验必须另获授权，确认输入、模型和执行范围；只应用用户明确要求或模型必需的
限制，记录实际调用/重试/资源。使用同一冻结输入分别保存旧/新请求与结果，开发诊断标签
单独存放，不进入模型输入。先分析分区、用途分类与绑定弃权，再由独立逐项诊断评估语义；
没有盲评 gold 时不报告准确率/增益。不要把这里的 fake 断言当成真实模型标签。


### v2.1：解释上下文保留原命令与事件身份

v2 的用途过滤遗漏了 execution 判断所需的原命令上下文，已修复。
核验的独立 `INTERPRETIVE CONTEXT` 现在包含全部原始可见来源投影，逐项保留
source_id、handle、role、event_order、field_path、visibility_ref、kind 和 slices。
使用已有身份和顺序解释命令/回执，不另造关联 ID、不补隐藏或未来历史。
因此 SQLite 的 PATH 导出与 which 命令条件、HTML 写文件的参数/代码仍对核验可见。
所有 scope 都保留这份上下文；抽取正文及其上下文保持原来的更小范围。

这些上下文可限制或推翻宽泛结论，但只有 Source Documents 中的来源可以作为该用途的
独立支持引用。execution 引用集合仍仅含观察回执，命令不能替代成功观察。
需要结合命令解释回执的语义判断仍由模型完成，不能从保留上下文推断已经判断正确。
请求策略改为 source-use-v2.1，实际请求摘要随之改变，冻结 packet 摘要不变。
新增最终请求回归核对整个可见来源投影及事件字段，并在冻结 SQLite 请求中检查
export PATH 和 which sqlite3 同时可见；命令单独引用仍拒绝。47 项离线测试通过。
