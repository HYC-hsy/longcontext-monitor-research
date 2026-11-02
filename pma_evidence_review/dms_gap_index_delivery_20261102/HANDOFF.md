# 审查节点：仅离线

本节点history helper尚未接入，不能作为最终组合候选或真实模型批次启动指令。

```powershell
git -c core.autocrlf=false fetch origin pma-dms-gap-index-20261102
git switch --detach <FIXED_REVIEW_SHA>
$env:PMA_TEST_STRICT_IMPORTS = '1'
$env:LITELLM_LOCAL_MODEL_COST_MAP = 'True'
& $P1Python -B pma_evidence_review/tools/run_p1_source_checks.py --dms-gap-index --report $FreshReport
if ($LASTEXITCODE -ne 0) { throw 'Preserve failure and stop' }
```

应87项；复验旧dms-inspired-v1可用--dms（81项）。新候选名dms-gap-index-v1，完整schema/prompt及64项source identity以本目录为准，旧交付清单不可跨checkout。原六冻结输入不改、不重跑真实旧组。

待主线程提供已测固定history helper后，仅接必要只读入口并补组合离线验收，再另交付未来真实Windows批次指令。不要启动Task、P2、模型、评价或额外真实冒烟，不加载私有profile。

公开投影排除profile/凭据/私有端点/隐藏思维/signature/source_links.secret；read回执为有界原文页，不能冒充原始HTTP。
