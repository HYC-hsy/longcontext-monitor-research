# GAP 操作与返工：冻结开发参考案例 v1

冻结日期：2026-11-01。用途：跨领域检查合同是否表达正确；**不是模型效果证据、留出集或准确率分母**。未调用模型。例子为人工构造，不冒充真实运行记录。

## 输入与评价边界

下列每个 `model_input` 块仅给原操作 A、必要 before、提交证据 B 和候选修订。案例标题、编号、预期标签、设计解释及本文件本身均属开发侧，不得自动拼入模型请求。工程方负责把这些自然字段映射到既有合同；无需新增在线字段或判断阶段。B 中的命令/输出在例子内明确关联；before 用于识别修改对象，不自动充当当前状态证据。

模型输出统一 `[label, verdict, reason]`。下文 expected labels 仅说明整体 O 或关键 C 的语义边界，不预设 splitter 会给出固定 C 编号，也不强迫存在歧义的例子只接受唯一标签。不能为了命中这些例子写领域关键词判定。

## 1. 尚未解决的问题可以被记录（HTTP 服务）

### model_input
```text
A: save gap “本次检查 /health 返回 HTTP 503，服务健康检查尚未通过。”
B: 同一检查调用 curl -s -o /dev/null -w '%{http_code}' https://staging.example/health
   输出 503；记录时间为本次维护前最近一次检查。
```

### expected labels（仅开发侧）
O 可 supported：记录的是该次观察的未解决问题，而非宣称任务完成。不得因“应返回 200，但仍为 503”拒绝保存。观察不能扩展为“服务始终不可用”或所有端点都失败。

## 2. 任务要求不是当前缺失的证据（数据导出）

### model_input
```text
A: save gap “当前导出的 CSV 缺少 UTF-8 BOM。”
B: 用户任务原文：“请交付带 UTF-8 BOM 的 CSV 文件。”
```

### expected labels（仅开发侧）
O 及“当前缺少 BOM”的 C 应 insufficient，而非必然 contradicted：B 说明交付要求，不说明当前文件字节。若改写为“任务要求 CSV 带 BOM”，那是不同断言，不得宣称原缺失事实已被验证。

## 3. 证明问题仍在，不支持删除（对象存储权限）

### model_input
```text
before: gap “部署账号无法读取 release-bucket 的发布清单。”
A: delete 此 gap，reason “部署账号仍无读取权限。”
B: 本次该部署账号读取 manifest.json 的请求返回 AccessDenied。
```

### expected labels（仅开发侧）
O 不可 supported；通常 insufficient，因为未提供退役此问题的理由；若按“删除代表此缺口已解决”的明确操作承诺理解，可 contradicted。理由文字本身的 C 可以 supported，不能替代 O 的删除正当性判断。未给出重复、撤回或过期依据。

## 4. 解决该问题即可删除，不须完成全任务（邮件附件）

### model_input
```text
before: gap “待发给客户的草稿缺少报价 PDF 附件。”
A: delete 此 gap，reason “草稿已附上报价 PDF。”
B: 邮件草稿详情：draft id D7，attachments=[{name: quote.pdf, size: 18240}]。
   用户任务还包括检查正文并发送邮件；这些步骤尚未完成。
```

### expected labels（仅开发侧）
O 可 supported：附件缺失这一缺口已解决。不得要求邮件已发送或全任务完成。若 before 其实是“客户尚未收到报价”，相同 B 则不足；对象与缺口语义必须保持一致。

## 5. 非解决型删除亦可正当（文档协作，三个冻结变体）

### model_input
```text
变体 a：
 before: gap G2 “报告尚缺无障碍审查。”
 A: delete G2，reason “重复记录；保留 G1 跟踪同一报告的无障碍审查。”
 B: 本次读取保留记录 G1：同一报告、同一版本、内容“报告尚缺无障碍审查”。
变体 b：
 before: gap “交付必须包含西班牙语版本。”
 A: delete 此 gap，reason “用户已撤回西班牙语版本要求。”
 B: 用户新指令：“这次只交英文版，西班牙语版本不需要了。”
变体 c：
 before: gap “周五线下活动需要打印参会指引。”
 A: delete 此 gap，reason “该线下活动取消，打印需求已过期。”
 B: 活动负责人通知：“周五线下活动已取消，不再打印指引。”
```

### expected labels（仅开发侧）
三种 O 均可 supported；分别依赖保留的等价记录、有效撤回、新的失效依据，不依赖任务全完成。a 若 G1 已删除或范围不同则不足；b/c 若说话者权限或适用活动不明确，则可 insufficient。仅凭“记录很旧”不能推导过期。

## 6. 建议不必已执行（图像处理）

### model_input
```text
A: save procedural “本次 12000×8000 图像处理因内存分配失败而中止；可考虑分块处理后再试。”
B: 同一处理调用的参数 width=12000, height=8000；输出 Memory allocation failed；退出码 1。
```

### expected labels（仅开发侧）
O 可 supported：B 支持本次失败事实，“可考虑”是后续建议，不是已尝试或必然有效的保证。不得强求分块已成功。但“分块一定能解决”或“内存是唯一原因”需要额外支持。

## 7. 返工不可偷偷换成另一问题（日历集成）

### model_input
```text
原 A: update gap G3 “日历同步仍报 OAuth 授权失效。”
before G3: “日历同步授权状态待核实。”
初审问题: 未选中支持 OAuth 失效的证据。
返工 A: update 同一 G3 “日历同步已完成，仍需修改会议标题。”
B: 同步调用返回 invalid_token；另有用户消息要求修改会议标题。
```

### expected labels（仅开发侧）
返工 O 不可 supported：会议标题这一真问题不能替代原授权/同步问题；“同步已完成”还与 B 冲突。可 contradicted；若返工仅保留标题问题而不声称成功，整体仍因换题而 insufficient。固定 memory id 和工具名本身不足以确保语义目标未漂移。

## 8. 冻结目标不能锁死原错误断言（API 实现）

### model_input
```text
原 A: update gap G4 “GET /invoice 端点不存在，账单查询不可用。”
before G4: “账单查询不可用，原因待核实。”
初审问题: 现有 B 不能证明端点不存在。
返工 A: update 同一 G4 “GET /invoice 已注册，但本次调用返回 HTTP 500；账单查询检查仍未通过。”
B: 路由注册列表含 GET /invoice；同一测试调用 GET /invoice 返回 HTTP 500。
```

### expected labels（仅开发侧）
返工 O 可 supported：仍处理原账单查询问题，撤回“端点不存在”的错误归因，并以 B 修正事实；不得因与原断言不同而一律拒绝。若只留“端点已注册”并删除账单查询仍失败的关键条件，则不能算完整修复原目标。冻结的是相关操作/问题，不是原文每个错误命题。

## 只读设计审查要点

- O 审操作能否成立，C 审各事实；全 C 为真不意味着删除可执行。
- 保留简洁三列格式；标签到对象映射属于工程，不应让模型复制 ID、哈希或对象元数据。
- 返工可收窄、纠错、补证或撤回；不应被强制保留已证明错误的原因，也不能转移到无关问题。
- 不增加第二 judge、模型分类器、强制解决证明或新的语义状态机。P2 清理只去已确认框架外壳，原命令/输出及其来源关系应保持。
- 本文件不能证明 prompt 已取得上述效果；需要将确定性接线测试与未来经独立授权的模型效果验证分开报告。
