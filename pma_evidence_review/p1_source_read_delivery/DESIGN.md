# 工具契约与工程边界

## 五个既有写工具

`memory_save_knowledge(content)`、`memory_save_procedural(content)`、`memory_save_gap(content)`、`memory_update_status(content)`、`memory_delete(memory_id)` 的完整 schema 保留。保存仍生成新 ID；纠正采用先保存后删除。普通写工具原有容错和非原子语义保留，不能把 schema 只列 content 说成执行器会严格拒绝所有多余字段。
仅来源关联失败增加工程保护：恢复这次保存前的普通 bank，保留 bank 对象身份、status 上限及之前已成功的操作，并停止本轮后续操作。失败新记录的诊断材料可以保留，但不能通过已删除/回滚 ID 读源。这不是语义审核、通用事务或历史版本系统。

## 只读工具

公开参数仅为 `memory_read_source(memory_id: string)`。工具先核对活动条目，再核对 task、cycle、ID、类别、当前内容及保存窗口的字节完整性。工程哈希仅用于关联检查，不作为模型置信度或逐句证据评分。
回执区分 `entry_not_found`（包括已删除）、`source_unrecorded`（旧条目无记录）、`source_missing`、`available`、`available_truncated`。错绑/损坏返回明确工程状态；没有来源不表示条目为假。读取不修改 bank 或来源窗口，普通调用日志仍记录这次读取。
默认每次维护最多处理两次读源请求，非法参数/不存在 ID 也占已处理配额；超额请求不访问档案并返回 `budget_exhausted`。第一轮若请求读源，最多续答一次；第二轮只提供原五个写工具，非法追加读源返回 `continuation_unavailable`，不产生第三次模型调用。
每个序列化读源 result JSON 至多 8,000 个 Unicode 字符；这不包括外层续答信封和完整原输入。预算是工程固定值，模型不能选择。原客户端/SDK重试保留，因此最多两次逻辑 P1 调用不等于已证明最多两次物理 HTTP 请求；当前适配器不声称完整计数底层重试。

## 确定性读取视图

任务/周期身份、来源范围、完整性、截断和省略信息在不截断的外层。优先保留此前实际呈现的读源回执，再保留最近的完整动作—回执单元；保留单元按原顺序展示，然后尝试放入 Actor 自述和完整输入。命令参数、provider/tool ID 和实际回执保持原值，不按 action.name 合并，不猜测配对。
超大单元整项省略并列出窗口序号，不从中间剪出假完整记录。以前呈现的回执若整项超限，明确缩为其元数据和可容纳的完整动作/回执单元，标注省略；不重新解析旧 ID 或自动追溯依赖。完整输入和原回执始终在生成窗口档案中。长任务/长 bank 加尾部短回执已做客户端续答检查。
`source_text` 仅在整个保存窗口可容纳时返回；否则为空并明确标注完整输入省略。工具视图不是“全部证据”，外层明确生成窗口不等于逐句支持、旧读源回执不等于新观察。

## 事件、输入和续答

完整原任务、当前可见 bank/status 和最近八轮仍保留，复用既有 project_steps 处理已知嵌套历史。实际命令和回执不按内容相似去重。有可靠接受事件 ID 才标 `new_event`、`previously_presented` 或 `repeated_in_window`；无可靠 ID 标 `identity_unknown` 并保留各次呈现。相同 ID 内容变动是工程错误；不同执行即使输出相同也分开。
保存关联的是该次模型调用的完整用户输入窗口，不是末尾事件的单一支持来源。system、tools、可见响应、逐项结果、可得 usage 与错误状态另按同一 window_id 记录。续答含原输入和一次可见调用/回执文本，不含 provider 隐藏思考或签名，也不自动给 P2 添加来源。
run-config 在客户端初始化后、首个请求前保存实际可得模型参数、未知值、源码及输入/system/工具 schema 哈希；每轮更新实际请求哈希。初始化和 build_case 失败也写 terminal，不能留下只有 identity 的悬空状态。profile、凭据、端点不写入配置或日志。

## 提示差异与参考

候选 SYSTEM 从既有 P1 文本保留保存角度、条件与简短记录规则，只增加来源角色、事件呈现标记及按需读源说明。**删除了原 visible-check GAP 一行**（missing coverage / weak assertions / expectations），因为本候选不承担测试质量判断；没有把这项删除藏在工具接线中。默认 P1 文本本体未修改。
只参考 MAGE 固定源码 `Komorebi660/MAGE@868e36bd3bdb378250f2f7457af5960193c9598c` 的原始事件与摘要覆盖关系。根目录未发现 LICENSE，本实现自主编写，没有复制 MAGE 源码；未采用树分支、环境回退、审核、搜索压缩或直接 True 检查。已阅读 ExplorationTree.py 和 AgentSTMemory.py，未把仅比较 action.name 的合并规则带入。
