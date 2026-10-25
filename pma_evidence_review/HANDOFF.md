# PMA 证据审核器 v1：中文交接与接口契约

本组件只审核当轮记忆写入/删除是否受到当时可见证据支持，不判断任务是否完成，
不改正式记忆、不触发返工或三角色运行。当前只有离线 fake 工程验收，没有真实模型
效果结果、人工标签或留出集对照。

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
的结果会报告 `alignment_error`，不会默认为已定位。现有定位算法保持不变。

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
