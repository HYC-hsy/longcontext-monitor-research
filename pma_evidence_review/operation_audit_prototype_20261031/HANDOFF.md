# 给开发线程：完整操作依据与缺口反馈原型

基线：HYC-hsy/longcontext-monitor-research 固定提交
48babf4302563bbe6e8f0d47e8c617d041a392b1。
这是隔离离线原型，未接入生产；旧两个选择原型不变。最终文件哈希与检查见 MANIFEST.json、VERIFICATION.md。

## 经源码核实的旧行为

- claim_split_semantic.VERIFY_SYSTEM 已要求 Judge every claim and the complete A；
  末段已要求所有子项和 overall 支持。不能说旧实现没有整体审核。
- claim_split_simple.verification_request 已送入 original_operation、claims、
  normative_requirements_context 和一次共享 B。
- claim_split_simple.parse_batch 已校验 overall/results，并把 overall 和所有
  子项合取；review_stage 已把完整操作、overall、子项和证据放入 repair_feedback。
  这些正确部分应保留，不重新发明第二次审核。
- semantic.deletion_candidate 已通过 memory._content(key) 冻结 old_content，
  要求 kind==gap，获取 active revision，并放入 original_operation.existing_gap。
- live_citations.build_live 的普通写入记录只有新 content 和前版本 ID，并未给
  审核视图提供旧正文。本轮有旧正文则带入，无则明确 unavailable；不新增所有更新
  必须保留全部旧事实的策略，也不阻塞现有普通写入。
- normative_requirements_context 常为空，不代表完整任务已经送审。原型不自动加入
  全任务或八步轨迹。缺失完成范围时应 insufficient，而非虚构更高的完成标准。

## 实质改造与边界

仍是 split 后一次批审。将原有 overall 作为固定 O 必审项，子项 C1...沿用既有
split 结果；不是再让 splitter 猜一次遗漏。完整操作、旧条目显示一次，O 引用它。
O 无论何种判定都要简短解释“本次变更为何成立/不成立”，必须面向原操作的决定性
条件；不允许用“子项都支持”代替范围解释。insufficient 的理由说明支持范围、
缺少条件、可行证据例子；contradicted 说明实际冲突，不机械索要更多证明消解反证。
supported 子项可只返回标签和判定，不复述原文。计划仍按计划判断，不要求已执行。

闭合 gap 要面对其实际条件；重复删除要有保留等价项的证据；合法撤销/过时按对应
理由判断，不能统一强迫做 fresh-process 测试。生产只允许 gap 删除，其它删除不开放。

工程保证 O 和每个 C 都存在且唯一、协议有效、关联正确、发布合取，以及整体失败
能进入原返工。工程不能判断理由是否真正面对条件，不能保证 LLM 不再漏审。
旧 overall 合取本来就能拦住正确的 insufficient；本轮改变的是判定提示的具体聚焦、
低冗余视图与反馈内容要求，并非填补一个不存在的旧合取漏洞。

## 轻量协议与映射

输入：target_context_not_evidence（完整 action/arguments、before_entry、可用标志、
必要 task excerpt）；required_judgments（O 和已有 C）；一次 shared_submitted_evidence_B。
from_closed_material 适配已检查的 v3/v4 形状。host_mapping 保留完整原材料、native
ID/revision/hash/target revision 和来源记录；不让模型复述。quote 字符串原样保留，
一次 quote 的多个来源仍为 alternative_origins，不拆成独立佐证；role、field_path、
event_order 仍显示。为避免丢失 code/stdout/参数语义，本轮没有粗暴缩短 field_path。
角色、事件范围和命令解释不能为省 token 被删。真实生产适配仍须沿用既有引文绑定。

返回紧凑 JSON 行数组：
[["O","insufficient","当前会话可运行；缺少独立进程范围；例如无临时 export 的调用回执。"],
 ["C1","supported"], ["C2","supported"]]
O 第三格必填；insufficient/contradicted 的 C 第三格必填；supported C 可省。
没有发布布尔值、版本、hash、正文回声、复杂嵌套理由字段。仍用 JSON，以复用客户端
和 JSON 解码，不为“标签”强换 XML。宿主唯一映射并聚合，contradicted 优先于
insufficient，均不得发布；parse_error 的 verdict=None，独立于语义拒绝。

允许 strip 外层空白和一个完整外层 Markdown 围栏（无标签/json/text），起止行独占。
拒绝围栏不全、多个/嵌套块、其他标签、混杂外文/解释正文、重复/未知/缺失标签、
错类型和 NaN。保存 raw/normalized/error。没有新增次数或容量上限，也没有自动重试。

repair_feedback 仅返回 control-only 指导和宿主锚定完整操作/旧条目；不返回 replacement，
不调用 memory API，不自动把建议写成记忆。仍由原 repair 流程提出修订并重新审核。
建议是例子，不是唯一必须测试；任务要求也不能被审核建议升级。

## 实际减负与证据限制

旧源码要求每个 results 子项都输出 verdict/reason；新协议支持子项只需两个短格。
旧原操作视图还含 op_index、memory_id、revision_id、content_sha256；删除还含
existing_gap/target_revision_id。新适配把 opaque 身份留宿主，保留语义 action/content。
已用同形模拟材料验证移除身份且 quote/替代来源语义不变；不是对真实 call 76 的
输入 token/cost 实测，不能声称实际省了某百分比或提示效果已提升。真实 smoke 应保存
新旧实际请求字符/token/usage，已有旧请求/输出直接复用，不新增旧组调用。

## 接入位置与验证

1. 在 claim_split_semantic.review_stage -> v3.review_stage 的批审构造处，接入
   低冗余投影和固定完整操作判定；split 请求、引文 eligibility/locator 不变。
2. 现 parse_batch 的 overall+子项合取、review_stage 的 repair_feedback 和
   gate_control.repair 的 feedback-not-evidence 边界继续保持；协议适配一次性统一
   normalizer/parser，审计回放/证书验证也必须使用同一新解析路径。
3. 删除继续 semantic.deletion_candidate 的 gap-only、before、活动版本及提交控制；
   原型未实现生产事务、版本核对和发布，不能把 publishable 当作可绕过 gate 的权限。
4. 真实客户端 smoke 推荐用冻结 PATH 原请求，只运行新提示，通过实际 client、
   parser、聚合、返工参数装配，保存 raw 和错误。旧输出已存在，不重跑旧组。
   smoke 与效果评估分开。本原型没有执行真实 smoke。
5. 后续获准后仅跑新方法 Task，旧同数据集结果直接复用，绝不自动重跑旧组。
   本轮不启动任何真实模型/Task，不改 phase2、状态、gap schema，不新增检索/证据图。

## 最终原型检查与真实历史材料

最终源码共 15 项定向假响应契约测试通过，记录见 final-test-output.txt；不是模型语义通过。
fixtures 保存已公开脱敏归档中 call_index=76 的请求/旧响应，以及候选请求投影。
原始包 SHA-256、提取方式、字符对比和边界见 VERIFICATION.md。历史材料已补齐，
不需要重跑旧组，也未执行新模型调用。两个子项支持/整体不足场景的工程合取原来就有，
测试通过仅证明新协议映射没有破坏它。

## 提示工作流增量：完整性、简洁性、自然性

本次仅将审核提示重组为四步：读 B 与来源范围 → 理解完整操作实际承诺/关闭目标 →
比较范围和条件并检查子项 → 给 O 与必要缺口反馈。不要求输出思维链、检查清单或
逐步执行痕迹。`system_for(batch)` 由宿主从已知 action 选择 save/update/delete
短分支；仍只有现有 gap 删除，没有新的 LLM 分类调用或 Skill/Plugin 加载器。
实际调用需用 system_for(batch) 的结果，SYSTEM 是带 action_guidance 插槽的模板，
不能把未填模板直接发送。三态保留 supported / insufficient / contradicted，
没有改为晦涩单字母编码。

- 完整性：证据边界、来源语义、要求/计划/事实、完整 O 不可被子项替代、三态与
  必要反馈仍保留，删除条件按真实理由判断。
- 简洁性：通用规则集中在四步，动作特有内容只在宿主选中的分支出现；宿主负责
  标签关联、版本与发布合取，支持子项不重复理由。
- 自然性：提示使用专业审核的连贯动作与条件说明，不堆关键词或连续禁令；结果
  是简短审计依据，不要求填满机械流程字段。不上传用户原图。

## 操作类型、目标绑定与生产容器映射

from_closed_material 的 operation_kind 来自宿主真实操作记录，而非 before 是否可用。
save_gap/save_knowledge/save_procedural 既可能新建也可能修订；宿主用原工具参数和候选
revision.previous_revision_id 决定 save/update，并显式传入。缺失该信息时原型拒绝，
不能默认为新建。update_status 固定 update，delete_gap 固定 delete，冲突值拒绝。
这只是宿主语义标签，不改变原有权限或动作策略。普通 update 无旧正文仍可判断新内容，
不能凭空补旧内容。existing_gap 存在时为唯一冻结删除目标；传入 before 必须正文一致。

production_result_example 只演示旧容器形状映射，不是整个生产适配器：
- parse_error 必须映射为既有 parse_failure，verdict 保持 None，error 进入 reason/explanation。
  不能把新状态原样传给 _execute_reviewed，避免误触发停止后续操作。
- 重建 overall、claim_reviews、model_verdict、explanation、repair_feedback 和 batch。
- O supported 而某 C 失败时，explanation 指向实际失败项，不只复制 O 的支持理由。
- batch 的真实请求、响应、审核身份和已有捕获字段须由生产调用链恢复并保留。
  示例中没有伪造实际请求或远端调用凭据，不能用它跳过 replay/certificate 校验。

保持同一现有批审调用和原有返工预算。不要为解释字段再增加审核调用或新返工循环。
