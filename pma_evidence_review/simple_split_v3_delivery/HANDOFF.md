# 简化拆分审核 v3：实现交接

## 范围与启用

- 基线：生产提交 `8c5f6ee0a9d64db39cee82df686bbf616f8e5ff3`。
- 新策略：`claim-split-same-evidence-v3`，通过现有 citation gate 的 strategy 配置显式启用；默认策略和 v2 均不变。
- 仍支持 `gate-only` 和 `gate-one-repair`。后者最多一次作者修订，并对完整替换操作重新拆分、整批审核；只有全部支持才提交。
- 本轮仅本地代码、离线定向测试与交接。不运行模型、Task、Docker、完整回归或生命周期认证。现有 v2 单独对比 CLI / certificate replay 未扩展为 v3 工具；在线 gate 的显式策略配置是本轮入口。

## 最小协议

拆分输出仅为有序、非空字符串数组，例如 `["观点一", "观点二"]`。无原文锚点、偏移、观点 ID、分类或静默上限。

同一原操作 A 的全部观点只进行一次批量审核，共享原提交证据 B。审核输出：

```json
{"overall":{"verdict":"insufficient","reason":"原操作仍有未获支持的完成判断"},"results":[{"verdict":"supported","reason":"该局部观点有证据"}]}
```

`results` 必须与保存的观点数组等长且同序。每项和 `overall` 仅允许 `verdict` / `reason`，结论仅为 `supported`、`insufficient`、`contradicted`，原因必须非空。宿主保守聚合：任一矛盾即矛盾，否则任一不足即不足，只有全部支持才通过。原操作完整含义仍由 `overall` 判断，不新增一轮覆盖检查，也不把 Step 1 / 标题逐字覆盖当门禁。保留既有 `SUPPORT_SENTENCE`，按含义判断但不扩大范围、丢条件或强化结论。

作者修订反馈由宿主附上完整 A、保存的每项观点文字、结论与原因、整体结论和 B。模型无须回抄观点或返回证据 ID。原 A 明确为审核目标，绝不是证明自己的证据。

## 引用与来源

v3 允许经过完整一致性校验的 `exact_multiple`。每个提交引文只显示一次，附实际匹配来源的 role、field path、source identity 和 event order；标明这些是同一引文的候选来源，不是独立佐证。命令中的成功字符串不能因为同文匹配就提升为执行 stdout。保留闭合 B，不补未引用历史、邻行、检索内容或上下文填充。

未找到引文、规范化匹配、缺失证据、重复伪造候选、来源哈希不符、候选基数/聚合不一致仍阻断。底层 bound write 已支持合法多候选，本轮未放松保存校验。

## 有界流水线与提交边界

同一时刻最多一个拆分和一个批量审核，最多预取一个后继操作。第一项进入审核后第二项可拆分；第一项修订时独立后继可继续审核。提交始终按原操作顺序串行执行。同目标后继等待前项最终结果，失败目标不被后继绕过。

候选已携带实际 memory/revision identity，不能在提交时重建成另一个未经审核的候选。后继候选只把其已审核单项 delta 合并入最新 bank，保留审核身份，不回写旧整库。要求 generation 未被外部修改、目标基线 revision 未变；legacy 目标使用候选归一化后的 pre-operation revision，避免第一次材料化被误判为并发修改。正常 publication 继续校验 bank，失败不会发布候选。

阶段请求、A/B 和冻结可见性不因前项提交或修订而重建。维护结束后才进入 selection，selection 只见实际提交结果。取消和全局传输失败会取消、收集未完成任务；实际发生的预取调用仍留诊断记录，不伪装成从未审核。使用任务局部 transport phase 防止并发审核/修订互相覆盖标记。

## 验证和限制

- `core-tests.txt`：22 项核心协议、绑定与 v2 核心兼容测试通过。
- 最终 pipeline / live / 兼容命令共 50 项通过，输出 `pipeline-tests.txt`。协议与多来源实际提交命令共 9 项通过，输出 `final-protocol-tests.txt`。这些命令包含重叠覆盖，不把旧计数相加。
- `historical-samples.json`：只取三个历史案例做准备及请求形状检查（多候选、span 失败、缺失 E ID）。多候选从旧准备阻断变成 v3 ready；其余可构造 v3 请求。未把历史模型输出转换成新策略判断，也未全量重放。
- 所有语义结论均为脚本化测试响应。此处证明接口、隔离、并发与提交行为，不证明模型拆分完整率、审核准确率或任务效果提升。
- 一项既有 Harbor binding 测试依赖本稀疏工作树外的 preflight 模块，不在本轮定向测试范围；没有为它扩展生命周期检验。

## 可复制的后续指令（仅离线）

在仓库根目录，替换为可用 Python 环境：

```bash
PYTHONPATH=/tmp/auditor-offline-deps:$PYTHONPATH /tmp/pma_evidence_repair_env/bin/python -m unittest \
  pma_evidence_review.tests.test_claim_split_simple \
  pma_evidence_review.tests.test_simple_split_commit -v
```

上面只运行协议和多来源提交定向测试；`final-protocol-tests.txt` 保存最后一次的真实输出。流水线命令见 `run_pipeline_tests.py`，可执行：

```bash
PYTHONPATH=.:/tmp/auditor-offline-deps:$PYTHONPATH /tmp/pma_evidence_repair_env/bin/python \
  pma_evidence_review/simple_split_v3_delivery/run_pipeline_tests.py
```

本轮未执行真实调用；后续按用户给定的任务和运行范围执行，不能把离线通过当成真实效果。共享 gate 配置使用 `--citation-review-strategy claim-split-same-evidence-v3`，同时显式选择既有 gate 模式。
