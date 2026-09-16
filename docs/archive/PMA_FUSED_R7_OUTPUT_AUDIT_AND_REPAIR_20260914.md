# R7 输出语义与退出控制审计、修订

## 原始证据与裁决

运行：clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r7。
trial：fyn-2.2.0-roadmap__fxqNfv7。
根目录：long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-pma-two-phase-20260913-r7/fyn-2.2.0-roadmap__fxqNfv7/。
D 指 agent/monitor/monitor_private/audit/dialogue.jsonl 的物理行号。

Agent execution 2026-09-13 16:31:06.406393Z—16:40:43.542613Z，约9分37秒。
初始化review65.69秒，以wait/follow/3结束。后两review167.95秒、297.69秒均调用预算耗尽；
runtime_receipts记录两次 `Fused review exhausted its shared model-call budget`。
完成提议被记录completion_incomplete(reason=review_failed)，不是10000秒耗尽，也不能给方法记0分。
任务自身已有ROUND END，外层仍因缺有效监察完成裁决而判无效；这两个完成口径不同。

### 断点一：两个输出协议同时存在

D57、124、232是comparison入口。D68、157、254、289输出no_intervention。
旧text_result却返回“No input sent. Continue investigating or use wait”，继续调用模型。
第一次模型之后调用wait成功退出；后续则继续读写、更新status，直到预算耗尽。
因此不是接口完全不可用，而是PMA的完整决定被本地解释为非终止提示，要求模型再作一次控制决定。
不能仅靠这些行认定所有重复调查都由协议导致，但该语义冲突是确定的。

### 断点二：同会话的阶段角色和真实动作混淆

D197进入maintenance，D222输出context_for_action，指出testApp.Metadata缺失。
此时尚未进入判断阶段，旧处理只提示继续维护，没有发送；全程无pma_direct_intervention记录。
D231才结束维护，D232进入判断。D281工具回执中的status已写“intervention delivered”。
因此是模型在记忆中把未发送的文本建议当作已执行动作，随后继续追踪不存在的采纳。
第一阶段D109也曾误写no_intervention，说明同一History有连续性但不保证阶段职责正确。

## 第二阶段选择谁为主体

选择监察者基线控制工具为主体，理由是它能直接表达异步纠偏、持续观察、自主等待节奏和根完成。
若以PMA XML为主，则必须额外规定无提醒后默认等待多久、是否继续跟踪、如何处理根完成；
这会把监察者的自主决定挤到第二套隐含协议中。本次不增加这种默认控制。

保留作者MemoryAgent.process、两阶段输入构造和bank操作；在调用前替换第二阶段输出说明。
作者vendor源码未改。不能继续声称第二阶段输出格式原样保留——这是明确且有原因的适配边界。

## 改动

- pma_fused.py：decision_prompts保留作者比较内容，将XML输出区和尾部决定要求统一到工具协议。
- phase2提供intervene、wait、allow_complete及调查/bank工具；不再隐藏intervene。
- intervene复用现有dispatch，取得真实回执；成功才计入已提交列表，记录pma_direct_intervention。
- wait一次即结束，不需XML前言或后续模型批准；是否pending仍由既有completion检查决定。
- 旧XML/其他纯文本不偷偷转换成执行：返回明确未操作及正确工具说明，不诱导额外调查。
- phase1误写纠偏/静默时明确input_sent=false；maintenance_complete仍仅切换阶段。
- 作者process仍解析适配器投影结果，但审计标明author_result_is_control_projection；实际干预由工具与回执记录裁定。
- 未提高调用/时间预算，未改任务调度、信息隔离、模型或原生事后评价。

## 验证

最终15个相关测试文件：134 passed, 19 skipped，11.61秒。19项为上一阶段已标记的历史候选契约，本轮未新增skip。
新增覆盖：第二阶段输入不再教XML控制；wait单次立即返回；维护阶段文本建议明确未发送；旧文本不会形成第二执行协议；pending时wait不变成批准；同一判断阶段两次真实纠偏、期间更新bank、最后wait。
同时保留provider真实序列化、工具回执、usage阶段标记、跨唤醒记忆、故障、宿主、follow及完成生命周期检查。
第一轮新增测试仅因测试读取UTF8日志使用Windows默认GBK失败，显式UTF8后通过；不涉及生产协议放宽。
代码差异110新增/17删除，小于600行；不含文档。本轮无API调用、无新真实任务。

## 限制与下一步

消除了可确定的双协议冲突，不等于解决浅层核验或错误记忆。模型仍可能拒不调用工具或反复调查，原调用预算继续显式保护。
第一阶段到第二阶段的结束标记仍需真实确认其使用情况，不自动把语义文本分类成终止。
新真实运行应同Fyne、同模型预算，用新run-id；须用户单独确认。
