# 独立 Claude 监察配置与协议适配

## 用户裁决与范围

只更换监察者为 Claude；GA 任务模型及其密钥不变。撤销误加到 GA mykey.py 的监察配置。
监察配置位于 `E:/LongContext/monitor_config/models.local.json`，不提交 Git。
独立 profile 为 claude_monitor_opus48：Opus 4.8、adaptive/high、8192 输出预算、200000 上下文配置。
独立内核不导入 mykey、llmcore、GA provider。任务宿主只传入已加载的配置。
没有修改工具选择策略、提示词、工作记忆、wake-control 机制。当前仍是方法发现与工程适配，非效果验收。

## 改动

- configuration.py：独立 JSON profile 加载，缺失显式报错；不自动回退到任务密钥。
- agentmain.py：Clean 入口使用独立 loader，默认 claude_monitor_opus48；不是修改任务 provider。
- provider.py：已有 Anthropic Messages、工具 schema 转换、SSE thinking/signature/tool_use、tool_result/history 续接。无需复制 GA provider。
  对照 llmcore.py 的消息结束检查，补齐 message_stop 完整性检查；不完整流重试而不执行残缺调用。
  保留 redacted_thinking 原始块以供历史续接；固定内部路由头只用于隔离网关。
- isolated_run_bundle.py / isolated_transport.py / run_ultralong_m12_proofs.py：任务配置仍从 GA 加载；Clean 监察配置从独立文件加载。
  同一模型可分别路由两方密钥；任务 mykey.json 不再含独立监察配置，监察脱敏配置放在独立包中。
  密钥只在外部 gateway；模型侧仍无网络，不新增外部检索权限。路由分离不是同容器两 agent 间的安全边界。
- prepare_claude_monitor_r1.py：生成独立新 run-id，保留 wake-control 条件，换监察模型。
- probe_claude_monitor_isolated.py：直接使用独立 core/配置，通过生产隔离链路进行工具往返。

历史 GPT manifest 若重跑，必须先在独立配置文件准备对应 profile；不再静默从 GA 配置取密钥。
本次没有提交 mykey.py、models.local.json、探针 source/gateway 或原有 .gitignore 改动。

## 验证

首次 pytest 从根目录运行漏设 PYTHONPATH，收集失败；设置正确环境后运行成功，不是实现回归。
扩大回归：全部 test_monitor*.py + test_isolated_transport.py + test_run_ultralong_m12_proofs.py，344 passed。
新增测试覆盖独立加载、Claude signed/redacted history 与工具结果续接、截断流、同模型不同凭据、隔离副本不含真实密钥。
git diff --check 通过。每步新增与删除均少于600行。

真实接口探针（不是题目运行）：
- probe_r1：首调用返回约3.841秒，严格参数断言失败；原记录未保留详细工具参数。
- probe_r2：首调用3.976秒，返回正确 read_sample，但空 schema 下带 `_noargs: unused`，严格校验失败。
- probe_r3：明确 label 参数，不放宽校验；首调用3.551秒，两次请求合计5.983秒，工具名、参数与返回内容均通过。
- 探针产物：method_discovery/artifacts/claude_monitor_20260913/probe_r*/probe_result.jsonl。
  `_noargs` 现象保留为服务适配观察，不能据此宣称所有无参数工具已验证；当前 allow_complete 本就无参数消费。
- 探针结束无运行容器。未启动完整真实任务。

## 启动门禁

准备的 manifest：method_discovery/artifacts/claude_monitor_20260913/fyne_r1_manifest.json。
任务 roadmapbench:fyn-2.2.0-roadmap；任务模型原 Opus4.8；监察模型独立 Opus4.8/high；500turn/10000秒。
比较目的为服务/协议适配与真实监察行为，不是因果证明 Claude 优于 GPT。旧 GPT wake-control 未启动，旧 R2 仅诊断参照。
没有整题可靠美元估计；需按调用、token、延迟、wall time 实测。完整任务仍需用户单独确认。
