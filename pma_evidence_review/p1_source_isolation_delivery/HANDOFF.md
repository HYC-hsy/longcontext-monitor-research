# Windows 开发线程交接（先审阅，真实批次尚待授权）

本文件不是当前真实运行许可。先使用最终交付回复的固定 SHA 干净检出；源码固定于 9e05fe51ee7375f2c4f0a6127aa7519aa463faea，交付尾提交只加材料。保留旧失败批次，不覆盖目录，不打断其他线程，不改原六例。

```powershell
git -c core.autocrlf=false fetch origin pma-p1-source-read-20261101
git switch --detach <FINAL_DELIVERY_SHA>
git config --local core.autocrlf false
git status --porcelain
# 使用既有真实依赖环境，不能以缺包替身放宽：
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --report <NEW_OFFLINE_REPORT>
if ($LASTEXITCODE -ne 0) { throw 'Offline verification failed' }
```

核对 MANIFEST 的所有文件、SOURCE_IDENTITY 的 59 项当前源码及原 cases/INDEX；重新运行 runner 的 source_identity，code_commit 应是最终检出 SHA，源码哈希应逐项相同。首请求前核对实际渲染输入／提示／schema／源码／案例哈希和参数 unknown 项，使用既有 Claude Opus 4.8 profile；不公开 profile 或端点。P1 输入外层有历史数据标签，实际历史文本仍在，不能声称已清洗。

主线程审阅并明确授权后，才可按以下单例模板在 INDEX 顺序串行执行新六例批次：

```powershell
# $P1Python、$P1ProfilePath 指向既有 Python 与私有 profile。
# $P1ResultRoot 为全新批次目录，每例输出目录必须不存在。
& $P1Python -B pma_evidence_review/tools/run_p1_source_case.py `
  --mode real --authorize-real-p1 --profile-file $P1ProfilePath `
  --case (Join-Path 'pma_evidence_review/p1_source_read_delivery/cases' $CaseFile) `
  --output (Join-Path $P1ResultRoot $CaseName)
if ($LASTEXITCODE -ne 0) { throw 'Stop batch; preserve this case and report' }
```

每例一次，最多两次逻辑 P1 调用（初始＋仅读源后的续答）、两次读源；全批最多十二次逻辑调用。读源不强制；继承客户端重试如无法关闭如实记 unknown／实际信息，逻辑调用不等于 HTTP 数。工程失败保存并暂停后续，不外层重发、不修输出追认、不额外冒烟、不重复采样、不跑旧组／Task／P2／原生评价。

保留每例完整可见请求、响应、tool calls/results、来源读取、操作、bank_after、终态、usage 和参数；保留私有原件，公开投影排除隐藏推理／签名、凭据、完整 profile、端点。新批次与首轮失败并存；完整投影和索引上传同仓库独立分支，远端回读逐文件字节/hash。语义效果由父线程审计，不以模型调用数或读源次数宣布收益。
