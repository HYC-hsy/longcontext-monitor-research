> 当前为已授权发布、尚未完成最终验收的中间审查版。独立分支pma/upstream-compat-review-intermediate；源码固定提交见SOURCE_IDENTITY.json。

# 本地离线交接

工作树：`upstream-reminder-compat`；分支：`pma/upstream-reminder-compat-v1`。本轮已按用户明确授权发布中间版；39c复审修补详见INTEGRITY_REPAIR.md；固定远端交付SHA见最终回复。实际efab基线导入后完整树与远端固定提交一致，来源归档保持原样。当前源码身份在SOURCE_IDENTITY.json；原版差异和必要例外见UPSTREAM_COMPARISON.md，不要继续使用旧交付目录的源码哈希或181项清单。

本轮只离线验收；以下指令不会加载真实profile、启动模型、Task或评价。Windows开发线程在取得该中间版固定提交之后，使用现有Python3.12兼容环境执行（只读取本次独立分支，其他旧分支不等于此中间版）：

```powershell
$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
$py = '.\.venv\Scripts\python.exe' # 可改为已有兼容venv的绝对路径
if (!(Test-Path $py)) { throw '请设置已有PMA Python3.12环境路径。' }
& $py pma_evidence_review/tools/verify_reminder_delivery.py --delivery pma_evidence_review/upstream_compat_delivery_20261103
if ($LASTEXITCODE -ne 0) { throw '字节/身份校验失败。' }
$report = Join-Path $env:TEMP ('pma-upstream-compat-' + [guid]::NewGuid().ToString('N') + '.json')
& $py pma_evidence_review/tools/run_p2_requirement_checks.py --report $report
if ($LASTEXITCODE -ne 0) { throw '离线检查失败。' }
$r = Get-Content -Raw -Encoding UTF8 $report | ConvertFrom-Json
if ($r.tests_run -ne 207 -or !$r.successful -or $r.errors -ne 0 -or $r.failures -ne 0 -or $r.skipped -ne 0) { throw '测试数量或结果不符。' }
Write-Output "207/207; report: $report"
```

字节验收覆盖113个清单文件与69个运行源码；MANIFEST自身不自哈希。

依赖沿用Python3.12.13、dirhash0.5.0、litellm1.106.6、pydantic2.14.2、httpx0.28.1。必须保留LF源码字节；不能为了通过hash校验放宽生产校验。运行测试需要已有Git历史中的冻结基线，独立零历史的文件副本不能代替完整仓库验收。

直接P1 maintain/独立pipeline以及Task opt-in调用方式没有新增参数。显式传入observation时，它按原PMA API约定是原任务与最近轨迹组成的context；Task适配直接调用原版_get_memory_agent_context，独立pipeline默认也构造同样context。P1/P2模型继续使用本轮entry=M编号及返回的历史handle，不需要内部ID。最终提醒可在标签前后带普通说明；缺失/空标签按原版默认静默并记录警告，不发起修复调用。

普通模型错误保留原始输出、错误类型、调用计数和实际操作，不升级为整题致命；Task事件结果含memory_cycle_status，细节见requirement_cycles.jsonl和trajectory_memory。不要把memory_error/tool_error/selection_error当作正确不干预。持久化/来源绑定损坏、未决周期、执行结果不确定、audit写失败仍终止并留下失败记录。没有自动回滚已提交操作，也没有静默恢复损坏状态。

本轮三份可见输出只回放文本协议，不评价提醒事实是否正确。真实模型效果、完成率、真实Actor投递均未验证；暂不启动任何真实运行或重跑旧组。


拉取当前中间版（不要运行真实实验）：
```powershell
git fetch origin refs/heads/pma/upstream-compat-review-intermediate
if ($LASTEXITCODE -ne 0) { throw 'Fetch failed.' }
$sha = (git rev-parse FETCH_HEAD).Trim()
Write-Output $sha # 与交付回复中的固定SHA核对
$checkout = Join-Path (Split-Path (git rev-parse --show-toplevel).Trim() -Parent) ('pma-intermediate-' + $sha.Substring(0,8))
git -c core.autocrlf=false worktree add --detach $checkout $sha
```
这是继续人工检查和修改的中间版；207项为已有离线记录，不是最终验收批准。本次上传没有重跑模型或测试。
