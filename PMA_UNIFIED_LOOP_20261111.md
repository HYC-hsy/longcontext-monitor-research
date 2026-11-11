# PMA 单一持续管理循环

基线：`d548ea0b208fbc1281637916be9fbf03dedfd226`。
入口保持 `pma-predictive-read-context` / `pma_predictive_read_context_v1`。
本分支升级这一方法，不新增配置开关；d548 原分支保留作对照。

## 目标与实施顺序

1. 将固定 P1→P2 改为一个持续管理者和一份历史，保留原有预测、记忆与提醒语义。
2. 接通真实工具回执、失败终止、审计、导出和现有认证的阶段识别。
3. 迁移旧两阶段断言，新增独立协议、原生 provider 和实际 worker 生命周期测试。
4. 同环境对照离线验证，独立审查后发布独立分支。真实模型与完整五题实验不在本次授权内。

各实现步骤分别进行，核心、接线、测试各组以及后续审查修复均少于 600 行新增加删除；未把整体实现当作一个单步变更。

## 运行行为

每次原定唤醒进入同一个 `process`：

- 系统提示合并 d548 的公开预测指导、P2 按需提醒指导及最小循环协议。
- 原任务固定保留；后续只送本次新增公开轨迹。预测未来 10 轮、默认每 8 轮唤醒及其可配置值不变。
- 每次请求只提供现有 `memory_add(content)` 和 `memory_read(bank_id="knowledge")`。schema、全量读取和有序执行不变。
- 公开预测仍是柔性指导。缺少公开正文只影响下一次本来就要发生的请求，不因预测摘要缺失单独重试，不把私有 thinking 转为正文。
- 当次响应可以直接以 `<context_for_action>非空提醒</context_for_action>` 或 `<no_intervention/>` 结束，无需额外 P2 调用。
- 同一响应可以带工具和结束标签。先执行整批真实工具、保存对应回执；只有全部成功才接受该响应的结束标签。无工具的合法标签也可直接结束。
- 若 read 的结果还需要影响判断，模型应先不给结束标签，看到真实结果后再判断。不会机械地强制所有 read 再多一轮。
- 工具失败时，同响应标签不生效；反馈错误后由同一管理者修正或重新决定。成功部分保留，历史中的调用不重放；连续 3 轮含工具错误仍按既有约束明确失败。
- 无工具且无合法结束标签时，提供一次格式反馈；再次无效则明确失败，不伪造 no-intervention。成功工具操作（含成功 read）允许重新开始这一格式恢复窗口，失败-only 操作不会重置窗口。
- 成功工具链不限为 1、2 或固定若干轮；没有新增全任务调用、时间或 token 上限。
- 标签必须唯一、完整、位于公开回复末尾；空、冲突、重复、隐藏/代码块内或不平衡隐藏标签中的决定不接受。这是语法与通道检查，不是事实核验或场景筛选。
- provider 错误、取消、原生 call ID/JSON/签名完整性错误不会变成静默决定；有效原生回执先落地，worker 原来的 fail-stop/no replay 路径继续生效。

## GA 与 PMA 的复用边界

### 实际阅读与版本

- 当前仓库 `GenericAgent-main/agent_loop.py::_agent_runner_loop_impl`、`BaseHandler.dispatch`，以及 `llmcore.py` 的历史转换/裁剪执行链：以 d548 中的源码为本次精确对照。GA 项目的 `pyproject.toml` 声明 MIT。
- GA `ga.py` 的公开 summary 提醒用法。这里只借鉴公开表达与轻量后续指导，不复制私有 thinking 的显示回退。
- PMA `yifannnwu/proactive-memory-agent` 固定上游 `89e5c0d6aadfe531a1aee42fd290d48be89973dd`，Apache-2.0；来源记录见本仓库 `SOURCE_PROVENANCE.md`。当前 vendor 含已有项目适配，本改动不是未经适配的上游复现。
- 当前 d548 的 `ReadContextPredictiveMemoryAgent`、`ContextPredictiveMemoryAgent.process`、`MemoryEnabledTerminus2._trigger_memory_agent`、`PMAEpisode`、worker 审计/失败分支和原生 transport。

### 直接复用

- 已接入的 GA-derived `trim_observer_history` 和 `provider_history`，原任务/活跃唤醒保护、闭合原生工具组裁剪及公开/私有 provider 状态分离不变。
- 当前 `_record_p1_response` 的原生 envelope 检查、按顺序执行 add/read、保存真实回执和 call ID 防重放不变。
- 原 bank、host 唤醒、原始 Task 轨迹、one-shot 提醒消费和实际 Task 请求送达链不变。

### 必要适配

GA 通用循环的“响应→执行工具→保留结果→继续或结束”结构适用于本目标，但不能直接调用整个 Task runner：它负责 Task 工具、终止、宿主控制及其他实验模式，会混入当前记忆角色不需要的能力。因此采用当前 PMA executor/history 直接复用，加一个小的 async 持续循环和已有 XML 结束协议，不搬入另一套框架。

不新增 delete、事实/推断分栏、场景筛选、selector/verifier 或任务控制工具。Task 模型、provider 参数、配置、batch cadence、输入轨迹及其他方法的行为不变。

## 文件与记录格式

生产改动只有 5 个文件，均位于 `method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013/`：

- `vendor/pma_89e5c0d/src/memory_agent/memory/read_context_predictive_memory_agent.py`：融合系统、持续循环、结束解析、有限格式恢复。
- `vendor/pma_89e5c0d/src/memory_agent/memory_enabled_agent.py`：只为 unified result 附加 loop mode/rounds/termination。
- `worker_main.py`：实际请求标记 `unified_memory`；真实回执、每轮公共回复、成功/失败 cycle 落盘；本地 synthetic fixture 同样走单循环；失败标记无决定。
- `archive_ordered_real.py`：公共导出保留逐次回复、回执、cycle、历史与关联 ID，排除原生私有字段及旧式 think/thinking 内容。
- `single_run_certification.py`：本方法期望 unified phase；其他方法保持原阶段集合。修改选择器不等于已经生成新的 Docker/native 认证。

原有内部 `_phase1_*` 名称保留作为单份历史/工具存储的兼容字段，不代表仍运行两个模型阶段。`_phase2_history` 不使用，结果中的 phase2 prompt/response 为空。新增 `loop_mode="unified"`、`loop_rounds` 和 `termination` 为权威循环记录；旧 raw_response_phase1 字段保存最后一次公开响应。循环记录不复制原生私有推理字段；公共导出进一步排除正文中的旧式隐藏推理标签。

## 离线验证及限制

准确命令、计数、基线共享失败、文件哈希见 `PMA_UNIFIED_LOOP_VERIFICATION_20261111.json`。

覆盖：一回合结束、成功工具+标签、read 后判断、部分成功与失败标签、格式恢复、长工具链、重置和跨 wake 历史、原生 OpenAI SDK MockTransport 与 Anthropic 序列化、签名/opaque 回放、公开导出隔离、host 提醒只消费一次、真实 `worker_main.serve` + EventClient/spool 的成功及失败持久化。

原有两阶段测试按实际单循环协议迁移，没有跳过失败来伪造通过。独立审查发现并修复嵌套隐藏块可能暴露标签和旧式隐藏文本可能进入导出的两个问题，并加入 canary 回归。首次新 host 测试误漏原有 memory_context 说明，仅修正测试预期。

源码是在有限的已验证投影中测试，不是全仓 CI；同环境 d548 的共享失败仍明确列出。旧日志/缓存不发布。离线检查仅验证工程契约，不证明更好的预测质量、提醒质量、调用成本或 benchmark reward。

真实模型调用 0；真实 benchmark 任务 0；没有执行五题、Docker/native 新认证或部署。下一阶段若要运行真实对照，需重新确认任务、预算、模型和确切发布 commit 后再启动。
