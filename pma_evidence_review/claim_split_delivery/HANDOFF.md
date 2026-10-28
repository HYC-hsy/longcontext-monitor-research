# 可复制开发交接：原观点拆解 + 同一证据包的一次批量审核

## 冻结边界

- 当前固定交付提交是候选；原基线固定为
  `f97033e98e36386474230ccc14f0c19f8a00e7ce`，不得覆盖原 worktree。
- 一次原操作 A + 原提交证据 B → 一次拆解 → **全部子观点 + 同一 B，进行一次批量审核**。
  不是拆成 n 个观点就调用审核 n 次。每次合格尝试固定为 1 split + 1 batch。
- 返回作者时指出原文哪部分、为什么不受证据支持；不要求作者解码 claim ID。
  全部必要观点 supported、结构覆盖有效且全局保真判断通过，才提交整个原操作。
- 一次作者修复后重新拆解、重新进行一次全量 batch，不继承任何通过结果。
  B′ 只能来自原冻结维护材料中的重新提交引文；删除协议保持不适用。
- 默认仍是 direct one-sentence。候选显式开关是
  `citation_review_strategy=claim-split-same-evidence-v1`。
- Span 全覆盖只是可检查的结构保障，不是语义完整性的数学证明；模型的保真判断仍可能出错。
- 不运行新真实模型或 Task，不复用旧启动授权，不重跑 HTML，不上传 profile/private_client。

## 1. 先完成无模型验收

使用已有 Python 3.12 和依赖，保持 UTF-8；不要在测试进程里把 native Harbor 和
PMA vendored Harbor 混用。`NATIVE_HARBOR` 从已登记环境读取，必须是干净的
`459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc` checkout；不要猜路径、下载替代版本。
以下 `python` 指上述解释器，所有输出路径必须不存在；如已有结果，换新的目录，禁止覆盖。

```text
python -X utf8 -B -m pma_evidence_review.tests.run_gate_regressions --native-harbor-source-root "$NATIVE_HARBOR" --report-dir claim_split_local_regressions
python -X utf8 -B -m pma_evidence_review.claim_split_cli export --trace-fixture sqlite_call_19 --strategy semantic-support-one-sentence-v1 --out direct_call19_initial.json
python -X utf8 -B -m pma_evidence_review.claim_split_cli export --trace-fixture sqlite_call_19 --strategy claim-split-same-evidence-v1 --out split_call19_initial.json
python -X utf8 -B -m pma_evidence_review.claim_split_cli fake --trace-fixture sqlite_call_19 --strategy semantic-support-one-sentence-v1 --out direct_call19_fake
python -X utf8 -B -m pma_evidence_review.claim_split_cli fake --trace-fixture sqlite_call_19 --strategy claim-split-same-evidence-v1 --out split_call19_fake
python -X utf8 -B -m pma_evidence_review.claim_split_cli fake --trace-fixture sqlite_call_61 --strategy claim-split-same-evidence-v1 --out split_call61_fake
```

这些命令不访问模型。fake 的默认答复是显式 canned fixture：原文完整单观点 +
insufficient，只验收运输/协议。真实多观点两调用、批量 ID 集合、原文反馈和作者修复链，
由完整测试中的多观点脚本夹具覆盖，不能把 canned 结果当作效果。

`export` **只导出初始请求**；实际拆解输出通过严格解析后，才动态生成唯一 batch
请求。运行目录保存 `initial-plan.json`、`requests.jsonl`、`responses.jsonl`、
`report.json`。比较 direct/candidate 时检查 `input_sha256` 相同，B 未增删、顺序未变。

现成冻结输入仍可使用原 `citation_cli build` / `citation_inputs.build_from_parent`
构建，经 `ci.validate` 验证后传 `--input packet.json`，替换 `--trace-fixture`。
不要自己把 Task logs 拼到 material。当前交付的 call 19/61 来自最新实际 SQLite
trace，具有独立 provenance；只有 `fixture.material` 进入请求，历史 verdict 和参考
期望不进入。特别检查：

- call 19 的唯一引文只证明未找到可用编译器，不能据此认定未安装编译器或源码已就绪；
- call 61 的后续安装记录本身不能反驳更早的超时观察，事件顺序和原命题范围必须保留。

如需自定义假响应，给 `fake --responses responses.json`；它是 raw JSON 响应字符串
数组，顺序为 split、**一份包含全部 results 的 batch**。不得为每个子观点提供一份
独立审核响应。额外、缺失或协议错误会留存报告并失败，不重试、不提交。

## 2. 真实 reviewer A/B 仅在获得单独明确授权后

此项是 reviewer-only，不运行 Task、不写记忆。先确认两个冻结输入和 direct/candidate
比较范围；拿到授权后，使用已存在的 profile 路径与 key，不创建凭据示例。保持现有
模型参数和 runtime policy，不增加新限额或 token/费用采集，先看审核效果。候选 1 split
+ 1 batch、direct 1 次仅是协议验收要求，不把 client calls 冒充全部 HTTP 请求。

```text
python -X utf8 -B -m pma_evidence_review.claim_split_cli run-profile --trace-fixture sqlite_call_19 --strategy semantic-support-one-sentence-v1 --profile "$EXISTING_PROFILE" --profile-key "$EXISTING_KEY" --execute-authorized-real-model --out direct_call19_authorized
python -X utf8 -B -m pma_evidence_review.claim_split_cli run-profile --trace-fixture sqlite_call_19 --strategy claim-split-same-evidence-v1 --profile "$EXISTING_PROFILE" --profile-key "$EXISTING_KEY" --execute-authorized-real-model --out split_call19_authorized
```

`--execute-authorized-real-model` 不是授权本身；没有新授权不要执行。当前交付没有执行
上述命令，测试只使用 mock loader。保存 raw 输出，不根据结果回填或改写固定输入。

## 3. 仅准备后续任务配置、重新认证，暂不启动真实 Task

从既有已核验配置复制开发副本，保持模型、task pool、source pin、预算、runtime policy、
维修次数等比较条件不变。候选增加如下字段，baseline 不加 strategy 字段：

```json
{
  "citation_review_gate": "gate-one-repair",
  "citation_review_strategy": "claim-split-same-evidence-v1"
}
```

下一道替换任务选 `fix-ocaml-gc`（task pool
`2fd12b88aafdd04a52c298e3940bcb189f9766d6`），不再跑 HTML；SQLite 可作为已有诊断参照，
但不能拿不同题的结果冒充严格 A/B。选择 OCaml 是因为多步修复/build/test 性质，
不是历史 reward；历史轨迹不进入模型证据。

```text
python -X utf8 -B -m experiment_runner plan --config "$NEW_CONFIG" --output "$NEW_PLAN_OUTPUT"
python -X utf8 -B -m experiment_runner prepare --config "$NEW_CONFIG" --output "$NEW_PREPARE_OUTPUT"
```

这些是准备入口，**不调用 `run`**。路径从用户已有环境/配置读取，不填猜测值。也可用
原 `single_run prepare`，加入 `--citation-review-strategy claim-split-same-evidence-v1`。
准备若要求新 certificate，应按现有 zero-model fixture 流程创建当前源码和策略绑定的
新证书，不降级检查、不拿旧 direct 证书顶替。以下三个既有入口都必须携带同一
strategy：`single_run_fixture`、`collect_single_run_fixture`、`gate_certification`。
其所有 runtime/profile 路径沿用已有已核验设置；仅准备本轮必要的无模型认证，不运行
真实任务。`gate_certification --evidence ... --mode gate-one-repair
--citation-review-strategy claim-split-same-evidence-v1` 只验证已收集证据，不执行任务。

最后报告：exact source SHA、source fingerprint、344 项离线测试及原始日志、新证书
状态，以及 OCaml 的 task/condition、沿用的模型参数和 runtime policy。清楚区分 fake
输出与另获授权后才可能产生的真实 direct/candidate 审核结果，先看效果，不新增
token/费用统计要求。**停下来等该次真实启动的新授权**。工程通过不等于方法有效，
旧 SQLite/HTML 授权不覆盖本次候选或 OCaml。

## 4. 完整结果 ZIP 与远端交付

把本轮实际完成的代码身份、测试原始日志、固定输入及来源映射、初始请求、拆解输出、
唯一 batch 请求/输出、原文反馈、修复和 receipt（如该流程实际发生）、报告与交接说明
按白名单打成完整诊断 ZIP，写清哪些是 fake、哪些是实际历史输入、哪些是真实模型
结果；没有执行的阶段明确标记未执行，不捏造文件。参考期望和历史 verdict 与模型输入
分开存放。不得上传 profile、private_client、密钥、认证头或未经审查的私有流；必要的
脱敏投影必须声明边界，不能冒称逐字完整私有原始流。

上传到本轮已授权的同一 GitHub 仓库 `pma_evidence_review/diagnostic_packages/`，
不另建公开仓库、不扩大分享范围。记录 ZIP 路径、字节数和 SHA-256，先完整解压/CRC
检查，再从远端读取确认 exact commit、文件字节/哈希可复验；报告远端 ref、commit 和
ZIP 链接。仅有本地 commit 不算已上传。归档与上传不授权新的真实模型或 Task 执行。
