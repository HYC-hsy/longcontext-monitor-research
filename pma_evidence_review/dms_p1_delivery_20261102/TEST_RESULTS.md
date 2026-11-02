# 离线验收

命令：
```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --dms --report <new-report.json>
```

本地 1105b52 与固定远端 576ab6b0 的完整 tree 一致，两次最终检查均 69 tests、0 errors、0 failures。包含原 58 项和新增 11 项；使用既有真实安装依赖、网络守卫和假 provider，未用缺包替身；沿用既有 typing.TypedDict→typing_extensions.TypedDict 测试兼容。

新增检查覆盖原任务段落逐字拼回、同输出不同执行与跨 workspace、旧断言保留但不升级、checkpoint 重复、单步经历、A+B legacy 组及删除后回查、长生成窗口分页、错误来源后阻止删除、准备阶段与 replace 后异常对账、持久化重开、原六例无操作保持初始bank、实际客户端三轮接线且工具数3/3/2、禁止新status/free-summary工具。实际 CLI 固定提交严格身份核验62项，六例 scripted 各一次，均 completed，每例一次假调用、零操作。

一次中间 66 项检查因新增合成 profile 缺 temperature 报 KeyError，补齐测试夹具后重跑通过，没有放宽生产检查。该失败原件留本机，当前最终修复报告是 dms-fix-final-local 与 dms-fix-remote；旧 dms-step1c/dms-remote 的66项报告保留为历史，不当作当前69项结果。完整旧472项、完整Task、P2、评价、真实模型未跑，已知旧U/A夹具问题未动。首步源码／测试／配置为412行增删，本次三项修复为87行，均未超过600。

dms-fix-final-local.* / dms-fix-remote.* 为当前69项完整离线输出的安全公开投影，仅把本机任务根目录替换为 <WORKSPACE>；原件及其哈希保留。IDENTITIES 记录原始输出字节/hash，MANIFEST 对公开投影重算hash。CLI stdout/stderr 无需修改。没有以固定假输出通过声称真实语义效果。

Windows 语义审计仍逐例看：01是否保留局部范围；02 checkpoint 是否重复计执行；03自述是否仍被当验证；04旧错误断言是否保留及来源是否读完整；05独立执行是否均保留；06 A+B 是否同时成组。schema没有Task complete字段不等于案例正确；漏选、错误保留和删掉有用记忆都需记录。

本次新增三项回归：超过阈值的原文关键词组仍展示且旧候选BM25开关不变；错task/cycle（含绑定身份）的合法digest窗口全部拒绝；旧save/status/未知工具后停止删除但此前keep仍逐操作保留。
