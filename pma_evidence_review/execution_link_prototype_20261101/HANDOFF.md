# 开发交接：已选证据的工具调用关系投影

生产基线 a0f35e1ab4586472ebc0768b87e3cc228f36aa14；旧原型 c08e84eda44a731fc4568533ac313dfa643cace6。
本目录独立，未改生产工作树，未调用模型/Task/安装依赖/推送。交付文件以本目录 MANIFEST.json 为准。

## 已核实源码与最小接入

D=method_discovery/curator_supervisor_convergence_v0/pma_full_upstream_ga_v1_20261013。
- D/gap_evidence.SourceRecord 已含 namespace/event_id/order/record_digest/tool_call_id/
  parent_wrapper_source_id；SourceSnapshot 已有 parent_wrapper 和 blob.text。
- D/evidence_gap_context._project_tool_text 从 command wrapper.id 提取 ID；prepare_context
  从 observation.tool_results[].tool_use_id 传入，父子 source 继承。不能凭 event_order 或索引配对。
- pma_evidence_review/live_citations.visible_snapshot 保留 asdict(record)。普通写入 envelope
  有 records，删除没有，因此统一由 D/citation_gate_agent._attempt 的 self._parts.catalog 构造。
- claim_split_semantic.audit_request 已调用 operation_audit.from_closed_material；review_stage
  已有 parse_failure/None、overall/claim_reviews/model_verdict/batch/repair_feedback 接线，本轮保留。
- D/episode.PMAEpisode._actor_step 接受原 commands（JSON字符串数组）和 observation（JSON字符串），
  在 accumulated entry 保存 _evidence_identity=event_identity(event)，随后 prepare_context。
  原信封包含完整 ID inventory，生产目前不验证 command/result ID 一一对应。

在 _attempt 调用 context_from_catalog(parts.catalog, _validate_catalog, accepted_events)，
将返回 Context 作为 host-only audit_execution_context 带到 audit_request。不得从模型材料读绑定。
accepted_events 是原已接受 event 对象映射，不是新日志检索/人工配对参数。当前 parts 不直接
提供这个映射：生产适配需在 _actor_step 接受 event 时保留该窗口的公开信封（仅 event_identity
白名单字段即可），或当时计算等价的完整 wrapper-ID inventory，按现有窗口生命周期保留。
不能用缩短后的可见 source 数量冒充完整 event inventory；否则隐藏的重复 command ID 会漏检。
context_from_catalog 只解码现有两个 wrapper JSON 结构以计数 ID，不解析日志或增加模型调用。
完整信封只作 host witness，不进 B。上下文仅存 source 原文和 ID inventory/digest。

先执行现有 _validate_catalog；snapshot parent链按 source_id去重，再核同 namespace+event_id+
record_digest+tool_call_id 下命令root和结果root各唯一；另以整个已接受信封摘要及完整 ID 数组
交叉检查唯一性。stdout/stderr 等 leaf 不算多个结果。索引只用于读取既有已验证 field_path，
关系本身按ID，不按相同下标/文字/时间推断。缺 wrapper/ID/完整信封、重复或备选来源跨调用都保留 quote，仅标
unlinked_or_ambiguous，不合并。已确认调用身份但B只选一侧时仍保留独立X，另一侧为空；
不能把已知不同调用退化成不知道关系，也不能把单侧选择称为配对成功。完整性篡改则 ProjectionError。

## 投影契约与旧接口

project(selected, context) 的 selected 直接用已通过现有引用资格检查的 submitted_evidence，
不自授资格，不补邻居。返回 model_json 与 host_json 的冻结字符串。
model视图：evidence 每条 E 保留 quote 和替代来源语义；executions X 列出已选 command/output
片段 E 引用。一次 quote 多位置不变成多份独立证据。所有正文逐字不变；长 ID/digest留 host。
同调用关系不等于执行成功，更不确定脚本哪一行产生某输出。不返回“成功”的工程语义标签。
不同调用的事实仍能联合支持结论；未绑定不自动反驳/不足，不要求所有联合证据同调用。

保留旧 from_closed_material(operation_kind=宿主值,before=冻结值) 调用，再将 batch.model_input()
经 replace_evidence_view 替换共享 B 的呈现。用 dataclasses.replace(batch,
frozen_material=operation_audit.canonical(view)) 保持 Batch/labels/request关联，照旧 system_for。
只把 SCOPE_NOTE 作为现四步流程第1/3步的小补充，不换三态、短理由、批审/返工预算。
实际 request SHA、host_context SHA、证书重放必须按新视图重建并保存；不把 ProjectionError
改成语义 insufficient。沿已有 preparation/parse_failure 显式工程路径处理。
operation_kind、before/existing_gap绑定、parse_failure映射和失败子项解释全部沿用。
历史 split_v4_compare 未适配，锁旧 SHA，仅作旧入口限制说明，本轮不修或运行它。

## 干净开发样例与不扩 B

clean_pair.py 固定旧 call2 的窄事实原句，事实/事实+计划都 save_knowledge、同 B、同顺序、
同任务摘录；只追加一个未来计划及其子项。REFERENCE 在任何调用前已冻结，为人工开发
参考，未经独立盲标；不进模型。事实句只说 captured stdout contained a version line，
不升级成某特定 version 命令已执行。旧call3不同事实句/类别的结果不作为严格计划对照。

旧三例及结果原地不改。archive f9dbc6703a6b03034287943ecfb82fa6ea1f485c 的历史PATH例
task_excerpt为空、available in PATH有范围解释歧义；不能写成原文要求persistently或独立进程。
不以它单独证明修复。若新负例需要跨环境条件，须标人工构造且把该条件明确写入新题。
本轮没有扩充 B。若未来确需完整 version 命令，另建显式新版fixture，真实片段经既有资格
检查后加入；记录旧B/新B及hash和来源diff，不能追认旧输出已拥有此证据。
父环境提供的真实event21/23重建fixture注明 reconstructed_from_public_event、原/重建records
及身份空白规范化说明；它不代表完整历史visibility manifest。子线程未伪造真实运行字节。

## 实际验证与后续

python3 -m unittest -v test_projection.ProjectionTests test_projection.CleanPairTests
最终 8 tests OK；全为泛型身份/投影和配对夹具测试，不证明 LLM语义泛化或在线收益。
涵盖乱序、多命令、跨event同ID、缺ID/重复ID、隐藏重复wrapper、半边选择、替代来源歧义、
多leaf去重、精确quote/不补邻居、validator回调确被执行（测试为mock）及调用前冻结事实/计划对。

开发后仅小量候选审核：严格事实/事实+计划对2次，加一条非SQLite的不同调用/范围不足样例1次，
调用前冻结标签并保存真实请求和错误；不重跑旧组。已见PATH不是留出集；完整Task另行决定。
工程关联域无关，不包含SQLite/PATH/version特定分支或跨环境通用禁令；样例领域字符串只在
clean_pair开发夹具中。未实现语义裁判、检索系统、插件/Skill加载器或额外模型关联调用。

## 窄修补充与完整性

完整 field_path 继续呈现，不能只保留末段而混淆嵌套字段。只有 accepted_public_envelope
摘要语义才能与宿主已接受信封 inventory 配对；其它种类保留未绑定。

_parts 当前没有 accepted-event 映射。生产优先在原事件接受时生成轻量 inventory，保留
event_id、order、digest_kind、digest、完整命令 ID 数组、完整结果 ID 数组，包括重复及缺失
标记，绑定真实事件身份。随现有窗口淘汰，同周期构造一次 Context 复用；不另存完整事件
或无限历史，不按 claim 重建，不增加模型调用，不将人工 inventory 当生产已验证来源。
本原型 context_from_catalog 接收原 accepted_events 并即时提取这些字段；若生产选择轻量
接口，必须保持同一字段、摘要和计数语义。交接不能仅用现存 parts 调用便声称接入完成。

clean_pair 的追加计划使用原三例中的原计划句，事实句与操作类别固定不动。SQLite 等
领域文本只存在于开发夹具，不在关联算法或通用审核规则中。

## 冻结输入的具体用法

fixtures/frozen_candidate_cases.json 固定三条案例，candidate_model_requests.json 是离线构造的
参考请求，不是已发送请求；reference_labels_development_only.json 单独保存人工参考，不进入模型。
两个正例严格同事实句/类别/B/顺序，只追加原计划句。第三条是人工构造的非 SQLite 构建任务：
目标 alpha 的命令与 beta 的成功回执属于不同调用；alpha 的失败内容只在宿主witness里，
没有作为已选B送审，因此参考为 insufficient，不可偷用宿主原文将其判为 contradicted。

SCOPE_NOTE 的精确插入位置：旧 system_for(batch) 的第1步段落末句
“operation A, before-entry, task excerpt and claims help interpretation, not proof.”
之后插入换行与 SCOPE_NOTE，一次即可。不在末尾另堆重复规则，其他四步保持。
实际生产请求可与这份离线参考逐字段核对，但真实调用必须使用生产构造、资格和身份链。

历史B0不变，默认三例只用B0或明确的人工来源。optional_extended_evidence_B1.json 只是
准备好的显式新证据版本，不在本轮三次调用计划中，不自动运行或混入B0。它唯一增加
E3同一来源脚本的连续片段，旧/新hash与span均记录。旧三例/旧标签/旧返回不改。

短X有两种已确认身份呈现：same_call_pair 表示B选中了同一次调用的命令/回执；
verified_call_single_side 表示该调用身份已确认但只选择了一侧，另一侧E列表为空。
两者都不表示执行成功。未知、缺失及歧义来源不分配确定X。

## 返工映射与公开边界

审核理由若引用E/X，既有repair_feedback也需携带对应已选E标签和X关系，保证返工能理解
同一调用/不同调用的含义。只复用本次model视图里的引文及关系，不把Context或host_json
完整source原文塞给返工模型，否则会绕过B边界。别名在当前请求内有效，不跨请求复用。
原submitted_evidence身份及资格仍由原材料计算，反馈展示标签不是新的证据内容。
公开归档沿既有脱敏投影规则，不直接上传生产完整host_context，避免带出未选原文中的
凭据、私有端点或隐藏内容。本目录fixture仅用已经公开的材料及标明的人工数据。
