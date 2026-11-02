# 实测离线结果

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --source-links --report <fresh-report.json>
```

本地 d168b87 和远端 8b9dcf3e334ceaba4c1729cdaa06d12474b59529：各 55 tests、0 errors、0 failures。两者完整 tree 相同。包含旧 31 项 P1 检查和新增 24 项；真实 LiteLLM/profile 适配路径使用 fake provider 与网络守卫，验证三次逻辑调用的忠实文本续接，而非原生 messages 工具续轮。无缺包替身；沿用既有 typing.TypedDict→typing_extensions.TypedDict 测试兼容。

覆盖事件身份／同文不同调用、未知 ID、JSON 字符串命令显式 ID、tool_call_id、歧义配对、请求冻结别名、批内 save/delete 与换号、错误来源后停止删除、继承及多跳未知、删除后原事件保留、旧条目不能暗读、状态冻结与截断绑定、未关联不报完整、只读性、超大 Unicode 分页逐字拼回、游标无效／跨任务／换目标／来源变化、替换前后故障重开对账、末轮收束及四次预算、实际新源码清单缺失／改字节拒绝。

实际干净固定源码 CLI：六个原冻结案例依 INDEX 串行，以 --candidate source-links-v1 --mode scripted 各一次，全部 completed，每例一次假调用、零操作。源码身份严格核对 61 文件；命令 stdout/stderr 与每例请求 system/schema/prompt 哈希在 SCRIPTED_CLI.json。案例仍是原开发材料，无模型语义评分；不把 no-op 预设输出当案例正确。

工程提交规模：第一步 346 行增删；第二步 447；第三步 386（均不超过 600）。文档、schema、清单和结果为生成／说明材料另计。保留已知旧 U/A official_source_git 夹具问题，不放宽或声称修好。完整旧 472 项、Task、P2、原生评价及真实模型批次均未运行。

links-checked.* / links-remote.* 为原始检查记录的公开投影，只将本机工作区根目录改为 <WORKSPACE>；CLI stdout/stderr 无需修改。IDENTITIES.json 保存本机原始报告字节/hash，原件留本机。MANIFEST 对公开投影逐文件取 hash，不冒充原始 HTTP。
