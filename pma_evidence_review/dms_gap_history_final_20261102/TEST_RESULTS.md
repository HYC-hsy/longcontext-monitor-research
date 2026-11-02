# 最终离线验收

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --dms-gap-index --report <fresh-report.json>
```

本地f05707d与固定远端bbc225f9完整tree相同；final100及remote100各100 tests，0 errors/failures/skips。旧73＋展示8＋GAP7＋history12，无可选依赖替身。使用既有真实依赖strict环境及假客户端/禁网保护；fixture执行成功不是语义评分。原六例实际组装的system/schema/输入hash与no-op bank一致，见CASE_REQUESTS；未真实重跑六例。

覆盖：pending空/超长/跨category拒绝、短多行原样保存、旧协议和P2字节隔离；完整JSON预览硬限、B01/B04可见fixture、empty/ID-only/Unicode；来源/别名/删除一致、写失败停批；输入窗口不回写、仅获H未read即引用、原子cited边、M继承、删除旧active后直达；typed legacy与冻结pending不受同ID当前metadata污染；坏coverage保留sources及合法explicit H；非法/未发放/跨任务H、原子目录分页/重开、grant/citation故障停批；短两读三轮和长来源仍partial/预算不足不伪装读完。

当前实现分步验证/提交：22行（pending格式/末句）、348行（helper底座）、326行（本地适配）、89行（故障隔离源码测试）、178行（explicit边）、6行（关闭措辞），每步<600。文档与机械报告另计。中间发现并修正页外追加解析metadata导致8065字符；最终工具结果连metadata一起<=8000。早期失败报告本机保留，未冒充通过。

公开dms-gap-closure-final2.* / dms-gap-closure-remote100.*只替换task工作根与host包安装根，原件字节数/hash见IDENTITIES；不含profile/凭据/私有端点/隐藏思维/签名/游标签名secret。stdout中的mode=real engineering_error来自受禁网保护的合成CLI初始化失败测试，不代表真实请求。

未跑：真实模型、Task、P2、原生评价、旧模型组与旧472全套；已知U/A问题未动。未验证语义增益、删除策略收益、长历史规模优化或P2后续消费。新真实结果只能归因组合候选，不能拆给每项修改。
