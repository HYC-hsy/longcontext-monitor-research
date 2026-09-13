# PMA maintenance R1：机制还是适配问题

## 审计范围

只读审计，无API、无运行代码改动。运行与路径见PMA_MEMORY_R1_LIVE_20260913.md。
核对19次维护完整操作与状态演变、全部工具调用清单、公开模型判断、关键工具返回、
最终bank、事后verifier，以及pma_memory/agent/provider源码实际消费路径。
下文L指该run的agent/monitor/monitor_private/audit/dialogue.jsonl一基行号。
不是复现效果归因实验；不能用单次分数变化识别维护机制的净因果效应。

## 裁决

当前接法未证明有益，不应晋级。不是机械接线未执行；也不足以否定PMA记忆机制本身。
证据支持更具体的诊断：知识保持确实发生，但维护目标仍偏向记录事实和进展，
没有形成对‘完成判断依据是否覆盖原要求’的持续维护；本地输入适配又重复输入了双方完成自述。
本轮不能称‘已经有效，只需微调’，下一步需要改变维护与判断的关系而非润色COMPLETE措辞。

## 已确认接线与局部能力

19次维护成功；操作合计save_knowledge12、save_procedural9、update_status19、delete2。
知识12条全部在初始化产生，后续未增加或修订知识条目；11次调用只有update_status。
最终12知识+7经验，未达到作者50条检索阈值；不存在BM25漏召回这些要求的解释。
_active_working_context在每次正常_request临时加入bank，维护调用禁用该hook并使用作者bank prompt，
结束恢复原history与hook。没有history压缩记录。原始网络请求完整bank没有单独逐次归档，
因此‘正常请求接入bank’依据实际执行代码、维护成功和provider请求记录，而非声称拿到每次wire dump。

原要求ALL existing App implementations与StringToStringWithFormat从初始一直保留到最终。
L379维护写ALL 7 TARGETS COMPLETE，L390监察仍发现SystemTrayApp命名错误并纠偏；
L400维护将该问题记回状态。说明新bank不构成硬许可，后续可纠正它，但未证明独立收益。
L327指出SetMinRowsVisible未影响MinSize，后续修改与事后对应子测试通过。
原任务本来就有该要求，不能单独归因于bank。

## 三个直接问题

### 1. 记住全称要求，检查时却主动缩小范围

L171/177/183明确说检查所有App实现；L184实际执行：
`grep -r "func.*NewWindow.*Window" /app --include="*.go" | grep -v "test" | grep -v "Binary" | head -20`。
L185只返回fyneApp。测试文件被模型命令过滤，并非file_read/code_run工具权限限制。
只检查test/testapp.go不等于检查所有测试中的App实现。
最终dummyApp与themedApp缺Metadata阻断多个phase测试编译。
因此这里更具体地暴露‘取证范围与原要求不一致’，不是工具不可用或事实消失。

### 2. 阶段跳转被当作阶段完成，未调查区域没有留作未决

L189–207监察追查Target2时，任务已经经过Target3、4；L213转而纠正Target5返回类型。
完整工具清单无针对StringToStringWithFormat或data/binding/sprintf.go的主动文件/搜索检查；
review_context可能展示部分绑定轨迹，不能夸大为完全没有任何相关信息。
L229首次维护写‘Targets1–5 successfully completed’，输入包含任务自己的完成checkpoint与
刚处理Toolbar的局部轨迹，没有对应所有前五项的完成验证。
最终knowledge仍列StringToStringWithFormat，完成清单却只列NewSprintf，native报函数未定义。
这显示记忆内要求与进度结论能同时矛盾，而没有进入调查或重开。

### 3. 局部纠偏记录被反复用于推导全局完成

L375‘All Targets1–6 complete’；L396‘Once rename...all7 fully compliant’；
L417/426反复‘all corrections addressed’并等待build；L570最终以BUILD SUCCESS和七项实现清单放行。
19次维护主要更新进度，经验保存的是‘哪个错误已修好’，并未建立尚未验证要求的判断依据。
这不是PMA存储坏了，而是当前维护对象仍是进展/修复故事，不是完成结论的支持范围。

## 与作者链条的适配差异

作者phase1负责信息保留，不承诺行为证明；phase2明确要求比较bank与近期行为的遗漏/矛盾。
我们复用phase1操作和格式，但没有运行作者phase2，而用已有持续监察者代替。
当前接法让bank‘被看见’，却没有通过实验确认它承担了作者phase2那种明确比较职责。
不能据这次结果判定完整PMA两阶段无效，也不能把新增bank称已完整移植PMA判断机制。

输入也不是作者原始recent8任务步骤：使用8条synopsis（可能是前后边界，不是8个完整回合）
加至多80000字符的监察历史。L229维护输入包含层层JSON转义的review_context结果、裁剪的
工具轨迹、任务checkpoint、自身判断。后期prompt约9–10万字符，完成自述可能被再次概括为事实。
它们确实被输入且状态出现过强完成结论；但‘正反馈造成退化’仍是待消融的因果假设。
同一review内不维护，下一wake才维护；并未消除长期局部追踪中的调查范围遗失。

## 成本与评价解释

19次维护耗时464.36秒；约49.1万新输入token、1.97万输出，缓存命中低。
额外调用成本是事实，但总美元成本不宜仅凭input字段比较，因为原分支缓存创建更多；
本轮全部token字段相加也不等于美元账单。31分03秒相对25分32秒不能全归因于维护。
2/7比4/7低，但多个phase由同一App测试实现遗漏连带阻断，不等于五种独立机制失败。
Entry子项通过说明局部正例与整体低分并存。

## 建议与停止点

保留作者bank实现及归档，不把本候选晋级。后续若继续，应先优化‘消费职责’与输入来源，
而不是加更多记忆分类、调大窗口、强制更多次检查或把COMPLETE换个词。
核心判别：明确要求存在时，监察者能否发现自己的调查范围/推断范围不足，并保留未决项。
优先核对作者第二阶段比较链如何适配，既不丢持续工具能力，也不默默增加三层模型调用。
此处仅建议，未实现、未重跑；完整原PMA与该适配不能混作同一条件。
