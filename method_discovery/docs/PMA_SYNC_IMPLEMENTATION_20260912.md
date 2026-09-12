# PMA同步对照实现与工程验收

## 范围和授权

用户已确认保留PMA原始同步调度作为独立外部对照，Clean Monitor主体继续并发。此例外只适用于GA_PMA_ENABLED的外部基线，不允许把普通监察改回审批。当前阶段完成实现与零API测试，真实任务未启动。

## 实际实现

`GenericAgent-main/pma_baseline/` 独立保存原仓库memory_agent.py、universal_memory.py、bm25_search.py及Apache许可证/来源说明。三步分别253、446、569行移植，不把全部视为一步；后续runtime和接线分别小步实现，均低于600行。

- 保留原phase系统提示、四个bank工具、status截断、K/P存储、超过50条时分别BM25 top20和输出解析。
- 原shortuuid依赖本环境未安装；仅将不透明ID改为uuid4十六进制前8位，NOTICE明确记录字符集/分布差异，不称逐字原样复现。随机ID存在有限碰撞概率，未新增基于ID的研究机制。
- 每题新实例/空bank；初始化先做两phase。后续每次任务模型调用前同步审议上一完整公开步骤；最多保留8步，命令展示前5项加超出计数。
- GA没有单独解析的plan字段，其公开response整体进入analysis；工具调用JSON作为commands，工具结果作为observation。没有提供隐藏reasoning、隐藏评价或目标版本参考源码，不额外喂旧运行记忆。
- phase1更新后phase2重建bank输入；不接入Clean的持续对话/主动调查/强制中断/完成批准。一次性软提示说明内容是待核实观察，不是指令。

`runtime.PhaseClient`使用已有独立provider传输原语，每phase单独构造请求会话，记录请求telemetry；不将PMA的记忆对象替换成Clean history。原上层call接口只有prompt/system/tools，不能依据源码标题中的“single phase / shared conversation”注释臆造额外会话。

`agent_loop.py`增加显式条件分支：关闭PMA则不构造PMA；启用则在任务推理前同步review和一次性注入，普通工具完成后收集公开步骤。Clean并发archive/interrupt路径未改。PMA与Clean同时开启报错。

## 工程接线

- Harbor透传GA_PMA_ENABLED/CONFIG/ARTIFACT_DIR；独立日志 `/logs/agent/pma`。
- isolated_run_bundle复制PMA包，网关选用PMA模型配置，仍固定Unix推理通道。
- runner将PMA纳入禁止在线checker条件，禁止通过Clean关闭而重新启用LHTB中途verifier反馈；真实运行仍要求隔离。
- prepare_pma_baseline.py仅输出提案，使用既有Clean任务注册门禁，固定PMA模型配置名和当前任务模型配置名；不读真实模型返回、不执行任务。提案不是已通过预检的启动manifest，不自动获批运行。
- 模型失败由独立phases记录并标provider_failure；未识别输出标unrecognized_response，不计为正常no_intervention。原phase1失败后仍尝试phase2的行为保留并披露。

## 验证

1. PMA单元/循环测试7项：bank更新后phase2可见、一次性提醒、窗口、跨题reset、检索删除、provider字段映射、失败可见、实际任务循环同步顺序和关闭路径检查（部分在同一test内）。
2. 与Clean runtime共同运行17项通过，覆盖原有并发交付路径。PMA关闭路径另有AST条件检查；不宣称AST等于全部动态能力验证。
3. 隔离transport及ultralong启动回归60项通过。

合计77项通过；没有付费模型或Docker运行。早先误用unittest运行pytest文件导致导入失败/零测试，已改用项目cwd下python -m pytest实际执行；未把那两次无效执行算作通过。

新增实验结果尚无，不能说PMA有效、劣于我们或并发创新成立。请求超时/费用/真实工具调用仍需实际服务验证。当前公开输入格式与原Terminus不同，模型和任务源也不同，因此命名PMA同步GA机制适配，不称原论文成绩复现。

## 文件变化和下一步

生产新增pma_baseline包，最小修改agent_loop、Harbor透传、runner隔离配置选择/no-checker判断、隔离包复制；盘点工具同步新增包名，避免新包漏入未来清单。没有改Clean提示、记忆、调度或中断机制。原工程回退点0aef4b8保留，旧指纹和manifest不用于新源码启动。

本阶段独立Git保存。下一步只做真实启动门禁：确认任务ID、同步PMA条件、模型、500turn/10000秒等最终生效预算、预期费用/耗时和对照依据；需要最小模型工具往返/环境预检及用户单次确认。不会自动运行6题或启动新方法候选。
