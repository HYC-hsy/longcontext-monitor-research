# 仅离线交接

本材料无真实运行许可。使用最终回复固定SHA干净检出，不启动模型/Task/P2/eval、真实冒烟、旧组或另一线程任务。

```powershell
git -c core.autocrlf=false fetch origin pma-dms-receipt-view-20261102
git switch --detach <FINAL_SHA>
$env:PMA_TEST_STRICT_IMPORTS = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --dms --report $FreshReport
if ($LASTEXITCODE -ne 0) { throw 'Stop and preserve offline failure' }
```

应81项通过。核对MANIFEST与SOURCE_IDENTITY63项；source_identity(candidate='dms-inspired-v1')重新生成时commit为当前检出，源码文件hash须一致。报告及测量输出用新路径，不覆盖历史。公开临时重关联目录不能当生产原件。

本轮SYSTEM/schema、三工具及4读/3调用预算不变。展示硬限是每事件完整JSON，整体bank无新增总量上限；可能省略中间材料，raw分页仍保真。P2未适配索引。后续真实批次和GAP策略须另安排。

公开前排除profile、凭据、私有端点、隐藏推理/signature、source_links.secret。仅上传审查投影，不直接上传整个原运行目录。
