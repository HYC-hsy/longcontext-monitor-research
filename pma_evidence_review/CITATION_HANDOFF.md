# 提交引文封闭充分性审核 v1：接收、准备检查、未来实验与上传

新方向：只判断第一阶段原操作实际提交的引文是否足以支持原正文。不是全轮来源重审，
不是 whole-focus，不切分、不改写、不替它补引。旧 whole/focus 的代码和语义未修改。
基线归档 `1b34bec46a00eaf4b6b51bcae249dcd609136d3c`，独立分支
research/pma-submitted-citation-v1-20261026。以最终回复的代码完整 SHA 接收。

## 实际准备结果（开发样本，不是语义标签）

| 样本/操作 | 恢复的提交引文 | 准备状态 | 模型调用 |
|---|---|---|---|
| SQLite C14 op0 update_status | 3 条 exact_unique/各单候选 | ready | 获真实授权后一次 |
| SQLite op1 delete_gap | 当前删除协议仅 memory_id | not_applicable_delete_protocol | 无 |
| SQLite op2 save_procedural | 2 exact + 1 fuzzy，fuzzy 有2个替代位置 | citation_set_not_eligible | 无 |
| HTML C2 op0 update_status | 1 exact_unique/单候选，来源 tool_command | ready | 获真实授权后一次 |
| HTML op1 delete_gap | 当前删除协议仅 memory_id | not_applicable_delete_protocol | 无 |
| HTML op2 save_gap | 2 exact + 1 fuzzy | citation_set_not_eligible | 无 |
| HTML op3 save_procedural | 1 exact + 1 fuzzy | citation_set_not_eligible | 无 |

全部13个宿主候选的可见区间、snippet hash、role/order/visibility/source identity 已核对。
HTML status 的成功字符串来自 commands/0/args/content、字符区间[4885,4934)，构造时仍是
源码 tool_command，不是执行回执。SQLite fuzzy 的两个位置是替代定位候选，不是两条佐证。
不筛掉坏引用再用剩下的引用放行整个操作，也不以 aggregate disposition=bound 代替逐item检查。

## 新输入身份与恢复边界

schema=`pma-submitted-citation-input-v1`，独立完整身份：

- SQLite citation_input_sha256 = `fbff3622cb07e5ae6c66ec5ad7f6285326b00ceba08dfb0fa2144477d35484d8`
- HTML citation_input_sha256 = `a9623c027854de358cb40845e2df3684937c89fef7d9f0d866214eef9722310d`

旧 0aa854… / 4760d6… 仅作为 parent_input_sha256 关联，不冒充新输入身份。
新摘要覆盖所有原操作、恢复 alignment、准备结果、规范上下文及宿主 provenance；另列
host_provenance_sha256。对 canonical UTF-8 sort_keys 紧凑 JSON 求 SHA256，排除摘要自身。
改变 submitted quote 会改变新身份；改变未引用宿主材料会改变 provenance/完整身份，
但不得影响实际模型 prompt。哈希校验是内容一致性，不是外部签名或语义证明。

适配器复用 INDEX/gzip/解压hash、周期/sequence、op/revision/body/before/delete 链校验。
按当前写入 revision 从 gap_alignment.alignments 取 alignment_json.items，保留quote/hint/
status/reason/candidates/metadata及顺序/重复条目。删除绝不拿旧 revision 的写入引用替代
本轮不存在的删除理由。核心接受已构造 citationpacket，不读取归档、最终bank或active状态。

每个candidate仅在原manifest-visible切片中验证，保留宿主推定身份和original_excerpt；
source_hint是第一阶段可选提示，不等于模型选择该来源。snippet必须精确匹配可见原文。
完整source hash若与从0开始的可见文本digest一致，记录matches_visible_text；如果全原source
不可恢复，只记录full_source_unavailable_not_asserted，不补隐藏文本、不声称验证整源。
实际两个样本的13候选完整源hash也都与可见文本一致。角色/顺序/visibility/源身份和snippet
不能因无法恢复整源而绕过校验。

两份选定raw_response_phase1均为空。恢复的是已记录alignment中的提交quote，不承诺恢复
完整工具args、缺字段vs空数组、被宿主丢弃的malformed输入。missing alignment、malformed、
no_evidence、unbound/fuzzy/multiple/候选完整性错误均有明确准备状态或issues，verdict=null。
failed/unknown明确未审核。严格ready要求整项逐item exact_unique、单candidate、quote与
可见excerpt逐字一致；无重新搜索/纠错/候选选择。原文省略/隐藏边界不补未来历史。

## 宿主材料与模型材料严格分开

`host_provenance`保留旧冻结packet，仅供宿主验证，包含全可见源/维护提示/旧记忆等。
它绝不整体序列化进模型请求。实际 allowlist 投影只有：

1. 本op的op_index/action/memory_id/revision_id/content/content_sha256；没有before或别的操作。
2. 该op全部合格submitted_quote，依原顺序E1/E2，必要role/field_path/source_id/event_order；
   明确source_identity_origin=host_inferred_not_model_selected。无候选日志、邻窗或额外结果。
3. normative_requirements_context默认空字符串。程序接口可显式给原任务的逐字摘录，验证必须
   属于原任务；只解释要求是什么，不能证明执行。归档CLI默认不加完整任务。
   本轮及后续首次真实实验固定采用默认空规范性上下文，不能中途换范围。原文有完成断言而
   缺少定义完成所需任务要求时，局部成果不能自动代表全部要求，模型应保留不足。
   可选摘录只允许原task_instruction逐字内容，语义上仅作规范解释；宿主验证出处不能
   自动证明摘录全为规范内容，不能通过它注入执行事实或任意上下文。

投影身份audit_request_sha256按实际system/prompt/tools计算，与输入/provenance身份分开。
新增未引用支持材料、其它op的引文/未来标签不会改变当前请求。模型不找新证据、不摘引、
不填来源或坐标。只有引用不足就要求补引，不能用未提交的命令上下文救supported。

## API、输出及语义限制

```python
from pma_evidence_review.citation_inputs import build_from_parent, validate
from pma_evidence_review.citation_review import requests, review
# alignments为当轮已记录、按revision索引的宿主定位产物；不是未来active bank。
packet = build_from_parent(frozen_parent_packet, alignments)
plans = requests(packet)  # 本地准备/导出，不调用模型
report = await review(packet, transport)
```

独立report schema=`pma-submitted-citation-report-v1`，strategy=submitted-literal-citation-v1。
模型唯一三字段输出示例：

```json
{"op_index":0,"verdict":"insufficient","explanation":"所提交的E1只建立了……，不足以支持正文中的……。"}
```

只接受小写supported/contradicted/insufficient，拒绝旧evidence/其它字段、错误op、重复JSON键。
引文及绑定由宿主回填报告，不让模型替换。每个原操作都有结果与preparation；ready项才调用。
调用异常call_error、已收到非法工具/非文本响应protocol_error、格式错误parse_failure分别记录；
保留可用raw_response/model_verdict，正式verdict=null。不存在准备通过自动等于语义通过。

supported仅表示提交的字面引文足以支持原正文需证据的所有判断/范围。部分支持为不足，
反驳需要实际不相容证据；不足不代表原结论假。计划问题不自动当错误事实，解释事实前提。
源码可证明窄静态性质，不能把print成功字符串当运行成功。通过也不证明全历史无反证、
没有选择性引用、记忆最优或任务真实完成；无全日志时不能声称抓住未引用反例。
本轮所有fake只验证流程，没证明模型会正确判断HTML源码来源。

## 固定SHA接收与离线验收

从最终回复的代码SHA新建worktree，保留本地修改；当前Python3.10+和现有依赖，不重装环境。
本机macOS/Python3.11.15使用既有../offline-deps（regex）；Windows UTF8/socketpair未改，
本次无新的Windows实机执行。旧whole/focus原回归仍运行。

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review.citation_cli build --repo . --sample sqlite --out sqlite-citation-input.json
python -m pma_evidence_review.citation_cli build --repo . --sample html --out html-citation-input.json
python -m pma_evidence_review.citation_cli validate --input sqlite-citation-input.json
python -m pma_evidence_review.citation_cli validate --input html-citation-input.json
python -m pma_evidence_review.citation_cli export --input sqlite-citation-input.json --out sqlite-citation-plan.json
python -m pma_evidence_review.citation_cli export --input html-citation-input.json --out html-citation-plan.json
```

输出路径必须不存在。确认新hash和上表状态，两个plan各仅op0 request非null。
不要把旧packet传给新CLI，或把新packet传给whole/focus；schema错误应拒绝，不做隐式转换。
离线工程ZIP仅含合成raw input/response、模型投影、计划/report、测试日志、公开样本的准备摘要
与哈希索引，不包含新的真实原件/配置/秘密。解包到新目录后复验：

```bash
python -m pma_evidence_review.citation_cli export --input /demo/synthetic-citation-input.json --out /demo/reexport.json
python -m pma_evidence_review.citation_cli fake --input /demo/synthetic-citation-input.json --responses /demo/synthetic-responses.json --out /demo/replay
```

reexport应与synthetic-request-plan.json相等；replay/report.json与synthetic-report.json相等。
INDEX.json逐文件SHA可复算。不要把这个ZIP称真实模型诊断。

## 给未来本机开发线程的完整任务指令（另获真实调用授权后）

检出本次固定代码SHA，读AGENTS保护其他工作，先运行全量离线测试和上面的build/validate/export。
核对新citation输入hash及严格准备状态。只使用既有opus48 profile，不读取或展示秘密内容，
不改profile参数、不新增预算上限/成本统计。cwd与--repo指向同一固定checkout，清除旧
PYTHONPATH以免串版本。SQLite先、HTML后，每个样本只给ready op0一次逻辑调用；delete/fuzzy/
无引用项不强行跑。不启动全context/whole-focus补救，不改引用或调参自动重跑。

未来已获真实授权时的命令（替换既有私有路径；本轮未执行）：

```bash
python -m pma_evidence_review.citation_cli run-profile --repo /absolute/checkout --input /private/sqlite-citation-input.json --out /private/sqlite-citation-real --profile /private/existing-profile.json --profile-key claude_monitor_opus48 --execute-authorized-real-model
```

先检查报告：全部原op有条目；op0工程ok，其余是预期not_reviewed_preparation，不能把这些
准备阻塞当语义insufficient。若op0 call/protocol/parse错误或准备清单改变，停止并报告，
不自动修响应/重跑。工程正常后才执行HTML：

```bash
python -m pma_evidence_review.citation_cli run-profile --repo /absolute/checkout --input /private/html-citation-input.json --out /private/html-citation-real --profile /private/existing-profile.json --profile-key claude_monitor_opus48 --execute-authorized-real-model
```

逐项诊断只根据该op提交包能建立什么，不拿未提交的全轮证据为模型“纠正成支持”；需要外部
材料讨论时另列全历史背景，不混入封闭充分性标签。无gold，不报告支持比例作为准确率。
记录真正不可审的5项及协议缺口，不宣称delete/fuzzy已做语义判断。

完成后用户已授权将本任务诊断ZIP直接上传同一GitHub仓库独立提交。白名单：两个新冻结
citation输入、导出plan、requests.jsonl/responses.jsonl/report.json、逐项DIAGNOSIS.md、
代码SHA/环境说明、离线测试日志、逐文件bytes/SHA256索引。宿主provenance若含私人内容先
检查，不得加入profile、private_client、凭据或无关个人文件；不递归打包工作目录。确认原始
响应无意外秘密后才能公开，发现秘密则停止发布并报告，不隐瞒。缺文件如实说明，不伪造。

ZIP重开CRC及逐文件hash验证，记录大小/SHA256。在归档分支只stage ZIP和说明，非强制推送：

```bash
git add -f pma_evidence_review/diagnostic_packages/EXACT_SUBMITTED_CITATION_DIAGNOSTIC.zip
git commit -m "Archive authorized submitted-citation diagnostic package"
git push origin HEAD:research/pma-submitted-citation-diagnostic-DATE
git ls-remote origin refs/heads/research/pma-submitted-citation-diagnostic-DATE
```

若git无凭据，使用已授权GitHub connector，不读取秘密找凭据。回读远端ZIP字节/hash和
exact commit，给固定链接。上传授权不等于现在已授权真实调用；本轮只实现、离线验收和交付。
