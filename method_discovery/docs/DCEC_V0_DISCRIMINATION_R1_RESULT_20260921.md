# DCEC-v0 四记录最小判别实验 R1：事实归档

日期：2026-09-21  
授权提交：`100c842`  
机制实现：`1cd7048c5742ca7415937ec5142cc28fd2bcaf22`  
launch 实现：`b4964a5282b53c0bbd18a954b2f47cc2326ca668`  
正式输出：`method_discovery/runs/dcec_v0_discrimination_r1_launchprep/`

## 结论边界

冻结的四份 record 均按预注册顺序执行一次且没有重跑。四份都在第一次 provider 请求、模型产生任何响应之前遇到同一种基础设施错误：隔离 gateway 返回 HTTP 400，正文报告上游 TLS 证书校验失败（`CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`）。

因此本批结果是完整保留的系统性基础设施失败记录，无法评价 DCEC 的机制效果，也不能评价 ordinary 与 DCEC 的相对表现。本报告不将最终状态、DCEC active-view 注入或错误退出解释为方法证据。

## 四记录事实表

| record | 条件 | status / stop reason | initial/root action | intervention / repair | logical calls | provider attempts | usage/tokens | supervisor wall | host elapsed / cleanup | deadline |
|---|---|---|---|---|---:|---:|---|---:|---:|---|
| 01 | latent / ordinary | error / worker_review_error | 均未形成 | 0 / 未触发 | 1 | 1 | 无成功 usage；input/output/cache 未取得 | 1.211s | 4.359s / 0.375s | 900s；未超时 |
| 02 | latent / DCEC-v0 | error / worker_review_error | 均未形成 | 0 / 未触发 | 1 | 1 | 无成功 usage；input/output/cache 未取得 | 0.892s | 3.953s / 0.375s | 900s；未超时 |
| 03 | correct / DCEC-v0 | error / worker_review_error | 均未形成 | 0 / 未触发 | 1 | 1 | 无成功 usage；input/output/cache 未取得 | 0.774s | 3.969s / 0.422s | 900s；未超时 |
| 04 | correct / ordinary | error / worker_review_error | 均未形成 | 0 / 未触发 | 1 | 1 | 无成功 usage；input/output/cache 未取得 | 0.875s | 4.156s / 0.391s | 900s；未超时 |

每份 request audit 都记录了一次 `request_started`、HTTP 400 response headers 和一次 error completion。没有 transport retry，也没有成功响应用量；不能把未返回的 token 用量写成零成本。

## 预注册机制链的可观察情况

### A. A 阶段

模型没有返回首个响应，所以没有识别 A、没有 intervention，冻结 repair 未触发，也没有 post-repair direct observation。

### B. concern lifecycle

DCEC 两份记录只完成了请求前 bounded active-view 注入：`working.md` 不存在，source hash 为空文本 hash，注入的合同视图为 784 characters。没有模型响应、state write/patch、concern 创建、recovering、resolved 或 reopen 行为。因此 concern lifecycle 不可评价。

### C. root investigation

四份记录都没有进入 root review。B 没有成为 focal uncertainty，没有模型发出的工具动作，也没有判别性观察。

### D. evidence use

没有取得模型侧新观察，没有 grounds revision，也没有 completion control。最终 error 不能作为完成判断。

### E. correct control

正确 control 两份同样在首个请求失败，无法判断是否存在 false blocking、额外 UNKNOWN、反复验证或错误拒绝。

## 状态与工具轨迹

- 每份 record 都保存了一条请求前 working-state timeline；初始 `working.md` 均不存在。
- DCEC records 保存了 active-view hash；ordinary records 没有 active view。
- state write/patch：0。
- continuation transitions：0。
- out-of-band state changes：0。
- 模型工具调用：0；不存在可评价的 file/code/control tool trajectory。
- final workspace 与各自初始 variant 一致；没有 repair 修改。
- `task_blocking_latency` 按协议为不适用，因为任务侧是冻结 scripted fixture。

## 归档完整性

每份 record 保留 `result.json`、task/workspace、dialogue、progress、provider history、request attempts、reviews、working-state timeline、transport 和 worker result。顶层 `results.json` 标记 `finished_once_no_retries`。本批没有现场修复、补跑或替换输出。

本报告到此停止，不对是否允许新实验批次作判断。
