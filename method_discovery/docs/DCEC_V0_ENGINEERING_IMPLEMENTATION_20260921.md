# DCEC-v0 最小工程实现（2026-09-21）

## 状态

- 基线：`9c5cb16`。
- 本轮只实现工程机制和离线确定性验收；模型 API 调用为 0，判别实验未启动。
- 唯一模型拥有的当前认知状态仍是 `monitor/working.md`。没有新增 semantic state、selector、verifier、maintenance stage、自动语义分类器或 requirement checklist。

## 接线

### 单一有界 active view

`working_context.dcec_working_context()` 从现有 `monitor/working.md` 生成请求局部视图，默认硬上限 4000 字符，可配置范围 512–8000。视图明确声明它是模型自身可修订状态而非事实来源；返回源字符数、可见字符数、注入字符/UTF-8 字节、粗略 token 估计、截断状态和源哈希。

复用 provider 已有的 `prepare_active_context` 接缝：正常带工具请求发送前临时追加，发送后从 History 弹出。因此每次正常推理可见，但不会被复制进持久 History。DCEC 关闭时不安装该 hook，ordinary system 与请求路径保持原状。

实际组装形态（正文来自当时同一 `working.md`，以下为脱敏短例）：

```text
DCEC current working state from monitor/working.md. This is your own revisable cognitive state,
not a fact source or verified truth. ...
<dcec_working_state>
Current decision
- decide whether the observed repair resolves the local concern
Active concern
- recovering: direct post-repair behavior is still pending
Current grounds and limits
- Task Agent reports a fix; this is not direct evidence
</dcec_working_state>
```

### revision contract

在同一个 persistent Supervisor system 中增加最小合同：一个当前 decision、一个 focal uncertainty、active/recovering concern 和 current grounds/limits；intervention 不等于 resolved；只有后续公开观察可支撑退出；新冲突可 reopen；local recovery 不支撑 whole-task completion。模型仍使用既有 `file_write/file_patch` 在原调用中自然修订，不要求每 wake 写文件。

runtime 只保留工具、路径、范围、哈希、截断和版本等确定性边界，不产生 `satisfied/correct/sufficient/stale` 等语义标签。

### continuation

复用现有 pre-compaction continuation，没有增加请求。DCEC 开启时，原 continuation prompt 增加 lifecycle 约束：resolved 不因历史重现而自动 active；open/recovering 不在无后续证据时丢失；claim/summary 不提升为 direct observation；local/root scope 保持分离。原有“先校验、后原子替换”不变，截断/拒绝/异常均不覆盖旧 working state。

### 遥测

现有 `progress.jsonl` 新增：

- `dcec_working_view`：每个真实正常请求的有界视图大小、截断、hash 和 token 估计；
- `dcec_state_mutation`：对 `monitor/working.md` 的成功 write/patch 操作及写后 receipt。

review 调用、provider request/attempt、usage、continuation usage 与 wall time 沿用现有 telemetry，不另建日志系统。

## 历史候选隔离

DCEC 开启时，对 independent C、inquiry、PMA、task model、旧 decision context、旧 active working context、grounded context、feedback focus、advice/handoff/tool-feedback/live-awareness 和旧 root contracts 组合 fail-fast。semantic continuation 是 ordinary persistent Supervisor 的既有容量机制，保持开启且两条件共同计量。

## 离线验收映射

`GenericAgent-main/tests/test_monitor_dcec.py` 经生产函数覆盖：

- DCEC-off ordinary contract 不变；
- 历史候选组合和非法 bound 被拒绝；
- 有界单一视图及成本元数据；
- production provider 发送边界只注入一次、发送后不持久复制；
- open → recovering → resolved → reopen 的真实 workspace write/patch fixture；
- local resolved 不自动成为 whole-task support；
- read receipt 保留 range/hash/truncation 且没有 runtime semantic label；
- continuation 截断两次仍保留原状态；
- adapter 显式解析 DCEC 开关和字符上限。

现有 monitor/provider/continuation/inquiry 等相关回归也必须保持通过。测试通过只证明接线与边界，不证明模型会正确维护或消费状态。

## 尚未执行的实验

冻结 manifest：`method_discovery/artifacts/dcec_v0_20260921/discriminating_manifest.json`。

它只比较 ordinary persistent Supervisor 与 DCEC-v0，包含 latent-defect 与 correct-control 两个领域中性序列，模型、工具、预算、并发和 completion 协议一致；DCEC 不增加模型调用。状态必须从序列自然形成，禁止研究者注入已知缺陷。当前 `execution_authorized=false`，等待独立审计与启动确认。
