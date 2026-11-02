# Windows 交接：当前只做离线验收

**本次修复尚待主线程复审，暂不启动真实验证。下面真实六例命令仅是后续预案，不构成当前启动许可。**

先交主线程审阅固定材料；Mac 本轮不启动真实调用。使用最终回复的远端 SHA，候选显式 dms-inspired-v1，不运行旧组、Task、P2、原生评价、额外冒烟或重复采样。

```powershell
git -c core.autocrlf=false fetch origin pma-p1-dms-20261102
git switch --detach <FINAL_SHA>
git config --local core.autocrlf false
git status --porcelain
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --dms --report $FreshOfflineReport
if ($LASTEXITCODE -ne 0) { throw 'Stop: offline failure' }
```

核对本目录 MANIFEST、SOURCE_IDENTITY 的62项和原 cases/INDEX。重新生成 source_identity(candidate='dms-inspired-v1')，code_commit 应为最终检出 SHA，文件 hash 与清单相同；旧清单不能跨 checkout 复用。

主线程审阅后由 Windows 开发线程，仅按原 INDEX 顺序串行跑新六例各一次，使用既有 Claude Opus4.8 私有 profile，不更换模型或修输出。$P1Python/$P1ProfilePath 是既有环境，$FreshBatch 是全新批次目录：

```powershell
& $P1Python -B pma_evidence_review/tools/run_p1_source_case.py --candidate dms-inspired-v1 --mode real --authorize-real-p1 --profile-file $P1ProfilePath --case (Join-Path 'pma_evidence_review/p1_source_read_delivery/cases' $CaseFile) --output (Join-Path $FreshBatch $CaseName)
if ($LASTEXITCODE -ne 0) { throw 'Stop batch and preserve case' }
```

每例最多4次读源、3次逻辑P1调用，全批最多18次逻辑调用。工具不强制调用，预算未设置的模型参数如实 unknown/uncapped；继承客户端 HTTP 重试单独记录，不能当作逻辑轮数。工程故障暂停后续，禁止外层自动重试或补跑抹掉失败。初始六例及bank不能重写；case04未读完仍如实保留，case06原A/B不得偷偷补成更容易的新输入。

保存完整可见请求、模型正文/tool calls、工具回执、实际读页及cursor、操作、bank_after、中央原事件、typed legacy引用、组原文展开及当前视图、终态、usage和可取得模型参数。bank_after.content 是索引，不能只上传索引却漏原文。私有原件不动，公开投影排除完整profile、凭据、私有端点、隐藏推理/signature，source_links.json的secret必须删除；不能整目录直接上传。投影明确标注删减并重算逐文件hash，上传后远端回读。语义审计由主线程负责，不用操作数量或无格式错误宣布收益。

本次接口修复固定源码为053cff29aa2c03c65c785a3f2f63dae4a4ac5bc9。离线应为73项；当前不自动重跑已有案例，DMS真实批次尚未开始。后续命令仍须主线程明确放行；日志同时保留原始memory_id与工程resolved_memory_id，任何协议/删除错误后核对后续操作未执行。
