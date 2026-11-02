# Windows：预检与真实 P1 入口

源码固定 f6a3982b73d4c7d657242cba4e6c0f3073848ff5；最终交付尾提交只加材料，完整 SHA 由最终回复给出。使用 A 的独立 checkout/worktree 和已有依赖环境，不改 B 的工作区。旧交付目录的身份/schema 仅是历史版本，本轮按本目录核对。

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

预期 90 tests、零 errors/failures/skips。核对 MANIFEST、INPUT_IDENTITIES 的六例原件及 SOURCE_IDENTITY 的 63 项运行源码。重建 source_identity(candidate='source-links-context-v1') 时，文件哈希须逐项相同，code_commit 则是当前交付 SHA。冻结 SYSTEM 与 TOOL_SCHEMA 也须匹配。不要安装缺包替身，不用旧 identity 代替本次核对。

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

该入口只跑 P1，不接 Task/P2/eval。两类读及历史 handle 共用四读、两续轮/三次逻辑调用，末轮 write-only；物理 provider 重试仍继承原客户端，不能把逻辑调用数当物理请求数或固定费用。大目录/窗口不保证本轮读完，partial/缺历史不自动判任务失败。

保留原始 bank、window、工具调用/回执、identity、终态和哈希。公开前做明确投影，不直接上传整运行目录：去掉 source_links.json 的签名 secret、私有 profile/凭据/端点、隐藏 provider 材料及未展示的调试内容；raw_generation_context 不应被误当完整可公开模型输入。公开投影另取哈希，原件私下保留。不得覆盖已有失败归档。
