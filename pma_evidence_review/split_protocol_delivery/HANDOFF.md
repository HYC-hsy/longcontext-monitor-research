# PMA split batch v2 — 开发交接

本轮真实模型、Task、官方评价调用均为 0。生产基线 6d2304d；当前修复只针对协议与
split 局部失败隔离。默认 direct 的请求和停止逻辑保持原样。历史原件不覆写。

一条 A 拆分一次，全部观点共享原 B 批审一次，不按观点分别调用。完整 A 和未覆盖
原文区间进入该 batch，不删除标点/连接词、不自动补观点。全部观点 supported 且
该 batch 明确确认对 A 的保真，才可提交；不能把 B 中但 A 未说的信息当作漏拆。
原文反馈优先 host 锚点，不要求作者理解 claim 编号。模型仍可能误判覆盖或证据。

v2 技术解析失败可用原有一次作者返工机会，不是增加格式修复模型调用；新版 A/B′
仍全部重审。同目标失败阻断其后续依赖；独立目标继续。全局 transport/protocol/
cancellation/host 错误仍停批。新策略需要新源码/策略认证，不能用旧证书顶替。

公开八槽 ZIP 已核对 103996503 bytes / SHA256
`a30ff99e694d645a507c1841c33960765cb3bd0baceb17369118a43855b76e25`。
回放108份 split：71份仅可进入 batch（历史没有 batch，未做新语义审核）；35份历史
batch 可按新协议解析；2份仍失败（非原文片段、decisive verdict 无证据）。这些不是
新方法效果、不是历史操作追认通过；REPLAY_INDEX 保存逐项路径/行/哈希，未复制原响应。

本机Python3.11完整隔离runner在PMA Harbor语法预检退出2，native1项跳过，总体退出1。
SUPPLEMENTAL_PMA_PY311 仅为同一PMA清单的补充执行（跳过Verifier身份预检，仍禁网），
不替代Python3.12+的隔离全量验收。目标环境须保持native Harbor固定459ff，与vendor分进程。

以下整个代码块可直接转发开发线程；占位路径从既有已验证环境读取，不编造或显示凭据。

```text
任务：接收 PMA split batch v2，仅先离线验收。不得沿用旧真实运行授权。
仓库：HYC-hsy/longcontext-monitor-research
分支：repair/pma-split-protocol-v2-20261029
固定SHA：使用本次交付回复的 exact SHA，记录为 CODE_SHA。

1. 保护现有工作树。fetch 新分支后，新建 detached worktree 到 CODE_SHA；不要 reset/force。
   git fetch origin repair/pma-split-protocol-v2-20261029
   git -c core.longpaths=true worktree add --detach <NEW_WORKTREE> <CODE_SHA>
   cd <NEW_WORKTREE>
   后续每条命令失败立即停止，保存原始stdout/stderr；新输出路径必须不存在。

2. 使用已有依赖齐全Python3.12+，UTF8，NATIVE_HARBOR必须为现有固定
   459ff6ec99417589b7f679d14ddf3b3f0ae4f1dc checkout。不得混vendor/native导入。
   python -X utf8 -B -m pma_evidence_review.tests.run_gate_regressions --native-harbor-source-root <NATIVE_HARBOR> --report-dir <NEW_REPORT_DIR>
   python -X utf8 -B -m unittest pma_evidence_review.tests.test_split_protocol_v2 -v

3. 历史公开回放不发模型。已有ZIP可直接用；若需从固定Git对象物化，用Python
   subprocess.check_output(['git','show', COMMIT+':'+POSIX_PATH]) 后 write_bytes，
   不用旧Windows PowerShell文本重定向写二进制ZIP。
   COMMIT=c40f191878d1c45afccba4098ba4a16c14129c2f
   POSIX_PATH=pma_evidence_review/diagnostic_packages/PMA_CLAIM_SPLIT_EIGHT_REAL_TASKS_20261029.zip
   python -X utf8 -B -m pma_evidence_review.split_protocol_delivery.replay --archive <PUBLIC_ZIP> --out <NEW_REPLAY_INDEX.json>
   核对71 eligible/no batch、35 archived parses、2仍失败；不得把它们追认成历史写入成功。

4. 导出/fake接线（reference labels不进入模型）。准备既有冻结citation packet时，使用
   citation_cli/ci.validate，不拼完整Task日志。也可用已有公开开发夹具：
   python -X utf8 -B -m pma_evidence_review.claim_split_cli export --trace-fixture sqlite_call_19 --strategy semantic-support-one-sentence-v1 --out <NEW_DIRECT_PLAN.json>
   python -X utf8 -B -m pma_evidence_review.claim_split_cli export --trace-fixture sqlite_call_19 --strategy claim-split-same-evidence-v2 --out <NEW_SPLIT_PLAN.json>
   python -X utf8 -B -m pma_evidence_review.claim_split_cli fake --trace-fixture sqlite_call_19 --strategy claim-split-same-evidence-v2 --out <NEW_FAKE_DIR>
   export只有初始请求；batch须等实际split解析后生成。核对direct/v2 input_sha一致、B同顺序同字节，
   v2实际为一split加一batch。fake结果不证明语义修复。--input <PACKET>可替换--trace-fixture。

5. 新生命周期证书：先完成步骤2；用现有single_run_fixture零模型流程生成本代码的A/B证据。
   所有路径参数保持已有已验证配置：--official-source-git、--task-profile-file、--ga-source、
   --runtime-root、--worker-python、--harbor-python、--bench-root、--harbor-source-root、--pma-profile-file。
   对每个gate-only/gate-one-repair分别生成证书；候选B还必须显式给
   --research-candidate pma_gap_evidence_v1 --citation-review-gate <MODE>
   --citation-review-strategy claim-split-same-evidence-v2。
   模块前缀 D=method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013
   python -X utf8 -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_fixture --task sqlite-with-gcov --condition A --output <NEW_A> <上述既有路径参数>
   python -X utf8 -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.single_run_fixture --task sqlite-with-gcov --condition B --research-candidate pma_gap_evidence_v1 --citation-review-gate <MODE> --citation-review-strategy claim-split-same-evidence-v2 --output <NEW_B> <上述既有路径参数>
   python -X utf8 -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.collect_single_run_fixture --a <NEW_A_ARCHIVE> --b <NEW_B_ARCHIVE> --output <NEW_REPO_EVIDENCE_DIR> --task-profile-file <EXISTING_TASK_PROFILE> --pma-profile-file <EXISTING_PMA_PROFILE> --research-candidate pma_gap_evidence_v1 --citation-review-gate <MODE> --citation-review-strategy claim-split-same-evidence-v2
   本地提交证据目录（包括其.gitattributes），不得把profile加入Git。记录CODE_SHA与含证书HEAD，
   核对两者生产源码diff为空；不要假称HEAD仍为CODE_SHA。
   python -X utf8 -B -m method_discovery.curator_supervisor_convergence_v0.pma_full_upstream_ga_v1_20261013.gate_certification --evidence <NEW_REPO_EVIDENCE_DIR> --mode <MODE> --citation-review-strategy claim-split-same-evidence-v2
   缺Docker/Harbor或认证失败则报告，绝不降级检查。

6. 停在离线交付。未来真实实验必须另获当前版本与槽位的明确授权：只选SQLite与fix-ocaml-gc，
   不跑HTML。保持模型、任务版本、runtime policy与比较条件一致；direct策略为
   semantic-support-one-sentence-v1，候选为claim-split-same-evidence-v2；两者各gate-only/one-repair。
   正式single_run prepare携带相同strategy/mode及匹配新--certification-dir；run仍需独立一次性授权。
   不预编真实结论；新模式局部错误隔离属于干预差异，不能将整体变化只归因于语义提示。
   记录实际split/batch/repair/提交/拒绝/同目标阻断/全局停机和receipt，不以supported率称准确率。

7. 本轮或以后已授权实际完成的结果按白名单打ZIP：代码身份、测试日志、公开输入来源、
   实际请求/响应的安全投影、report/receipt、manifest、说明。没有运行的阶段注明未执行。
   不含profile/private_client/凭据/认证头/私人授权。逐文件SHA256，ZIP大小/SHA256、CRC重开验证。
   上传同repo diagnostic_packages 新文件与独立归档commit，绝不覆盖旧包；回读远端字节核验。
   本轮上传代码/离线证据不授权真实模型、Task或评价。
```
