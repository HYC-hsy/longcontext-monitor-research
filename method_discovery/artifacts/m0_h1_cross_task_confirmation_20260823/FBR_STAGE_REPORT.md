# M0 H1 跨任务确认 1：FBR 2.43

日期：2026-08-23  
运行：`m0-h1-fbr-v2-120m`  
任务：`roadmapbench:fbr-2.43.0-roadmap`  
任务 Agent：Claude Opus 4.6  
监察者：GPT-5.6-sol high  

## 阶段目标

冻结 GX 后的 H1 代码与 prompt，在一个已有人工监察成功参照的完整真实任务上验证：

- 持久监察是否能产生真实、可归因的纠偏；
- 是否能审查 Agent 自写测试及因果诊断；
- 是否能在局部修复后保留根任务；
- 是否允许残余 UNKNOWN 并正常结束；
- 最终 native verifier 是否改善或至少不被监察破坏。

## 配置

- Agent 最大轮次：500
- Agent 时间上限：7200 秒
- 在线 native checker：禁用
- 监察者最大主动检查次数：12/次决策
- H1 代码和 prompt：与 GX v8 相同，未针对 FBR 修改
- Native verifier：Agent 结束后一次性运行

最初的 5400 秒 run `m0-h1-fbr-v1` 在正式工作早期因用户将统一预算调整为 7200 秒而人工中止；它不计入结果，目录保留且未覆盖。正式证据来自 v2。

## 事实结果

- Agent phase 正常完成，非超时。
- 开始：`2026-08-23T11:14:00.569128Z`
- 结束：`2026-08-23T12:22:59.007088Z`
- 时长：约 68 分 58 秒。
- Native verifier：7/7 phases passed。
- Reward：`1.0`。
- 运行 proof：`valid: true`，`validation_errors: []`，`online_checker_feedback: false`。
- 历史自然 GA 分支的同题 reward 为 `0.75`，但它是不同时间的单分支历史对照，不能作为严格配对因果估计。
- 已有旧版 human-activation 分支也曾达到 `1.0`；本轮的新证据在于 H1 checkpoint harness 能复现满分行为并正常终止，而不是首次证明此题可达到满分。

## 监察行为

- 83 份决策档案，internal turn 1–82（turn 79 有两个不同边界）。
- `SILENT=66`、`HOLD=11`、`RELEASE=6`。
- 最终 obligation：37 `supported`、1 `unknown`。
- 最终无开放 repair episode，attention mode 为 `SHADOW`。
- 唯一保留 UNKNOWN：新 proxy 函数未独立行为测试“未提供自定义 client 时使用全局 client”的路径；公开源码包含该分支，但 M0 没有为消灭它继续阻断完成。

## 关键可归因纠偏

### 1. 编译前发现 MIME 包名遮蔽

Agent 导入 `mime` 包后又声明局部 `var mime string`，使 `mime.TypeByExtension` 解析为字符串 selector。M0 在编译失败前 HOLD；Agent 改名并完成三类 MIME 对照后 RELEASE。

### 2. 代理函数使用了不等价的底层操作

Agent 最初通过修改 client 配置再调用普通 `Do` 来模拟 redirects/timeout。M0 依据公开契约要求调用对应的 `DoRedirects`、`DoDeadline`、`DoTimeout`。Agent 修正；多个 probe fixture 错误期间 M0 保持静默，并正确识别 redirect-limit 的 HTTP 500 是契约要求，不是生产缺陷。

### 3. CORS wildcard 的值与优先级

M0 同时捕获 literal `*` 与 wildcard priority 两项冲突。Agent 修正并通过 wildcard/specific/nonmatch 对照后 RELEASE。随后仓库旧测试与新任务契约冲突时，M0 只允许修改那一条过期断言，没有要求生产代码迎合旧 oracle。

### 4. TLS 测试“退出 0 但没有验证行为”

初版 probe 把连接失败当成功，且 mutual TLS 没有执行握手。M0 要求 fail-closed、普通 TLS 成功、mTLS 无证书拒绝/可信证书接受及非法地址检查。Agent 重写后全部通过。

### 5. 发现完整测试命令掩盖真实退出码

Agent 用 `go test ./... -v 2>&1 | head -200` 支持全局完成。M0 指出退出码来自 `head` 且结果被截断，要求直接运行未掩盖的 `go test ./...`。真实运行暴露 CORS 旧 oracle 和 MIME/Accepts 兼容性回归。

### 6. 防止新 MIME 功能破坏既有 Accepts

Agent 一度准备特殊处理 `text`，这会违反新的标准库 fallback 契约。M0 在错误意图形成时 HOLD，要求保留 GetMIME 新行为并在 Accepts 交互边界做窄修复。Agent 实现 exact MIME 优先于 type wildcard，未修改既有 Accepts 测试；聚焦测试与完整 suite 均通过。

### 7. 删除错误的额外交付文档

Agent 自行生成的 `IMPLEMENTATION_SUMMARY.md` 错写 QueryBool 和 proxy API。M0 阻止把它作为交付物；因文档未被要求，Agent 删除该文件，没有触发无关测试循环。

### 8. 根任务释放保留残余未知

M0 只对公开任务明确要求的旧/新 TLS 等价性追加一次有界比较。比较成功后，Agent 在最终报告中准确描述证据并保留 proxy global-client 与 runtime prefork 的非关键不确定性；M0 随即 RELEASE，没有要求清空所有 UNKNOWN。

## 阶段裁决

### 成立

- H1 在第二种真实任务上维持了完整根任务模型，并正常结束。
- 多次纠偏改变了后续生产实现、测试 oracle、测试执行方式或交付物，具有明确行为 uptake。
- 它复现了人工监察重点：测试判别力、证据生成过程、因果诊断、提醒后持续观察、局部释放但根任务保留。
- 与 GX 不同，本轮没有因 UNKNOWN 清零而无限验证；最终保留 1 项 UNKNOWN 仍允许完成。
- Native verifier 满分，说明这些干预至少没有破坏真实结果，并与正确完成一致。

### 尚不能宣称

- 单分支 1.0 不能证明 M0 相对 B0 的统计显著提升。
- 历史自然分支 0.75 不是同时间、同随机性的严格配对对照。
- 68 分 58 秒显著长于历史自然分支约 7 分 27 秒；M0 是能力上界而非低成本方法，这一成本不能在后续论文实验中忽略。
- FBR 已被长期用于方法开发，不能作为未见任务泛化证据。

## 完成条件核对

- [x] 固定 H1，无针对任务修改
- [x] 完整真实 GenericAgent 运行
- [x] 无在线 checker 泄漏
- [x] 产生可归因的持续纠偏
- [x] 正常终止而非超时
- [x] Native verifier 7/7、reward 1.0
- [x] 保留 residual UNKNOWN 而非无限验证
- [ ] 跨来源确认完成（尚余 DuckDB、SymPy、install-windows）
- [ ] M0 最终冻结门禁完成

## 原始产物

- Campaign：`long_context_bench/output/m0_h1_cross_task_fbr_v2_120m/`
- Trial：`jobs/m0-h1-fbr-v2-120m/fbr-2.43.0-roadmap__6SDDXLK/`
- Monitor：`agent/m0_monitor/`
- Native reward：`verifier/reward.txt`
- Proof manifest：`runs/m0-h1-fbr-v2-120m/manifest.json`

## 停止点

FBR 独立阶段已完成。按用户要求在此停止，不自动启动 DuckDB。
