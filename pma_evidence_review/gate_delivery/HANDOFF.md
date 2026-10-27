# 开发线程接收：PMA citation 门禁双模式

当前为本地审阅候选，尚未发布；等待最终回复中的 exact SHA。不得以此文档自行启动真实运行。
本轮只有实现与离线 fake 验收，无真实模型/Task/评价/正式记忆写入。

## 接收与复验

从独立分支 research/pma-citation-gate-v1-20261027 的最终 exact SHA 建新 worktree，
保护旧工作树，不reset/force-push。使用现有Python。此次实际Python3.11.15/macOS arm64；
Windows已有socketpair/LF/longpaths回归保留，但没有新增Windows实机验收。

测试新增实际依赖shortuuid、rank-bm25、rpds-py及固定vendor宿主的既有依赖；不修改项目依赖配置。
当前独立测试依赖目录为工作区gate-test-deps，旧regex目录为offline-deps。环境版本见ENVIRONMENT.json。
不读取profile。测试runner为未安装包的Harbor版本元数据、Python<3.12 TypedDict做仅测试导入适配，
不改vendor、不替换宿主执行逻辑，不称已验证任意生产环境。生产按现有宿主支持环境运行。

```bash
PYTHONDONTWRITEBYTECODE=1 LITELLM_LOCAL_MODEL_COST_MAP=True \
PYTHONPATH=.:../offline-deps:../gate-test-deps \
/opt/homebrew/bin/python3.11 -m pma_evidence_review.tests.run_gate_regressions
```

已有依赖齐全的Windows环境可在checkout根运行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:LITELLM_LOCAL_MODEL_COST_MAP='True'
python -m pma_evidence_review.tests.run_gate_regressions
if ($LASTEXITCODE -ne 0) { throw 'Offline regression failed; do not run models' }
```

runner包含原审核器全套及8个受影响PMA回归模块；socket guard禁止网络连接（仅保留Windows
asyncio内部本机socketpair）。fake worker用临时文件spool和合成事件，不启动容器/Task/evaluator。
日志中的fixture错误堆栈是故意模拟失败测试，最终总结果以OK为准。

## 配置

默认不设置citation_review_gate：原baseline不变。
显式方法仍为pma_gap_evidence_v1，carrier B；只允许以下两种附加模式：

- `--citation-review-gate gate-only`：repair_limit=0，但有相同最终控制回执。
- `--citation-review-gate gate-one-repair`：repair_limit=1，同一原整理者最多修订一次后复审。

共同审核策略固定semantic-support-one-sentence-v1；不是旧长段候选，不运行benchmark来在线选策略。
共用纯request builder；A/旧B/单句29样本计划身份不变。模型/引用契约/默认参数不变。

以下是未来准备命令模板（需要既有真实输入位置，当前线程没有执行）：

```powershell
$Module='method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run'
python -m $Module prepare --help
```

在已有批准的single_run prepare命令中，保持Task/profile/证书/运行参数原值，显式加入：
`--condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate gate-only`
或`--citation-review-gate gate-one-repair`。两模式分别使用全新输出目录及manifest。
原CLI其他必需参数以当前--help及既有运行指令为准，不猜测私有路径或用旧证书冒充本轮认证。

plan/config冻结mode及共享gate源码hash，配置hash纳入原授权绑定。batch_controller透传至
live_launcher、worker_main；Harbor核对mode与冻结manifest，worker ready回显mode，任何不匹配失败。
旧launcher无该flag即不支持，不能去掉flag绕过后把baseline称gate。
直接worker_main也接受同名flag，但它是宿主内部入口，不替代真实运行授权与认证。

## 真正整体实验之前

接收方需要另获真实模型、Task、官方评价及相应记忆运行的明确授权；必须完成既有
source/lifecycle认证，基于最终代码准备新manifest和授权。当前fake通过不代替这一步。
若原认证不覆盖新gate模式，应先报告并补离线认证，不关闭认证检查。

建议对照默认baseline、gate-only、gate-one-repair，固定其余任务/模型/输入协议。
两种gate的唯一开关差异为修订机会，均有相同下一轮commit回执。不要把删除暂缓混称已验证删除。
不要把审核supported率当Task效果；同时检查Task结果、错误记忆传播、旧值保留、gap积压、
准备跳过、工程缺失、repair撤回/仍拒绝、回执是否实际进入后续maintenance。
本轮未证明减少误放，也未证明整体效果。两题29条开发数据不代表泛化。

## 诊断文件与限制

worker私有archive的memory_payload/gap_visible_transport区分maintenance/citation_review/
citation_repair/selection。gate的独立citation_review目录保存实际requests/responses和gate_cycles；
episode gap_cycle附citation_gate_report。输入包schema为pma-live-citation-candidate-v1，
不伪造历史archive SHA。保留每attempt候选、原prompt hash、实际audit/repair请求hash、raw/status。
不要将这些审核日志作为Task观察重灌source catalog。

最终receipt是控制信息，待下一次maintenance；实际含入请求并取得非空响应仅证明送达，
不证明模型理解。无下一轮则pending，不额外调用。进程自动恢复/receipt replay尚未实现；
不要把重启当安全续跑，也不要自动重发写入。

本轮发布白名单仅源码、合成测试、说明和离线日志。真实结果以后若需上传，先确定具体
白名单与用户授权；不包含profile/private_client/凭据/未授权私有轨迹，不覆盖任何历史包。
