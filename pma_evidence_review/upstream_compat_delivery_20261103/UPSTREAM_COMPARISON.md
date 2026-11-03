> 当前为已授权发布、尚未完成最终验收的中间审查版。独立分支pma/upstream-compat-review-intermediate；源码固定提交见SOURCE_IDENTITY.json。

# PMA 原版接口对照与最小修补

对照原版 `89e5c0d6aadfe531a1aee42fd290d48be89973dd`；实际执行基线为 `efab10decdafa578c2ba5b9d58600433b4ba6bdf`。本地导入基线完整 tree=`47b3ef72ed164ad7e5a30578f2f731e527cf3bdf`，与 GitHub 固定提交一致。失败材料来自 `b61a725f563cfcb1bd2c94c89a5ac79eb34399e9` 的公开可见投影包，原失败归档没有改动。本轮实现和离线记录作为中间版发布，仍待独立最终验收。

| 接口 | PMA 原版实际代码 | efab 与原版的差异 | 本轮结果与保留原因 |
|---|---|---|---|
| P1 SYSTEM | `PHASE1_SYSTEM`，1382 字符，FACTS/EXPERIENCES、精简、任务要求、失败和环境发现指导 | 来自 bank_display 重写后再叠加多层策略，5577 字符；不是原版加小扩展 | 恢复原版全文作为逐字前缀，合计2951字符。只增加 GAP、固定要求属性、来源/历史导航及绑定安全说明。删掉自写的额外整理策略；原版“终端刚看过的明显内容不用存”等指导没有被替换 |
| P2 SYSTEM | `PHASE2_SYSTEM`，2114字符，综合针对性提醒或静默 | 原版全文加较长导航说明 | 原版全文逐字保留，合计2824字符。附加部分仅解释概览可错、可选主题/平铺/证据、GAP计数非完成证明、范围与有限读预算；不要求逐条审核 |
| 工具原有含义 | save knowledge/procedural/status/delete，创建新ID，不增加UPDATE | 多了 GAP、requirements、source_ids、读源 | 保留原版四工具的内容含义和原执行器；GAP为用户明确要求第三类，requirements/source_ids是新组织与来源能力必要参数，没有新UPDATE、审核或判断模型 |
| 工具字段校验 | 原版schema不禁止额外字段，执行器通常用args.get忽略它们 | 六工具严格字段，要求属性枚举及来源/ID校验 | 保留并明确为必要例外：防止错拼要求/来源被静默丢掉、双ID或跨快照错误操作。错误现在留在记忆组件，普通参数错误不再使整题异常；不是语义审稿 |
| 工具执行批次 | 逐条执行，单条异常记录后通常继续 | 错误后不执行后续调用，前面提交的仍存在 | 保留既有批内 fail-stop，尤其防止保存失败后删除旧记录；没有事务回滚假象。已提交操作和未执行操作分别记录，P1的普通错误后可用一致库继续P2 |
| 保存与来源 | 原版仅内存记录/单独保存文件，无来源合同 | bank、正文、要求、refs同一原子bundle提交 | 保留。新属性和来源必须与正文一起落盘，不能伪造成功绑定；删活跃项不删冻结H历史。未知持久化结果不得当普通模型格式问题 |
| 当前ID/历史ID | 原版真实ID；无冻结来源历史工具 | 本轮显示M、内部ID与H目录 | 保留统一entry参数和本轮M标签，工程解析真实ID；H1/P2H是只读冻结历史，不是当前可删M。原始调用和实际目标留日志，兼容旧host memory_id入口；同名歧义拒绝 |
| 固定要求 | 原版无此属性 | 首次额外调用P1抽取固定自然语言要求 | 保留，用户明确要求；无R1/R2索引、无动态主题、无旧库迁移、多归属或[]可见。每个新任务空库；原任务全文始终保留。初始化不吞维护 |
| 初始化失败 | 原版无初始化 | 坏初始化保持pending，使后续Task触发也被挡住 | 独立P1 runner原有显式恢复保持。Task适配只对确定的模型输出/调用失败、未维护、库未变且catalog仍None时显式关闭失败尝试；记录失败，当前不调用P2，后续触发重新初始化。无伪造[]或自动重放已执行写入 |
| 初始化调用计数 | 原版无初始化 | 参数解析在completed记账前，返回坏JSON会漏记completed | 先记录实际返回，再解析。保留原始可见输出/参数；attempted与completed按本次实际观察分别记录，不以请求格式正确代替模型已返回 |
| BM25筛选 | `MemoryEnabledTerminus2._get_memory_agent_context`：原任务＋最近8步；每类top20，阈值/启用开关 | P1可能只encode(events)，P2可能只最近轨迹 | Task适配直接复用原版context；独立pipeline无observation时也复用该函数。P1默认query包含原任务＋8步。调用方显式传入observation仍按原API视为已组合context；直接API调用方须遵守此合同 |
| 模型近期输入 | 原版任务＋最近步文本；query的commands最多5条，其他数量标注，observation原样 | `project_steps`移除了重复history并只留最新checkpoint/earlier_context | 当前要求候选P1/生成式P2移除该删减投影，保留接受事件内完整history/checkpoint/earlier_context及回执。仍白名单取实际可见字段，丢研究标签/签名/隐藏块；原始来源不从旧包装重建成新事件 |
| 输入布局 | 原版文本bank+status+trajectory | 别名行、固定要求归属、来源范围及JSON事件 | 保留必要新属性/稳定编号；正文与原任务不改写。要求全文按反向归属只显示一次，无额外模型可见要求编号；分组明确显示子集，完整库可按需分页 |
| 可见事件身份 | 原版近期文本无独立证据身份 | 接受event_id去重，旧事件重复展示不算新执行 | 保留新来源合同所需身份/接受次序。历史包装仅作为当时可见文本，不解析为新的accepted事件；相同输出但不同事件不合并 |
| P2最终文本提取 | `_parse_phase2_response`用re.search找到提醒标签，前后普通文字/Markdown不妨碍；`<no_intervention`可出现在说明中 | 要求整个响应严格标签，efab仅加“静默后换行纯文本”特例 | 删除两套严格整响应/句式归一化，直接调用原版解析器。前置/后置说明、普通标记和代码围栏都按原版提取；真实三例逐字回放结果一致 |
| 缺失/空/未闭合标签 | 原版警告并默认不干预，空提醒也可落到默认 | 严格拒绝后变成Task异常 | 恢复原版默认，另记parse_status和format_warning。没有把警告算成证据有效或任务完成；没有额外修复模型调用 |
| 冲突决策 | 原版可能优先取第一个提醒，即使另有静默/多提醒 | 统一拒绝但误伤普通说明 | 必要例外：多个完整提醒，或提醒之外还有静默，明确记录model_output错误、不注入；不执行工具；Task继续。提醒正文内的标签样例作为正文，不做关键词清洗 |
| P2工具与文本混合 | 原版P2无工具 | 新工具扫描可能先执行正文里XML样例；后加严格判断又误拒普通文本 | 先识别可提取的决定；正文内工具样例不执行。native工具＋最终决定，或提醒外可解析text-tool＋决定，明确冲突且零执行。纯工具轮复用已有原版XML回退/结构化提取 |
| 原始错误响应 | 原版返回raw_response_phase1/2 | P2解析前抛错导致turns=[]；原始出错文字丢失 | 解析前先留可见文字/native参数，错误另标parse_error；工具原参数和实际执行receipt分开。初始化、P1和P2均覆盖，诊断字段不送续轮模型 |
| P1普通错误 | 原版process记录错误，仍用更新后的库运行P2 | 任意非completed都跳过P2并由Task适配抛错 | 已知模型调用/参数错误且已提交库一致时继续P2，保留p1_warning及操作记录。绑定/存储损坏、未知执行或未解决周期仍停止，不用“兼容原版”吞工程错误 |
| P2普通错误 | 原版process或外层_trigger记录异常，通常不让Actor整题退出 | 所有非intervention/no_intervention都被升为Task异常 | 普通模型输出冲突、只读参数错误、模型调用失败明确记录为记忆错误并跳过提醒；pipeline和Task适配器均在实际继续前重新校验P1 bundle与周期状态，只有健康时下一串行事件可继续，不改为假no_intervention。源绑定错误、版本失配、持久化/audit失败仍fail-stop |
| 触发与成本 | 同一现有client，trigger interval=1，首步触发，8步window；普通P1+P2两调用 | 新初始化、可选读轮、独立pipeline | 调度/模型/既有provider重试不改。无工具的新任务3逻辑调用（初始化+P1+P2），之后2；最大新任务7、之后6。初始化失败后的下一触发可能再花1次初始化；无本轮自动重试或额外审核。物理重试次数仍未知 |
| 记忆轨迹/计数 | 原版_trigger累加trigger/operations、调用_record_memory_step，save_memory保存trajectory | 新Task路径绕过它们，轨迹空/operations为0 | 复用原版_record_memory_step、MemoryAgentResult/MemoryOperation和save_memory；记录P1/P2实际原文、prompt、操作、决定，补GAP数量与明确错误字段。trigger记尝试；错误不伪记普通noop；P1警告即使P2正常也留记录 |
| 注入与串行 | 原版_pending_injection由_get_memory_system_prompt单次取出 | GA事件桥提供提醒到下一Actor请求；另有版本检查 | 保留原版单次包装和消费；沿既有GA桥追加，不新增Actor/Task决策器。冻结版本失效不投递；串行模型格式错不再自动终止任务。离线只验证桥的拼接/返回，不声称真实发送 |
| 冻结范围与只读来源 | 原版无此接口 | 全量快照、分页授权/游标、最终投递版本核对 | 保留必要安全例外：浏览、查源、最后提醒同一版本；分页未全不能授权隐藏条目；跨任务/会话/视图拒绝。P2 grant仅会话RAM；P1历史目录首次发handle会持久化grant，不能称全程零写入 |
| 老候选/default | 原版及source-read/linked候选各自入口 | Task/CLI在fd00新增显式opt-in，不再全文件字节相同 | 原版系统/工具/两调用默认路径单独端到端检查；旧案例和core文件继续字节检查。只对已增opt-in的episode/CLI取消过时整文件冻结断言，改为实际默认路径验证，没有删掉旧行为测试 |

直接复用的代码：原版两个SYSTEM全文、四个基本工具与MemoryAgent操作、原版P2文本解析器、原版task+window格式函数、BM25/阈值、MemoryAgentResult/MemoryOperation、_record_memory_step/save_memory、单次提醒包装。现有SourceLinks、RequirementHistory、snapshot pager和GA桥继续复用；没有复制新第三方框架、图、embedding或审核器。PMA既有Apache-2.0许可证不变。

仍然不是“除新增功能外逐字等同原版”的所有文件：表中的属性存储、来源快照、接口校验、混合工具/决策冲突、错误分类和GA实验桥确有必要差异。它们支持用户明确保留的新能力或防止真实数据错配；不应用于宣称语义可靠性。原版也不会程序证明提醒正确。

证据：207项严格离线检查，零失败/错误/跳过；其中三份归档可见输出在独立P2和Task适配链各回放一次。真实提醒只提取标签内正文；两份静默保留完整原始返回。没有调用真实模型、启动真实Task、原生评价或旧组。长输入/目录仍受四读、两续轮限制，末轮无读；本轮不证明效果提升，也不修此前暂缓的模型恢复配置或历史存储体积问题。
