# Windows：预检与真实 P1 入口

源码固定 22fb79813bf64d4c42b6b2f6408403bf807be3a7；最终交付尾提交只加材料，完整 SHA 由最终回复给出。使用 A 的独立 checkout/worktree 和已有依赖环境，不改 B 的工作区。旧交付目录的身份/schema 仅是历史版本，本轮按本目录核对。

```powershell
$env:PYTHONUTF8 = '1'
Set-Location $RepoA
if (git status --porcelain) { throw 'Stop: preserve existing work first' }
git -c core.autocrlf=false fetch origin pma/source-links-context-v1
git switch --detach $DeliverySha   # 最终回复的完整交付 SHA
git config --local core.autocrlf false
$OfflineReport = Join-Path $env:TEMP ('p1-history-' + [guid]::NewGuid().ToString('N') + '.json')
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --source-links-context --report $OfflineReport
if ($LASTEXITCODE -ne 0) { throw 'Stop: offline verification failed' }
```

预期 95 tests、零 errors/failures/skips。核对 MANIFEST、INPUT_IDENTITIES 的六例原件及 SOURCE_IDENTITY 的 63 项运行源码。重建 source_identity(candidate='source-links-context-v1') 时，文件哈希须逐项相同，code_commit 则是当前交付 SHA。冻结 SYSTEM 与 TOOL_SCHEMA 也须匹配。不要安装缺包替身，不用旧 identity 代替本次核对。

以下只给 Windows 执行线程使用；本机未执行真实调用。按主线程安排的案例、模型和预算运行，每次一个案例、新私有输出目录，失败即停，不做外层重试或额外冒烟，不重跑旧对照组：

```powershell
# $ApprovedCase 是既有冻结 INDEX 中本次安排的一例；$FreshPrivateOutput 必须尚不存在。
# $PrivateProfile 是既有私有 profile 文件，不复制进仓库或交付包。
& $P1Python -B pma_evidence_review/tools/run_p1_source_case.py `
  --candidate source-links-context-v1 --mode real `
  --case $ApprovedCase --output $FreshPrivateOutput `
  --profile-file $PrivateProfile --authorize-real-p1
if ($LASTEXITCODE -ne 0) { throw 'Stop and preserve terminal/result; do not retry the allocated output' }
```

该入口只跑 P1，不接 Task/P2/eval。最多四次总 read，但只有 r0/r1 两个可串行发现、跟进的读取轮，r2 write-only；并非可串行读四页。sources 目录可能排在大来源之后，长 origin 只能如实 partial，不保证任意祖先一次维护内可达。helper 的百页循环只是传输测试。物理 provider 重试仍继承原客户端，不能把三次逻辑调用当物理请求数或固定费用；缺历史不自动判任务失败。

保留原始 bank、window、工具调用/回执、identity、终态和哈希。公开前做明确投影，不直接上传整运行目录：去掉 source_links.json 的签名 secret、私有 profile/凭据/端点、隐藏 provider 材料及未展示的调试内容；raw_generation_context 不应被误当完整可公开模型输入。公开投影另取哈希，原件私下保留。不得覆盖已有失败归档。

H1 只读表示不能修改记忆内容。首次授予会持久化 grant 元数据，写失败仍保留工程错误；不是零存储副作用。source_ids 中明确引用的 H 与 sources 原子保存在 ref，标为输出引用，不回写生成前 input coverage。GAP/status 分工是本轮授权的语义提示调整，独立差异见 GAP_STATUS.diff；收益仍待真实验证。
