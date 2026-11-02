# Windows交接：先离线，真实模板待主线程放行

不能仅凭本文件启动真实调用。主线程审查最终固定SHA后，才可使用第二段；本机实现阶段真实调用0。

## 1. 干净固定检出与离线

使用既有真实依赖环境，不装替身；替换下面路径及主线程提供的最终SHA。

```powershell
$P1Python = '<existing-python.exe>'
$FinalCommit = '<root-reviewed-final-SHA>'
git -c core.autocrlf=false fetch origin pma-dms-gap-index-20261102
git -c core.autocrlf=false switch --detach $FinalCommit
if (git status --porcelain) { throw 'Use a clean isolated checkout' }
$env:PMA_TEST_STRICT_IMPORTS = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
$D = 'pma_evidence_review/dms_gap_history_final_20261102'
$m = Get-Content "$D/MANIFEST.json" -Raw | ConvertFrom-Json
foreach ($p in $m.files.PSObject.Properties) {
  if (-not (Test-Path -LiteralPath $p.Name)) { throw "Missing $($p.Name)" }
  $h = (Get-FileHash -LiteralPath $p.Name -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($h -ne $p.Value.sha256 -or (Get-Item -LiteralPath $p.Name).Length -ne $p.Value.bytes) { throw "Mismatch $($p.Name)" }
}
$FreshReport = '<new-offline-report.json>'
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --dms-gap-index --report $FreshReport
if ($LASTEXITCODE -ne 0) { throw 'Preserve offline failure; stop' }
$FreshIdentity = '<new-source-identity.json>'
& $P1Python -c "import sys,json,pathlib; from pma_evidence_review.tools.run_p1_source_case import source_identity; pathlib.Path(sys.argv[1]).write_text(json.dumps(source_identity(candidate='dms-gap-index-v1'),indent=2),encoding='utf-8')" $FreshIdentity
if ($LASTEXITCODE -ne 0) { throw 'Source identity failed' }
$new = Get-Content $FreshIdentity -Raw | ConvertFrom-Json
$old = Get-Content "$D/SOURCE_IDENTITY.json" -Raw | ConvertFrom-Json
if ($new.code_commit -ne (git rev-parse HEAD)) { throw 'Wrong commit identity' }
foreach ($p in $old.source_files.PSObject.Properties) {
  if ($new.source_files.PSObject.Properties[$p.Name].Value -ne $p.Value) { throw "Source mismatch $($p.Name)" }
}
```

应100项通过、65项runtime文件一致。保存的SOURCE_IDENTITY对应已测源码bbc225f9；最终文档SHA仅多文档，重新生成code_commit应为实际检出SHA，file hashes须同。CLI参数可用--help离线查，不读私有profile。

## 2. 真实P1模板：仅待主线程明确放行后

仅此新候选、原INDEX六例，严格串行各一次；最多18次逻辑P1调用/24次预算内读源（实际可少；模型提交的额外读请求可被拒并须另记），不加真实冒烟/重复采样/旧组/Task/P2/评价。不强制read；不能为演示工具改输入。既有Claude Opus4.8 profile的真实model/可取得参数在首请求前落盘，未知标unknown；profile未设置预算记uncapped，不声称新设token/time上限。既有客户端HTTP重试如不能单独关闭如实记录，逻辑轮数不是物理请求数；不另加外层重发。

```powershell
$P1Profile = '<existing-private-profile.json>' # 包含claude_monitor_opus48，不上传
$BatchRoot = '<new-private-six-case-output-directory>'
if (Test-Path $BatchRoot) { throw 'Do not overwrite or retry an allocated batch' }
New-Item -ItemType Directory -Path $BatchRoot | Out-Null
$Cases = 'pma_evidence_review/p1_source_read_delivery/cases'
$index = Get-Content "$Cases/INDEX.json" -Raw | ConvertFrom-Json
if ($index.cases.Count -ne 6) { throw 'Unexpected case count' }
foreach ($case in $index.cases) {
  $path = Join-Path $Cases $case.file
  if ((Get-FileHash $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $case.sha256) { throw 'Frozen input changed' }
  $out = Join-Path $BatchRoot ([IO.Path]::GetFileNameWithoutExtension($case.file))
  & $P1Python -B pma_evidence_review/tools/run_p1_source_case.py --candidate dms-gap-index-v1 --mode real --authorize-real-p1 --profile-file $P1Profile --case $path --output $out
  if ($LASTEXITCODE -ne 0) { throw 'Preserve this case and stop; no retry or following case without direction' }
}
```

保留每请求system/schema/prompt、原模型参数、tool calls/results、完整可见续答、每页source/H返回、操作/对账、bank_after、来源存档/窗口、terminal、可得usage及物理请求情况。不要修输出追认；运行线程只报执行事实，语义审计交主线程。两轮读不足时保留partial/cursor，不提高预算或隐藏补读。

公开前按允许字段投影；保留私有原件。可公开本轮可见返回/工具回执/输入窗口/来源关系和报告；排除完整profile、凭据、私有端点、隐藏thinking/reasoning/signature、client原始provider日志及source_links.secret。H本身可保留用于审计，但签名密钥不公开。公开投影重算逐文件hash，记录原件与投影关系，不冒充原HTTP或可直接复用的生产存档。ZIP/SHA/CRC/逐文件hash推送后远端回读核验。
