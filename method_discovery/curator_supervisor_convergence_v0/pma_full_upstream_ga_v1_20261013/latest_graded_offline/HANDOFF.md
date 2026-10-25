# 开发线程接收指令：最新记忆版本与分级引用定位

## 目标和授权边界

接收现成补丁，不重新设计或重写方法。本轮只做接收、必要的本地适配、离线复验及最终源码绑定的全假验收；不得调用真实模型、启动真实 Task、创建真实授权或执行官方评分。

我们只解决工程问题：合法内容更新不因引用未绑定而停留在旧版本；引用结果作为新版本属性；消除活跃待定提案及自动清理的双重职责；增加可区分等级的规范化/模糊出处定位。不是修复 Task 判断能力，也不是加审核、复审、完成门或更多工具。

## 接收

- 仓库 HYC-hsy/longcontext-monitor-research。
- 远端分支 research/pma-gap-latest-graded-20261025。
- 在主线程回报的最终 exact SHA 接收，不根据可移动分支猜版本。检查 git status 和 remote URL，保留无关改动、pycache 和运行目录。
- 先 fetch。若当前开发 HEAD 是补丁祖先，优先 fast-forward。已发生其他提交则只合入本补丁内容，不能 reset --hard、force-push 或覆盖历史归档。所有真实运行的旧代码、reward 和证据保留。
- 上传的代码按 ≤600 行变更的阶段提交，现成实现位于 latest_evidence_gap_store.py、latest_evidence_gap_agent.py、graded_evidence_alignment.py、vendor/langextract_3a68580/fuzzy.py。
- 先阅读本目录 DESIGN.md、ACCEPTANCE.md、replay_README.md 和 ../vendor/langextract_3a68580/GRADED_REUSE.md。

## 不要改错的合同

1. public method 仍是 pma-gap-evidence，research_candidate 仍是 pma_gap_evidence_v1。episode.py 选用 Latest 类，运行记录 policy=latest_revision_with_graded_alignment_v1。普通 PMA、pma-gap、旧严格/旧 aligned 类与 vendor 不变。
2. 同 ID 的合法保存成为最新内容；绑定失败、引用缺失或 evidence 格式错误只记录各自 binding 结果，不造 proposal ID。旧内容/引用留在历史。没有模型可操作的待定提案。
3. 新版本不自动继承旧版引用。来源是派生记忆时仍保留 parent revision，不冒充新观察。多候选不能变成多份独立证据，也不能因一个派生候选未绑定就抹掉干净原始候选。
4. 保存不顺带删除另一条记忆；delete 只显式撤下指定条目。仍逐操作原子提交，不猜测跨操作依赖，不恢复整批回滚。修订用原 ID 保存，不用 delete+save。
5. 原文精确优先，其次限定格式规范化，再上游 LCS 模糊候选。规范化和模糊都保留真实原文片段、原坐标及原文哈希；不能用模型 quote 哈希替代实际片段哈希。
6. fuzzy_candidate 不等于 exact、unique 或语义正确。有限 DP 工作量触顶要记录未搜索，不把它变成 Task 异常。不得跨隐藏片段、搜模型不可见内容或任意反复反转义。
7. 内容错误、未知 ID、错误类别、调用结构错误及内部账本/哈希/来源损坏仍拒绝。只对明确的 evidence 输入格式错误走绑定错误结果，不能吞掉任意异常。
8. 两阶段、五工具、Phase2 提示/解析/调度不增不减；程序只改变记忆正文及来源属性的投影。不增加模型调用或在线语义判官。
9. 新运行从新空 bank 初始化。旧有 pending 的历史库不能静默迁移或自动挑一版采纳；旧归档用旧 loader。不要为接收补丁批量重写历史库。

## 本地复验

用本机已工作的 Python 和现有 PMA 环境；此前 Python 3.13.14 可继续用，不要换到云端的 3.12。检查 evidence_requirements.txt 对应依赖实际安装且从正确解释器加载。新增 LCS helper 没有新增模型服务或图数据库依赖。

必须在新子进程启动前将仓库根目录、D、D/tests、D/vendor/pma_89e5c0d/src、D/vendor/pma_89e5c0d/external/harbor/src、experiment_runner 放到 PYTHONPATH。D 是本方法目录。打印实际 Python 版本及 PMA/Harbor 导入路径，避免误用环境中另一份 Harbor。

最少复验：
- D/tests/test_gap*.py 与 experiment_runner；云端最终为 324 passed、240 subtests，不把 subtests 与主测试相加。
- GA 四项文件：test_pma_upstream_ga_bridge.py、test_pma_capture_boundary.py、test_pma_upstream_parity.py、test_task_complete_response.py；云端 42 passed、38 subtests。
- Windows 符号链接权限跳过可如实记录，不改源码绕过。
- 检查每个运行/序列化文件的 LF/哈希规则，补丁已包含新文件的限定属性，不要全仓改换行。
- 历史 C8 两条实际引文是必测开发反例，应得到规范化候选且原文摘录仍保留原始续行符。hidden-gap 拼接仍不绑定。不能拿微型样例替代真实反例。

可用 pytest；若本地只采用 unittest discover，也要报告自己的统计口径，不强行对齐云端 subtest 数字。

## 宿主与统一入口

完成上述复验后，只做一次最终源码的既有 Harbor A/B 全假认证和统一入口单个 SQLite 全假 slot。用已有 plan→prepare→run 路径，不新建启动器，不重做整个数据集框架。

核对 B 的实际类型、policy、五工具、maintenance→selection、gap 进入实际 Phase2、提醒进入后续假 Task 请求、下一次 silent 不再新注入。源身份覆盖 latest agent/store、graded aligner 和固定 fuzzy helper。旧证书不得冒称新源码认证。

核心反例由定向测试覆盖：同 ID 的 bound→unbound/error 最新版本、随后 bound、历史不串用、清理不产生独立 proposal、规范化/模糊原文与 quote 不同、内部损坏拒绝、部分成功。若全假链没有触发其中某个分支，不得声称该分支已在 Harbor 中验证。

小型路径/导入/换行/源码哈希适配可自行核对并限定修复，重新验收实际最终源码；不得改变方法语义、放宽完整性校验、换模型/工具/调度或增加真实调用。需要这类变化才回主线程决策。

## 交付与停止

提交本地适配和验收材料，非强制推送，重新 fetch 回读 exact SHA。报告执行源码 SHA、归档 SHA、真实调用全为0、测试通过/失败/跳过、全假证据路径、授权及容器/卷清理。无需上传大私有日志；提交可核对的脱敏验收索引，不将本地文件声称为远端可读。

公开历史材料的限制必须保留：4份 SQLite 脱敏 blob 与原始 hash 不同，另有未保留来源，不能据其做完整相同目录的49条召回率复现。云端仅验证了可恢复来源与明确 C8/C5/C6 反例；不要修原 hash 让重放通过。完成接收和全假验收后停止，真实验证另行授权。
