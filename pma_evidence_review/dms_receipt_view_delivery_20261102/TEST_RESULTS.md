# 当前离线验收

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --dms --report <fresh-report.json>
LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/measure_dms_receipt_view.py --archive <public-zip> --output <fresh-measure.json>
```

当前本地641b54e与固定远端f66005c源码tree相同，两个最终检查均80 tests/0 errors/0 failures/0 skipped。旧73项加展示7项，无可选依赖替身。覆盖宽内外dict、多空/仅ID回执、完整序列化上限、继承/顺序标签、长行/多行/CRLF/Unicode、B01完整stdout与B04失败、配对/未知格式、预览只读、旧source/keep/delete/分页边界。中间分配实现曾失败，原件本机保留；这些失败未冒称通过。当前变更源码+测试+脚本163行增删，低于600。

receipt-cap-final2.*及receipt-cap-remote.*为当前80项原始输出的公开投影，仅替换本机task根目录为<WORKSPACE>，原件hash见IDENTITIES。旧receipt-view-checked3/remote.*为587第一版77项历史，不是本版证据。原本已知U/A问题未改；未扩大跑旧472全套。

完整重建输入精确长度如下（Unicode字符，另列UTF-8增量）：

|案例|旧字符|新字符|字符增量|UTF-8字节增量|
|---|---:|---:|---:|---:|
|01-local-success-scope|23353|25955|2602|2602|
|02-checkpoint-not-new-install|24814|26481|1667|1679|
|03-no-new-result-history|28800|31473|2673|2787|
|04-counterevidence-to-old-claim|29600|32456|2856|3444|
|05-distinct-executions-same-output|4050|3812|-238|-238|
|06-optional-read-preserve-correct-memory|3338|3346|8|8|


B01完整1615字符stdout保留，B04仍有失败原文；算法无对应词。每选中事件的实际完整JSON<=原预览序列化长度+512，逐项见MEASUREMENTS。新分区仍增加部分输入，未声称零成本；总视图没有另加全局总量硬限，组/事件数量仍可增长，大bank未做规模优化。

真实模型/Task/P2/eval均0，假客户端及fixture不构成模型语义效果。没有测删早期经历/保留旧错误的改进；GAP新候选后续单独验收。
