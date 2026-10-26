# v5：完整操作审核＋无改写原文焦点核验

本轮只做实现、fake 工程验收及工程 ZIP 发布，未执行真实模型、Task、评价或正式记忆写入。
whole 语义底座固定 A=`77f0f91dc4f508c9ef8e39c9f01e1d50c59eebd7`。
分支从归档 `667d05b14e0f309c27a29c5ea3fc65f4f5b613b3` 继续，保留 A/B 原件。
失败候选比较段已移除；旧候选隔离测试随该阶段退休，可在旧提交复验，不污染本次实验。

## 接口和实验边界

默认入口仍 whole-only；只有显式选择 whole-focus 才增加局部核验：

```python
from pma_evidence_review.focus_review import focus_plan, review
from pma_evidence_review.location import locate
plan = focus_plan(packet)                    # 纯本地，不调用模型
report = await review(packet, transport, locator=locate)
```

`packet`/第一阶段/完整输入摘要不变。CLI `export/fake/run-profile` 新增
`--review-mode whole-focus`；默认 `--review-mode whole` 保留 A。
未恢复 extract、--mode 或任何模型抽取/改写/分类。
whole 的实际 system/prompt/tools、原正文、before、删除问题、所有来源/上下文与 A 完全一致；
测试同时比较七个冻结请求与同一 fake 输出下的 whole report。共享执行函数只消除重复代码，
未改变协议、绑定、响应捕获、客户端参数或 whole 判断逻辑。

执行顺序固定：所有成功操作各一次 whole，然后按 op_index 和原文顺序核验预定局部。
所有 focus 请求在任何响应产生前构建，不输入 whole/local 判定、解释或引用选择。
这是输入隔离，不是统计独立。对照 A 就是报告内同一次 whole_report，不再另跑 A 造成随机差异。

## 无损分片和身份

成功 save/update/status 的正文按保守自然句、段落及列表项分片。标准库实现，不依赖新包。
每项含 op_index/memory_id/revision_id/content_sha256、start/end、text/text_sha256、focus_id。
`coordinate_unit=python_unicode_code_points`：Python 字符串的 `[start,end)`，不是 UTF-8 字节。
不 strip、不补主语、不规范化 Unicode/标点、不删短句，所有区间连续重建原文（包括空白）。
前导/空白分段附着邻段；小数、路径、URL、常见缩写、引号/括号保守保护；fence/缩进代码和
表格保留整块，列表项不强拆。未知或未闭合边界保留大块；不保证语言学原子性，句内仍可混合
真假判断。机械文字覆盖不是语义覆盖，不保证每个条件单独成为焦点。

局部仍看完整原操作/上下文来解释前后句条件，但只能判断当前原文焦点；其它正确句子不
能替代当前焦点的支持。纯计划/问题的不足不自动等于记忆错误，不增加用途分类器。

- 全文只一个区间：`execution=reused_whole`，复制关联本次 whole 结果，不发等价 local 请求。
- delete_*：只 whole 固定删除问题，不切旧条目，不用其它操作结论为它背书；删除误放未自动解决。
- failed/unknown：明确 no_focus_reason，仍保留 whole 未审核状态，零 local 调用。
- source 引用 start/end 是原来源坐标，与 focus 的 operation.content 坐标不同，不能互用。

## 输出和工程错误

导出 `pma-focus-plan-v1`：whole_plans 和逐操作 focuses；request=null 表示复用或未审核。
新报告 `pma-whole-focus-report-v1` 嵌入完整未覆写的 whole_report、逐操作 focus_plan、
local_results、no_focus_reason、diagnostic。策略 whole-A-verbatim-focus-v5。
每个预定焦点恰一结果，按 host focus_id 绑定；模型仍只返回既有四字段
op_index/verdict/explanation/evidence，不要求重复 focus_id/坐标/来源身份。
局部调用顺序由宿主绑定身份，不接受模型返回的多结果数组或新ID字段。
相同响应文字本身可合法重复；不靠字符串去重伪装身份校验。

引用仍一基 `{document_index,quote}`，必要时 source start/end；严格角色/身份/可见范围/
文字定位、未知/越界/歧义拒绝、空证据不可 supported/contradicted。保留原始响应、model_verdict、
请求payload摘要；protocol_error 与 call_error 分开，不执行工具。无 locator 不能默认通过。

诊断没有综合 verdict、比例或写入门槛：

- engineering_incomplete：whole/local 工程失败或焦点ID缺失/重复/未知。不可当语义不足。
- whole_local_disagreement：whole supported，但有效 local 是 insufficient/contradicted。
- no_disagreement_observed：只表示本次未观察到上述分歧，不代表综合通过。
- not_applicable：delete/failed/unknown 无局部。

分歧ID单列，即使同时有工程缺失也不隐藏。local 支持不能升级 whole 不足，local 不足不能
自动判整条记忆错。无第三模型、投票、自动返工、回滚、写入或依赖图。

## 接收与离线验收

从最终回复的代码 SHA 建新 worktree，保留旧历史；当前 Python 3.10+ 和现有 regex 依赖。
从该 checkout 根执行：

```bash
python -m unittest discover -s pma_evidence_review/tests -v
python -m pma_evidence_review build --repo . --sample sqlite --out sqlite-focus-input.json
python -m pma_evidence_review export --review-mode whole-focus --input sqlite-focus-input.json --out sqlite-focus-plan.json
```

文件/运行目录必须不存在。原 UTF8/socketpair 兼容保留；本次实际 macOS Python3.11.15，
`PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=../offline-deps /opt/homebrew/bin/python3.11 -m unittest discover -s pma_evidence_review/tests -v`。
没有新 Windows 实机运行。旧输入 hash SQLite=0aa854b8…、HTML=4760d69e… 不变。

复验离线交付 ZIP 的合成 demo：解压到新私有目录，依据 INDEX.json 的 code_sha 检出代码后：

```bash
python -m pma_evidence_review export --review-mode whole-focus --input /path/demo/synthetic-input.json --out /path/demo/reexport.json
python -m pma_evidence_review fake --review-mode whole-focus --input /path/demo/synthetic-input.json --responses /path/demo/synthetic-responses.json --out /path/demo/replay
```

比较 reexport 与 synthetic-plan.json、replay/report.json 与 synthetic-report.json。
合成 verdict 是固定 plumbing probe，不能作为诊断效果或 gold。ZIP 内 INDEX 对每个文件记录
大小/SHA256；README 明确是工程验收，不是模型诊断。构建脚本为
`python -m pma_evidence_review.tools.build_offline_delivery --out /new/private/delivery --code-sha FULL_SHA`。

## 未来本机真实实验指令（另获真实调用授权后才执行）

授权范围须明确模型/输入/执行范围；沿用既有 profile，不新增成本统计或人为上限。
本次实现授权不包含现在执行这些命令。新本机线程收到真实授权后执行以下任务：

1. 检出交付代码 SHA，检查工作区与规范；先全量离线测试和 export，验证 whole payload 与 A。
2. 用仓库现有 v4 ZIP 中两个冻结 input.json（或公开 build 得到同 hash），不读取诊断/响应作为
   模型输入，不执行轨迹命令。原件 ZIP SHA256 为
   adc43e5719cbdc7a0aa1ac3766d07f79722fb1256c59c704fb611f03a6836f28。
3. SQLite、HTML 各一次 whole-focus，串行、私有新目录；不要再跑独立 whole-only 对照。
   --repo 指向当前 checkout，进程 cwd 也是该目录，移除旧 PYTHONPATH，确认实际模块路径。
4. 每次返回后检查 whole_report 与所有 local 工程状态；失败保留原始文件并报告，不自动修复
   响应、调参或重跑。现有单个 run 内会继续记录后续操作；不在此机制中改变该行为。
5. 从嵌入 whole_report 保存 A-whole-report.json（同一次原始响应，不是历史重放）。逐操作比较
   whole 与 focus 分歧及工程缺失，保留代码支持的窄正例；不把计划问题不足当错误，不称准确率。
6. 诊断完成后按下述白名单打包，并直接上传 GitHub 独立归档提交。用户已授权此任务诊断 ZIP
   上传，无需另问上传许可；不包含 profile、凭据、private_client 或无关私人文件。上传前检查
   原始文本中是否意外出现秘密；发现则停止发布并报告，不能把秘密随诊断包上传。

示例运行命令（路径/key 用既有私有值，不打印配置；未来获准才执行）：

```bash
python -m pma_evidence_review run-profile --review-mode whole-focus --repo /absolute/checkout --input /private/sqlite-input.json --out /private/sqlite-focus-real --profile /private/existing-profile.json --profile-key EXISTING_KEY --execute-authorized-real-model
python -m pma_evidence_review run-profile --review-mode whole-focus --repo /absolute/checkout --input /private/html-input.json --out /private/html-focus-real --profile /private/existing-profile.json --profile-key EXISTING_KEY --execute-authorized-real-model
```

Windows 同一 CLI 支持绝对 Windows 路径。不要使用已移除的 --mode。未来线程应先完成上一步
工程检查再启动下一样本。报告本机源码 SHA、输入 hash、whole/local 身份和原始输出位置。

### 未来诊断 ZIP 白名单及发布（本轮不执行）

允许：两个冻结输入、两个导出 plan、每个 run 的 requests.jsonl/responses.jsonl/report.json、
由嵌入结果保存的 A-whole-report.json、人工逐项 DIAGNOSIS.md、源码/环境说明和测试日志。
只显式枚举这些文件，不递归打包整个目录；创建 FILE_INDEX.json 记录大小/SHA256和代码 SHA。
无相关文件不得补造，缺项写清楚。ZIP 命名如 PMA_AUDITOR_WHOLE_FOCUS_REAL_DIAGNOSTIC_DATE.zip。
重开检查 testzip 和索引，再计算 ZIP 大小/SHA256；逐文件确认无配置/凭据/无关私人内容。

在保留其他修改的归档分支只 stage ZIP 及不含秘密的索引/说明，提交并非强制推送：

```bash
git add -f pma_evidence_review/diagnostic_packages/EXACT_DIAGNOSTIC_ZIP.zip
git commit -m "Archive authorized whole-focus diagnostic package"
git push origin HEAD:research/pma-whole-focus-diagnostic-DATE
git ls-remote origin refs/heads/research/pma-whole-focus-diagnostic-DATE
```

若 git 无凭据，使用已授权 GitHub connector 上传二进制 blob + tree/commit，不能读取秘密找
凭据。远端回读 commit 和 ZIP 字节/hash，提供固定链接，不把本机路径当交付附件。
此上传授权不扩大真实实验范围；无 gold/留出集，无模型效果增益结论。

### v5.1：跨消息层目标一致

local 现在使用专用 FOCUS_SYSTEM，最高优先级也仅要求审核当前原文区间；完整 operation/
before 仅解释引用、条件与限定，不把其它内容变成额外目标。来源安全原则保留。若焦点本身
是完成断言仍须审核。whole.SYSTEM 及所有 whole payload 不变，继续逐字对照 A。
策略为 whole-A-verbatim-focus-v5.1，86 项离线测试通过；新增最终请求回归检查 system/user
两层目标一致。旧 v5 ZIP 保留，新 v5.1 ZIP 是此修正的工程验收，不是新真实诊断。

### v5.2：删除 whole 错误不得被摘要遮住

策略更新为 whole-A-verbatim-focus-v5.2。delete_whole_only 仅在 whole 工程正常时显示
not_applicable；调用、协议、解析或绑定失败保留 engineering_incomplete。failed/unknown
本来未审核的项仍明确 not_applicable，不表示语义通过。87 项离线测试通过，新增删除 whole
异常回归。最终交付使用 v5.2 包；未发布的中间 v5.1 包不作为交付。
