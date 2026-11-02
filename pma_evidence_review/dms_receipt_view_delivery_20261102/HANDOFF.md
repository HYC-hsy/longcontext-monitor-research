# 仅离线交接

本轮无真实运行许可。用最终回复固定SHA干净检出，候选仍dms-inspired-v1；不要启动模型/Task/P2/eval、额外真实冒烟、旧组或另一线程任务。

```powershell
git -c core.autocrlf=false fetch origin pma-dms-receipt-view-20261102
git switch --detach <FINAL_SHA>
git config --local core.autocrlf false
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --dms --report $FreshReport
if ($LASTEXITCODE -ne 0) { throw 'Stop and preserve offline failure' }
```

应77项通过。核对MANIFEST和SOURCE_IDENTITY全部63项，重新生成source_identity(candidate='dms-inspired-v1')时commit为最终检出SHA，文件hash须相同。测量脚本需要固定公开ZIP；输出目录/文件必须新建，不能覆盖历史结果。不能把公开投影临时重关联目录当生产原件。

SYSTEM/schema及read预算不变；新展示仅存后组重建。头尾可能仍省略有用中间内容，分页可读全部但预算不保证读完。P2尚未适配此展示，不作下游收益结论。后续真实批次由主线程另行安排。

公开只允许审查后的投影：排除profile、凭据、私有端点、隐藏推理/signature和source_links.secret。不能把测量临时目录或整个原运行目录直接上传。
