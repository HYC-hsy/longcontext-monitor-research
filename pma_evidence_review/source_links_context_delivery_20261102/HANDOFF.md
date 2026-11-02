# Windows 离线交接

使用最终回复的固定交付 SHA。保持已有依赖环境，不加载真实 profile，不用 authorize-real-p1，不跑 Task/P2/eval/旧真实组。源码提交 b2bc53856863c971107fa02fc57aae60f142be33；材料尾提交不改运行源码。

```powershell
git -c core.autocrlf=false fetch origin pma/source-links-context-v1
git switch --detach <FINAL_DELIVERY_SHA>
git config --local core.autocrlf false
git status --porcelain
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --source-links-context --report <FRESH_REPORT_JSON>
if ($LASTEXITCODE -ne 0) { throw 'Stop: offline verification failed' }
```

按 MANIFEST 验证材料/代码，重建 source_identity(candidate='source-links-context-v1')，62 文件哈希应与 SOURCE_IDENTITY 相同，code_commit 是当前交付 SHA。旧候选 source-links-v1 和默认 source-read 的源码身份须在本 checkout 重建，不能挪用旧源码哈希清单。

仅需 CLI 接线验证时：

```powershell
& $P1Python -B pma_evidence_review/tools/run_p1_source_case.py --candidate source-links-context-v1 --mode scripted --case $FrozenCasePath --output $FreshPrivateOutput
if ($LASTEXITCODE -ne 0) { throw 'Stop and preserve terminal result' }
```

新输出目录不可重试覆盖。读源最多四次、续轮最多两次/三次逻辑 P1 调用，末轮 write-only；两视图共用预算。真实实验的启动/参数另行安排。原件与窗口保留；不能直接公开整个运行目录：source_links.json 含游标签名 secret，须去除凭据/profile/私有端点/隐藏推理及签名，并为公开投影重算哈希。
