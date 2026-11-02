# 极小契约与复用

- 唯一模型自由文本是GAP的pending；schema保持简单optional字段，执行层按category要求/禁止。长度/空白/换行是工程校验，不用标点启发式判断句子或意义。合法来源仍由冻结映射解析，不能引用未来/外任务/不存在来源。
- bank content仍是host index：原材料ID、category、outcome=unknown；GAP额外含pending与明确index_kind。活动组展示独立generated_unresolved_index；read页首字段generated_unresolved_index_not_fact，后续为原材料。生成索引不当作原始回执，也不计为支持证据。知识/经历不开放新正文。
- 复用DMSMaterialStore、原子单条bank/source提交、别名解析、read分页/cursor、中央事件表及runner。只添加store类型、keep校验/元数据、组展示、read字段四个小hook；旧类默认返回旧行为。新增runtime文件纳入64项身份清单。
- 新候选read字段按来源宿主顺序、同来源字段名确定性排列，避免内存dict插入序与持久JSON排序不同导致重开页序变化；字符串、空白、Unicode、原始事件/参数/回执值不变。索引字段进入既有分页预算及cursor快照，不在8000字符页外另塞说明。
- 保留原文来源和事件，不自动生成完成结论。save新条目后delete旧条目仍是逐操作，不是整批事务；工程/参数/工具错误阻止后续操作，已提交条目不回滚。短索引内容是否合适未由离线假客户端验证。

## 提示三原则

完整性：保留原角色、来源非证明、继承非已读、部分非完整、三工具与4读/3轮边界；补GAP与经历/计划互补、同一未决项及旧解释受新观察限制。
简洁性：只替换开头维护职责及原GAP定义，未再堆新报告/列表；模型只增加pending一句，内部存储/校验细节留在工程。
自然性：使用普通未决条件/问题表达，不要求模型学新枚举、来源评分或生命周期步骤。实际system长度/hash见IDENTITIES，prompt完整差异见PROMPT.diff。

## 尚未接入

等待A线程通过测试的固定helper/API：自动冻结生成时已展示记忆及其来源目录、只读history handle。本节点仅保留既有活动来源/typed legacy引用；未选M而随后被删的旧材料不因此保证可回查。不会把输入目录当支持证据或声称覆盖完整；也未另造历史树。最终组合验收须单独补这一接缝。
