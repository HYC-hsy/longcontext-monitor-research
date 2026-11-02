# A：冻结输入记忆入口与默认读取优化

基线 `19405c86d4081c0a48517608671265ff622f71bf`；最新源码固定为 `26ff924d083616c5b6c91136b6ee6af312f8f83c`。仍显式选择 `--candidate source-links-context-v1`。本目录是本轮交付；旧 `source_links_context_delivery_20261102` 目录仅保留历史版本证据。

本轮修复两点：默认读取不再先空耗一轮；生成时实际看见的旧记忆，其来源入口不再随活动条目删除而丢失。没有增加模型步骤、自动祖先遍历、语义审核或向量库。GAP 同时按新授权调整定义，语义收益尚未验证。

## 读取协议

仍只有 `memory_read_source(memory_id, view?, cursor?)`：

- 省略 view：有选定来源先读来源；确实未关联来源且有有效生成窗口时直接返回 context。
- 显式 `view='sources'` / `'context'`：严格读取对应内容；来源表或绑定损坏不会触发宽松回退。
- 所选来源独立完好时，context/输入目录缺失或损坏不会遮蔽 sources。回执单独给出 coverage unavailable/integrity_error、具体错误及目录不可用状态，不发放坏 handle；context 及需要自动回退到 context 的读取仍严格拒绝损坏。
- 返回 `requested_view`、`resolved_view`、`fallback_reason`；目录、派生记忆内容、原始来源/生成输入各有独立字段，不把 context 伪装成选定证据。
- 分页续读须保留原来的 view 选择，包括省略 view；cursor 绑定目标、快照及请求/解析视图，不能跨视图重放。

每个实际请求的既有 window 额外冻结本轮已展示记忆的内容、类别及来源 ref，包括有内容的 STATUS；续轮仍对应实际 prompt 中的初始记忆，另记录先前读回执中的历史 handle。未展示条目不被加入目录。新摘要照旧绑定本生成窗口，source_ids 只作重点定位。

回执中的 `input_memory` 目录条目含简短预览和 H1 handle。handle 只有完整目录条目实际返回后才授予；绑定任务、窗口字节哈希及记录快照，不能变成任意路径或全局 archive 查询。通过 handle 读取旧记录时，活动旧条目可以已删除、换内容或被预过滤，仍使用冻结 ref。handle 不可删除；可在 source_ids 中引用其冻结来源，缺关联仍保留未知标记，不冒充原文已读或结论已证实。

明确引用的 H 还以 `cited_history_handles` 写入新条目 ref，与 sources 同一次原子提交，不回写已经冻结的生成 window。目录内优先列这些输出引用，标记 `explicitly_cited_history`，区别于 `displayed_record` / `earlier_read_handle`。因此 C 可直接给出被明确引用的旧 H，不必再绕过父摘要；legacy 仍保留 unresolved。引用或继承不等于读过或证明。

“只读”指不能修改活动记忆或历史内容，并非零存储副作用：首次返回新 handle 会持久化 grant 元数据。该写入失败仍是工程错误，不伪装成成功读取。

来源视图优先返回所选原文，再分页目录；context 视图先给目录，方便按需跟进。目录是 input coverage，不是逐 claim 支持。旧窗口没有当时的覆盖快照时明确标记 `unrecorded`，不从摘要文字补造来源。新功能不追溯修复已经丢失的旧绑定。

两种活动读取及历史读取最多共用四次总 read，但只有 r0/r1 两个可串行发现、跟进的读取轮；r2 write-only，不是四页可串行读。短 summary→H(A)→A 原回执可在 r0/r1 完成，长 origin 必须如实 partial。sources 目录可能排在大来源之后，不能保证任意祖先都在一次维护内可达。每页整 JSON 不超过 8000 Unicode 字符；测试中的 helper 百页循环仅验传输，不代表真实 P1 可读完整历史。页序完整不等于来源选全或语义核验。

## GAP 与提示

仅替换 A 候选原 GAP 定义与工具说明：GAP 是任务相关、仍需满足的条件或仍需得到的答案；不是失败日志、原因猜测或行动计划。失败细节放经历，status 只写当前进展。知道失败或解除另一个阻塞，不自动解决原未决条件。沿用 content/source_ids 和 save-before-delete，没有新字段、审核或模型阶段。

SYSTEM 还做必要的默认视图/H1 协议对齐；本轮不再声称 SYSTEM 字节不变。冻结文本与差异见 SYSTEM.txt、PROMPT.diff 和 TOOL_SCHEMA.diff。旧 source-read/source-links-v1 的实际 system/schema/行为检查继续通过；它们的源码身份须在新 checkout 重建，不挪用旧哈希清单。

## 验收与边界

95 项离线检查通过，0 failures/errors/skips。A+B 只选 B 的夹具能从自动目录追到旧 A 原来源；删除、同 ID 替换、预过滤及重开状态不破坏已授予历史入口。另验证独立 sources 的可用性、两轮短链、长 origin partial、grant 写失败，以及未先读原文就显式引用 H 的身份保留与原子失败。跨任务、篡改、未授予、名字冲突、删除尝试、共享预算、长 UTF/CRLF 和大目录分页均有检查。

实际 A04 可见工具调用也以假客户端原样回放：默认读取直接解析为 context；旧 RL3HYG6d 删除后，其 origin_27 入口仍保留在新摘要窗口并可校验读取。这里只证明工程接线，不评价回放生成正文是否正确。详见 TEST_RESULTS.md 和 RECORDED_A04_PROBE.json。

本机没有真实模型、Task、P2 或 eval，没有重跑旧真实组。原六例输入与失败归档保持不变。旧错误不会自动被发现，模型仍可能不读、误读或过度推断；窗口/目录也可能超出本轮预算。本项是本仓的适配补齐，不是 MAGE/SAM 的逐 claim 递归闭包复现，没有复制第三方实现。

复用边界见 REUSE.md；Windows 预检及另行安排的真实 P1 入口见 HANDOFF.md。最终交付 SHA 由回复给出。
