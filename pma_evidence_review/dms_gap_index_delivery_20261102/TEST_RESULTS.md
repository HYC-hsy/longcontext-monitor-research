# 离线结果

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --dms-gap-index --report <fresh-report.json>
```

本地fabbbb1与远端3607e25完整source tree相同；最终两次87 tests、0 failures/errors/skips。旧73＋展示8＋GAP6，无可选依赖替身。原六例只用无操作假客户端走实际runner，请求schema/system/任务/hash见CASE_REQUESTS，初始bank及六JSON字节不改。此项不是六次真实模型，也不是语义评分。

新测覆盖缺pending/空白/超长/换行/非法category、知识经验多pending/自由content拒绝；失败save后delete停批；短GAP在bank/display/read中typed而非事实；真实工具适配器形状的读源→文本续答→同M删除；绑定故障无半提交并重开；候选存档错配拒绝；P2合同文件字节相同。旧source/分页/预算/未知工具与别名失败路径继续由81项覆盖。

首轮报告因新测试误读tool_results外层status出现8个测试错误，及发现新候选页字段重开次序不同出现1失败；修正receipt断言为真实result.status，并在新候选稳定字段序后重跑通过，未放宽内容保留要求。原始失败报告本机保留。公开final/remote输出仅替换任务工作根为<WORKSPACE>，原件hash见IDENTITIES。

源码步骤246行增删（含新runtime65、测试127、runner/小hook），小于600；展示小修另步47行。文档/生成检查结果另计。真实模型/Task/P2/eval均0，旧472全套未扩大运行，已知U/A问题未动。未验证未决项语义、模型保留行为或history helper；不宣称收益。
