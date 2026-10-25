# 开发接收：程序定位与未绑定记忆

## 本轮只接收实现，不启动真实任务

在现有开发分支吸收本补丁，保留本地其他工作和旧运行。无需新建运行框架、注册新方法名或改任务包。统一入口仍选择 `pma-gap-evidence`，内部候选仍为 `pma_gap_evidence_v1`；本版周期记录另有 `alignment_policy=literal_alignment_with_explicit_unbound_v1`，比较实验必须同时记录源码提交及此策略，不可与旧严格绑定版本混称。

读取本目录 DESIGN.md、ACCEPTANCE.md，以及 ../vendor/langextract_3a68580/REUSE.md。所有必需资料在仓库，无需另外下载文档。

## 已实现的改动，不要自行重写

1. 新 `gap_evidence_alignment.py` 实际调用钉扎 LangExtract 的 tokenizer/位置映射和候选枚举函数；源码、Apache 许可证和原始文件哈希在 vendor/langextract_3a68580/。不是引入完整 LangExtract 服务，也没有新的模型请求。
2. 现有五工具保留。写入只有 content 必需；evidence 可省略或为含 quote 的数组，source 仅可选提示。错误提示不再阻止程序在本轮真正展示的来源中定位。目标 memory_id 仍是精确操作身份。
3. 唯一匹配、多位置匹配、未绑定分开记录。多位置是候选出处，不是多份独立证明。未绑定结论可保留到原类别并明确显示给两个阶段。
4. 未绑定修订不得覆盖已有有据条目；保留一个可修订/删除的待确认提案。状态同样保护。成功的有据修订可替换原条目并关闭提案。不存在的目标、参数损坏、来源完整性错误仍拒绝。
5. 第二阶段仍是原选择逻辑和提醒/静默协议，没有审核、修复或复审阶段。输入增加程序生成的绑定标签、出处摘录及待确认提案。P1 不把旧摘录文本当成当前可搜索原始来源。
6. 单项原子提交继续复用。一个操作失败不回滚其他成功操作。新增 retained_unbound 计数不能当成引用成功数；success 仅表示存储操作成功，不表示结论正确。
7. 原始严格绑定类、普通 PMA 和普通 pma-gap 保留。生产 construct 的 evidence 分支已切换到 aligned 子类；不要只测试旧类而误称已接入。

## 本机环境与依赖

使用你已有的可用 Python（此前为 3.13.14），不要求改成云端 3.12。启动前设置原有钉扎 PMA/vendor Harbor 的 PYTHONPATH，避免导入环境内另一份 Harbor。保留原 rpds-py，新增的 regex==2026.9.29 已写入 evidence_requirements.txt；用实际执行该候选的同一个解释器检查/安装依赖，不要只安装到另一个 shell 或无关 venv。

必要路径：候选目录 D、D/tests、D/vendor/pma_89e5c0d/src、D/vendor/pma_89e5c0d/external/harbor/src、仓库根目录、仓库/experiment_runner、仓库/GenericAgent-main。测试可使用既有 LITELLM_LOCAL_MODEL_COST_MAP=True，避免离线收集时联网查询价目表；它不是关闭真实运行的计费记录。

## 有限复验

- 执行 `python -m pytest <D>/tests/test_gap*.py <仓库>/experiment_runner -q`，确保包含 aligned_host、alignment_integration、alignment_replay 和 langextract_alignment_reuse。
- 执行现有四个 GA 文件：test_pma_upstream_ga_bridge.py、test_pma_capture_boundary.py、test_pma_upstream_parity.py、test_task_complete_response.py。
- 用相同解释器运行本目录 replay_historical.py。它读取旧公开可见来源，未改历史模型引文和提示 ID；不是新的模型实验。
- 验证最终记忆保存/读取后未绑定标签、待确认目标、全部候选引用仍在；未知目标仍被拒绝，成功兄弟操作保留。
- 实际发送的 P1 提示不得同时要求 delete-and-save 和原位修订；不得仍要求来源 ID 必填或引文全局唯一。P2 必须读到标记后的未绑定结论，不能仅在日志里保存标签。
- 沿用已有最终源码绑定的有限全假 Harbor/统一入口验收，不增加其他框架或模型探针。旧证书不能冒充新提示/新存储已验收。保证 actual candidate class、policy、同一 bank 对象、maintenance -> selection 和提醒/静默正常。

Windows 已知符号链接权限跳过如实记录，不为测试改系统权限或降低断言。环境路径、缺依赖、测试夹具旧预期等小问题可以就地修复；不要修改本版的准入/未绑定/多出处语义去迁就假响应。

## 输出和停止

提交只限相关源码、测试、接收记录及必要脱敏证据，保护原运行和不相关 __pycache__。报告 exact SHA、实际 Python/依赖路径、测试通过/跳过/失败分别计数，以及最终假运行是否使用新策略。推送后回读核对。完成后停止，不新建真实授权、不续跑旧任务、不调用真实模型或官方评价；真实效果需另行决定。
