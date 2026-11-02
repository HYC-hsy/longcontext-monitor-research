# 离线验收与长度

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --dms --report <fresh-report.json>
LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/measure_dms_receipt_view.py --archive <public-zip> --output <fresh-measure.json>
```

本地3a9015e与固定远端3b34b6a的完整tree相同。两次最终检查均77 tests、0 errors、0 failures，包含旧73项。初次77项仅旧DMS清单数仍断言62而失败，新增展示模块后正确更新为63；没有降低校验。曾测得初版JSON包装增量过大，收紧重复元数据及固定片段分配后采用下表最终版本。

覆盖真实B01/B04选中事件预览及配对动作、外壳success/exit0和stdout失败同时保留、多调用反序不串配、未知/超长/Unicode/缺回执、Actor历史不能占掉回执、原文区间可追溯、预览不改事件状态、原始字段读回保真；旧分页/哈希/ID/keep/delete与候选回归继续通过。真实LLM零，假客户端不能证明收益。未运行Task/P2/eval或真实旧组，旧472全套未扩大运行，已有U/A问题未动。

六例公开投影重建输入精确长度（不是原运行输入）：

|案例|旧字符|新字符|字符增量|UTF-8字节增量|
|---|---:|---:|---:|---:|
|01-local-success-scope|23353|27029|3676|3754|
|02-checkpoint-not-new-install|24814|24870|56|68|
|03-no-new-result-history|28800|31745|2945|3079|
|04-counterevidence-to-old-claim|29600|33048|3448|4086|
|05-distinct-executions-same-output|4050|3158|-892|-892|
|06-optional-read-preserve-correct-memory|3338|3019|-319|-319|


B01 event_7和B04 event_8在before该事件预览都无目标失败原文，after回执分区均有。不能解释为当轮初始输入没见过；没有语义评分或新模型结果。每页原始读源仍8000字符，预算不改。

receipt-view-checked3.*和receipt-view-remote.*为原始检查输出的公开投影，仅替换本机任务根目录为<WORKSPACE>；原始文件/hash本机保留，IDENTITIES记录原件元数据，MANIFEST对公开投影取hash。生成fixture/测量/清单为数据；本步全部增删398行，连同数据亦不超过600。
