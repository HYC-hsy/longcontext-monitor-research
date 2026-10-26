# v4 原始操作直接审核：接收与离线验收

本版本基于归档 `4e3a52a637322c3b436552390e8c0ccb035d8cef`（生产 v3
`79708fd7531956e067094fa8d2ca2c00fd226bd9`）。默认不再调用模型抽取、拆分、改写或分类。
每个成功且支持的原始操作一次核验；本轮仅工程实现及 fake 测试，没有真实模型效果结论。

## 接口与版本

```python
from pma_evidence_review.review import review
from pma_evidence_review.operation_review import operation_requests
from pma_evidence_review.location import locate
from pma_evidence_review.transport import CapturedTransport, FakeClient

plans = operation_requests(packet)  # 本地校验、完整请求导出，不调用模型
transport = CapturedTransport(FakeClient(raw_response_strings), private_new_directory, fake=True)
report = await review(packet, transport, locator=locate)
```

`packet` 与第一阶段接口、原完整输入摘要均不变。核心不读取最终 bank 或归档，不硬编码
开发任务。`inputs.build` 仍只是公开归档适配器；可将当轮既有对象投影为同一 packet。
显式提供 `locator=locate`；否则有引用的结果以 `locator_unavailable` 拒绝，不假装已定位。

- `review_strategy=direct-operation-v4.1`，报告 `schema=pma-operation-review-report-v2`。
- 来源协议仍 `evidence_policy=source-use-v3`，一基 Document N / document_index。
- 身份为 `op_index/action/memory_id/revision_id/content_sha256`，没有伪造 claim_index。
- `operation_requests` 返回按操作顺序的 `{op_index,target,engineering_status,request}` 列表。
  failed/未知 action 的 request=null，结果仍保留，不冒称它们已应用到记忆。
- 全部成功操作的正文和 before 均原样保留。delete 的问题由宿主固定为是否有充分依据删除
  该条目；旧缺口曾经成立不是删除理由。材料可支持解决、替代、重复或失效等理由。
- 当前支持 save_knowledge/save_procedural/save_gap/update_status，以及
  delete_knowledge/delete_procedural/delete_gap/delete_status。新增宿主 action 需显式适配；
  未识别项返回 not_reviewed_unknown_action。输入身份或链条非法则整包校验拒绝、零调用。
- 报告每操作都有完整 target、verdict、model_verdict、raw_response 和 engineering_status；
  含引用时保留来源身份、角色、可见范围、原分级定位结果及 evidence_spans。
  抽取 claims/coverage、kind、conditions、dependencies 和用途分类字段不再是输出契约。
- 请求摘要仍对实际 `{system,prompt,tools}` 计算，capture 另记 strategy/op_index。
  来源仅来自原可见切片；命令和回执上下文、身份与顺序保留；待审操作不加入来源。

## 最小模型响应

```json
{
  "op_index": 0,
  "verdict": "NOT_ENOUGH_INFO",
  "explanation": "具体指出操作中哪一部分缺少什么可见证据。",
  "evidence": []
}
```

supported/contradicted 需要非空证据，如
`[{"document_index":3,"quote":"green"}]`，编号以当前请求显示的 Document N 为准。
重复文本必要时才提供 start/end 原来源坐标，二者必须同时给出。
响应要求恰好 op_index/verdict/explanation/evidence 四个顶层字段，不接受旧 claim 报告。
支持 SUPPORTED、CONTRADICTED、NOT_ENOUGH_INFO（解析也接受 insufficient）；报告规范化为
supported/contradicted/insufficient。未知操作编号、重复 JSON 键、错误形状不自动修复。
缺响应、调用错误、引文未知/越界/不匹配等工程失败得到 verdict=null，并保留可解析的
原 model_verdict、原 raw_response 和错误状态。调用没返回响应时 raw_response=null。

整体 supported 要求所有需证据的实质判断获支持；部分不足须定位到正文具体部分。
计划/问题/假设不自动判假，说明非事实部分并审核其事实前提；纯非事实且没有可裁决依据时
返回 insufficient 并解释，不加分类预调用。完成断言必须审核，但不替代 Task/官方评价。
这些是模型语义责任；宿主只固定完整目标、校验身份/引文，不证明模型认真看完或判断正确。
无总分门槛、自动返工、依赖图、正式记忆写入或在线接入。

## 本地接收和离线测试

使用现有 Python 3.10+。定位器依赖 `regex==2024.11.6`；已安装则不需重复安装。
在新目录克隆/检出本分支的交付 SHA，保留旧报告，不覆盖旧运行。仓库根执行：

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review --help
```

本次实际环境 macOS、Python 3.11.15，命令：

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11 -m unittest discover -s pma_evidence_review/tests -v
```

Windows 使用当前 Python 和 UTF-8 文件；原 UTF-8 读取修正及 asyncio 本地 socketpair 例外
未改，测试仍阻止网络连接。本次未在 Windows 新运行，不能称 Windows 实机验收。

下面是跨平台、全合成且不调用网络的 CLI 演练。在仓库根运行 Python 片段：

```python
import json, tempfile, subprocess, sys
from pathlib import Path
from pma_evidence_review.tests.fixtures import packet
root = Path(tempfile.mkdtemp(prefix="pma-v4-fake-"))
(root / "input.json").write_text(json.dumps(packet(), ensure_ascii=False), encoding="utf-8")
raw = json.dumps({"op_index": 0, "verdict": "NOT_ENOUGH_INFO",
    "explanation": "Synthetic plumbing response, not a semantic label.", "evidence": []})
(root / "responses.json").write_text(json.dumps([raw]), encoding="utf-8")
base = [sys.executable, "-m", "pma_evidence_review"]
subprocess.run(base + ["export", "--input", str(root/"input.json"), "--out", str(root/"requests.json")], check=True)
subprocess.run(base + ["fake", "--input", str(root/"input.json"), "--responses", str(root/"responses.json"),
    "--out", str(root/"run")], check=True)
print(root)  # 新输出目录，保留 requests.json、run/requests.jsonl、responses.jsonl、report.json
```

构建两个公开开发样本（输出路径需不存在）：

```bash
python -m pma_evidence_review build --repo . --sample sqlite --out sqlite-v4-input.json
python -m pma_evidence_review build --repo . --sample html --out html-v4-input.json
python -m pma_evidence_review export --input sqlite-v4-input.json --out sqlite-v4-requests.json
python -m pma_evidence_review export --input html-v4-input.json --out html-v4-requests.json
```

SQLite 3 项、HTML 4 项；每项 request.phase=verify_operation，无 extract。
`--mode`（包括 batch/evidence-first）和 `--extraction-response` 已移除，CLI 明确报错。
导出与 fake/profile 实际接收的 prompt/system/tools 相同，测试逐字比较并校验请求摘要。
旧 Python 路径明确为 `review.legacy_review(packet, transport, mode=..., locator=locate)`；
其响应和报告仍是旧抽取协议，不自动混读，不属于新 CLI。旧测试显式调用该路径。

## 验收证据与下一步权限

73 项离线测试通过，包括 61 项既有回归（legacy 明确标识）和 12 项操作级测试。
`tests/test_operations.py` 核对 v3 ZIP 哈希，只读取两个冻结 input，不执行轨迹命令或导入
诊断标签；旧输入摘要保持 SQLite 0aa854b8…、HTML 4760d69e…。
测试覆盖 3/4 一对一请求、完整完成句、固定删除目标、失败项/未知 action、空/错/重复输出、
引文绑定、原始响应、CLI/profile 替身一致性、no overwrite 和未授权 profile 零读取。
旧输入身份、同周期 update/update/delete、定位与 Windows socketpair 回归仍运行。
原始本轮测试 stdout/stderr 保存在 `test-records-v4/`，不包含真实模型结果或秘密配置。

后续真实运行须另获用户授权，确认输入、模型和执行范围；无需人为新增预算上限。
现有 run-profile 客户端参数保持，只在明确授权后提供既有私有 profile 与执行标志。
本轮没有读取真实 profile、真实模型调用、Task 或官方评价。以后真实结果存新私有目录，
按操作逐项诊断遗漏/范围推广/删除合理性，与旧版本比较时明确粒度变化，不能直接把旧
claim 支持率与新 operation 支持率当同一指标。两样本均开发样本，不是 gold 或留出集。


### v4.1 交付复核修正

直接模板只包含一套操作级输出契约及一个完整示例，示例 op_index 使用当前操作的准确值。
不再嵌套旧 claim 核验模板，也不靠 overrides 追加覆盖。继续执行上游 format_documents，
证据优先步骤适配为先读来源、对照整个操作、再决定 verdict。来源协议和报告 schema 不变；
review_strategy 改为 direct-operation-v4.1，实际请求摘要自然改变。旧结果不覆盖。

已收到文本但附带工具调用时，先捕获文本再报告 protocol_error/unexpected_tool_calls，
verdict=null；保留可解析的 model_verdict。非文本响应为 protocol_error/response_content_type，
不序列化任意对象。真正调用异常仍是 call_error；这些情况不混同。工具不执行，工具对象、
客户端和 profile 不进入日志。本轮以替身验证上述流程，未新增真实调用。
