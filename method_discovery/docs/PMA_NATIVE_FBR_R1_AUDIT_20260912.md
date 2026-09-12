# 原生 PMA FBR R1：完成后审计

## 裁决

本次是完整运行结束、原生评分0/7，不是API中断、OOM、50轮耗尽或7200秒超时。但存在明确的 **Terminus2登录终端与Roadmap镜像PATH不匹配**，必须标记为环境混杂，不能拿0分直接裁决PMA方法优劣。

同时，在线原始证据独立证明了：要求被正确保存以后，PMA仍生成了错误解释、把未完成验证的代码标为完成，并在提醒未被执行后关闭状态。这些是可用于候选生成的行为证据，不是方法优越性或长程遗忘的因果证明。

本轮只审计、增加只读诊断脚本和报告；未修改PMA/GA执行源码、未重跑模型、未改旧分数。

## 1. 运行事实与统计

控制器启动2026-09-12 16:07:03，退出16:37:16，约30分13秒；exit0，非OOM。task47轮，memory46次触发/92次调用、78个成功操作、14次提醒、32次no-op。139次逻辑调用全部返回；没有记录到memory操作异常；task summarization_count=0。

|角色|调用|输入token|输出token|缓存token（勿重复加到输入）|客户端估算美元|累计调用等待|
|---|---:|---:|---:|---:|---:|---:|
|task|47|1,619,199|31,262|1,501,656|1.35314205|740.84秒|
|memory|92|1,275,320|11,032|见审计JSON|7.9989665|1007.91秒|

合计约$9.35只是Harbor/LiteLLM估算，不是中转账单。记忆侧约占85.5%估算费用、55.6%控制器总墙钟时间。保留了原版同步机制，此处只能说明本次开销构成，不能据此计算我们异步方法的收益。内部未返回的重试用量仍可能缺失。

原始根目录：`bench_runtime/pma_linux_controller/native_fbr_20260912_r1/work/trial/`。以下episode采用作者目录的**零基编号**；memory Step采用trajectory_memory.json的**一基step_id**，不得混用。

## 2. 环境因素：不是没有Go，而是实际任务终端找不到Go

- episode-15真实执行了 `go build middleware/proxy/proxy.go 2>&1 | head -20`。
- 后续公开终端输出为 `bash: go: command not found`，不是通过编译。
- episode-16中Agent明确说“Go is not in the PATH but that's fine”，转为浏览代码继续实现。
- PMA Step17的phase1、phase2输入都包含这条错误；它仍把Target2标记为COMPLETED，没有保留验证受阻状态。
- 全47轮显式工具命令中，只找到这一次go build；没有go test、go vet或gofmt。此结论同时经过响应命令扫描和末段原始轨迹核对，不靠关键词搜到一次成功就当完整验证。

只读复核使用同一固定依赖镜像，断网、无模型调用：

```
DIRECT_PATH=/go/bin:/usr/local/go/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
command -v go -> /usr/local/go/bin/go
go version -> go1.22.12 linux/amd64
LOGIN_PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
command -v go -> exit1
/usr/local/go/bin/go version -> go1.22.12 linux/amd64
```

作者 `external/harbor/src/harbor/agents/terminus_2/tmux_session.py` 的 `_tmux_start_session` 明确启动 `bash --login`；镜像 `/etc/profile:5` 重置PATH，删除/usr/local/go/bin。评分脚本直接执行go test，继承非登录环境，因此可以找到Go并报告编译错误。

**责任边界**：这是原生终端迁移到本地Roadmap镜像时我们没有验全的兼容问题，不是PMA论文算法的缺陷。上一阶段只验证了终端/录像可启动和合成文件操作，没在实际Agent shell里验Go工具链；预检不足。无需联网安装Go，二进制和模块缓存本来就在镜像中。正确补救方向是保持原终端交互并让登录shell保留镜像声明的工具路径，再验证实际终端中的Go调用；本轮未实施。

## 3. 致命错误的时间线：从代码可见到无依据闭合

|锚点|公开事实|PMA处理|任务后续|
|---|---|---|---|
|episode-41 → memory Step43|插入 `mime = mime.TypeByExtension(extension)`；同一函数已有 `var mime string`|完整冲突代码同时进入phase1/phase2；未指出变量遮蔽，却判断“fallback logic structure itself is correct”，提醒缩进/重复return|episode-42只改缩进、删除重复return|
|memory Step44 → episode-43|代码仍存在同名遮蔽|提醒对齐return，并明确建议之后运行go build|只执行sed和sed读取，未编译|
|memory Step45|只有上一步格式修改和代码输出，没有编译成功证据|写入“function compiles properly. ALL 7 TARGETS NOW COMPLETE.”，不提醒|episode-44用grep/sed列出各功能|
|memory Step46|仍无实际验证；Target7片段仍含同名冲突|写“Final verification confirmed all implementations are correct”，不提醒|episode-45提出完成，episode-46再次确认，最后只echo成功声明|
|事后评分|utils/http.go:9导入未使用；:30字符串没有TypeByExtension方法|仅结束后可见，未泄漏在线|7组测试均无法编译，0/7|

**两点区分**：PMA没有在线看到“编译器报出mime遮蔽”却装作通过；它在线看到了足以诊断的代码以及没有编译成功证据，仍写出“编译正常”。这是推理判断错误与证据不足闭合，不是编译日志被接线丢掉。

所有Step43–46的phase1输入均含`var mime string`和`mime = mime.TypeByExtension`；不是因为滑动窗口把这段关键代码完全剪掉。全程无任务压缩，当前证据也不能指控压缩机制导致此错误。

## 4. CORS：保留要求不等于保持原来的判定标准

- Step1正确存储Target4：存在通配符时返回字面`*`，不回显origin；这条原知识在最终bank中仍然存在。
- Step20在知识中新增错误诊断：认为已有break之后的subdomain匹配还能覆盖结果，并将预期缩成“non-credentials case”。这段错误诊断随后被提醒给任务Agent。
- episode-19/20的任务推理注意到了当前break会退出循环，但又引入一般CORS惯例作为本任务例外。
- Step22继续重复错误解释，甚至说break只退出条件块。与此同时它自己的status又承认原代码表面逻辑正确；知识与状态没有形成一致修订。
- episode-21改写条件形式，但保留credentials时回显origin的逻辑；Step24和最终bank把这项标为完成。

这是两种不同问题：**Go控制流解释错误**，以及**外部领域惯例覆盖本次明确要求**。不需要隐藏checker就能发现要求与实现仍冲突；但本次评分全部先被编译阻断，不能把CORS语义问题伪称为已独立观察到一项评分失败。

最终bank保留原要求和新“已完成”的描述并存，说明“知识没丢”与“执行标准没失真”不是一回事。这与既定unsupported closure/completion-evidence drift主线一致；不据一题宣布新颖性或收敛机制。

## 5. 提醒是否真的发出、有什么作用

逐条核对全部14次 should_inject=true记录，在对应episode debug.json的**当前user消息**中都能找到完整提醒原文：14/14送达，无投递丢失。

注意作者prompt.txt是在注入前保存，不能用其没有memory_context误判“没注入”。应检查实际调用messages；原版_memory_aware_chat在调用之前才追加提醒。这是审计工具口径问题，未改源代码。

有价值的行为：
- Step16指出缺time导入，随后补上；但Agent此前已经计划补入，不能证明该提醒独立导致修复。
- Step25指出ContextKey改为interface{}后默认值检查需要处理nil；随后确有相关修改。
- Step32–38持续跟踪session编辑破坏、重复代码和工具不可用，促使/伴随Agent恢复文件并换编辑方式。存在后续行为吻合，但没有无提醒反事实，不能量化净增益。

有问题的行为：
- 将“缩进错误会导致Go编译失败”作为提醒依据，这不正确；Go不是缩进决定代码块的语言。本次真正的变量遮蔽反而没被指出。
- 认为局部代码看起来修好后即可完成，未核实最后一次“运行go build”的建议是否执行。
- session部分消耗许多轮处理交互式终端的多行/制表符编辑破坏；Agent早在episode-10就报告tab completion干扰heredoc。它属于工具使用/任务框架适配因素，不能全算成长程遗忘，也不能通过事后给PMA加入我们的编辑工具来冒充原版。

作者完成提议后会要求第二次确认，但memory调度在该分支continue，确认之间没有新memory review。这是原代码行为，不是我们的接线漏调用；且Step45在首次完成提议之前已经错误闭合，因此不能把失败全归因于“缺最后一次审查”。

## 6. 哪些结论能下，哪些不能

可以确认：原核心循环和提醒投递真实运行了；PATH兼容缺陷存在；PMA正确保存了多项任务要求并发出具体建议；也确实出现错误解释、检查建议未落实和无证据完成状态。

不能确认：修好PATH就能得到多少分；PMA相对无记忆是否更好；我们的方法是否更好；失败是否由长程长度而非基础推理能力造成；任何新组件已经有独立收益。47轮、单题、异模型/框架结果不支持这些结论。

另外当前native trial结束后删除了任务容器，没有单独归档完整最终工作区/patch。终端录像、逐轮响应、观察、记忆和评分还在，可以查上述直接证据；不能假称已保存完整可重新评分的最终代码，或无损执行“只修一个变量”的反事实。下一运行准备应补结束前工作区归档，这是证据保存问题，不是修改PMA策略。

## 7. 建议的下一步（未实施）

先修**登录shell工具链可达性与终局工作区归档**，在真实终端做零API工程验收。保持PMA算法、50轮、模型与隔离不变，再在同题运行干净原生PMA；之后配对无PMA的原生Terminus2。原有R1结果完整保留并标环境混杂，不删除、不改成成功。

方法研究先保留一个候选方向：让“公开要求、已经验证的事实、仍待执行的核验”不能因一轮局部代码浏览而被合并成成功；用普通可执行验证取得新证据，而不是一直重述旧判断。这只是待比较的机制目标，不能立即往PMA基线加自己的控制器，也不急于重新堆叠全部旧候选。

## 复查入口

- `audit_pma_native_run.py --trial <trial> --output <new-json>`：生成计量、全部送达回执、显式验证命令和关键原始材料SHA；不会调用模型或改原始轨迹。
- `diagnostics/pma_fbr_path_audit.sh`：同镜像只读shell可达性诊断。
- `PMA_NATIVE_FBR_R1_AUDIT_DATA_20260912.json`：本轮生成统计。
- 验收：47task/92memory与native_result/原bank摘要一致；14/14当前消息回执；只有episode15一次编译尝试，与原始输出相符；两种shell诊断复现PATH差异。

本轮不清理运行残留服务或容器、不改执行源码；当前审计请求不自动授权下一条真实实验。
