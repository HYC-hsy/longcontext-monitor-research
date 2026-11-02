# Windows 交接：本次仅离线验收

没有真实批次授权。不要启动真实模型、Task、P2、评价、额外真实冒烟或旧组，不影响其他线程。使用最终回复固定交付 SHA；源码固定 8b9dcf3e334ceaba4c1729cdaa06d12474b59529，交付尾提交只加材料。

```powershell
git -c core.autocrlf=false fetch origin pma-p1-source-links-20261102
git switch --detach <FINAL_DELIVERY_SHA>
git config --local core.autocrlf false
git status --porcelain
# 用既有真实依赖环境，不安装缺包替身：
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --source-links --report <NEW_REPORT_JSON>
if ($LASTEXITCODE -ne 0) { throw 'Stop: offline verification failed' }
```

核对 MANIFEST 全部文件和 SOURCE_IDENTITY 的 61 项运行源码，重建 source_identity(candidate='source-links-v1')，code_commit 为当前交付 SHA，文件哈希逐项匹配。默认 source-read 是旧入口，本候选须显式 --candidate source-links-v1。schema/system/hash 见同目录文件；原六例 INDEX 和输入文件不得改写。

如需实际 CLI 离线复验，仅用 --mode scripted，以原 cases/INDEX 顺序一次一个、新输出目录；不得加 --authorize-real-p1 或加载私有 profile。例：

```powershell
& $P1Python -B pma_evidence_review/tools/run_p1_source_case.py --candidate source-links-v1 --mode scripted --case $FrozenCasePath --output $FreshCaseOutput
if ($LASTEXITCODE -ne 0) { throw 'Stop and preserve engineering error' }
```

输出目录已存在即拒绝，出现工程故障保留终态后停止，不外层重试。未来真实运行的数量、题目和参数另行安排。读源每维护最多四次、最多三次逻辑 P1 调用，每页完整 JSON ≤8000 Unicode 字符；budget/partial/unassociated 不能当语义不通过或完整核验。

保留内部 bank／绑定／事件原件和哈希。公开投影必须删除 source_links.json 内 secret（游标签名密钥），排除完整 profile、凭据、私有端点、隐藏推理／签名；不能直接上传整个运行目录。投影明确标注删减，并为公开文件重算哈希。来源回执和可见模型记录由之后另行授权的批次完整保存，语义审计由父线程负责。
