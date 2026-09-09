# 完成协议修复 + U：Fyne R1 正常结束

## 结果

2026-09-09，用户明确授权后运行。run/trial/manifest及源码摘要见同目录LIVE报告。

- 任务执行：2026-09-08 16:18:06.711至17:03:07.129 UTC（CST次日00:18至01:03），45分00.4秒；239轮。
- Harbor trial含准备/评价共45分23.3秒。预算500轮/10000秒；原生task配置7200秒仅作为来源元数据保留，本次integration预算10000秒。
- 正常结束，runner退出0，validation_errors为空，exception_info=null；无人工提前停止。
- 原生评价：6/7阶段通过，reward=0.9090909090909091。这不是把6/7自行换算为分数，而是评价器原始奖励。
- 事后检查docker ps为空。没有追加重跑，没有向任务人工补答案；verifier输出仅在任务结束后读取。

## 本轮真正验证到的协议差异

1. 第一次完成提议被具体纠偏恢复，completion_decision=CONTINUE、reason=INTERRUPTED（16:56:45.931 UTC），没有无理由续跑。
2. 第二次完成提议位于public_events第469行。监察者仍在普通review `82134fe077024ec28627001009bd0df6`中。
3. 1788886917.195调用wait(1)，返回handoff_pending：任务正等待答复，未发任务消息。同一review继续，没有旧版自动CONTINUE。
4. 1788886984.076同一review调用allow_complete，后台绑定completion-2并实际送达；17:03:04.676 UTC任务记录ALLOW_COMPLETE/MONITOR_ALLOWED，随后正常退出。

本次两个完成提议：一次真实纠偏、一次批准。没有TIMEOUT，没有completion_incomplete，没有model_error。300秒迟延路径本次未触发，因此只能引用工程测试，不能宣称真实验证了跨300秒等待。

批准后worker曾启动另一条普通review，随后随运行关闭。这说明尾部仍可能有在途/多余调用；本轮未影响完成，不据此立即改动或夸大零额外成本。

## 未通过的具体原因

原生第7阶段编译失败：`mockDesktopApp`不能赋给`desktop.App`，缺少Driver方法。

任务178轮创建接口时嵌入了整个`fyne.App`，184轮补SetSystemTrayIcon时仍保留嵌入。结果不仅要求题干列出的两个托盘方法，还要求fyne.App的全部方法。

监察者1788886148明确看到了这个嵌入，但只要求补缺少的SetSystemTrayIcon。后续working note保留“embedding fyne.App、interface tests passed”作为完成依据，最后批准。原始接口题干列两方法；原生最小实现不满足附加Driver等要求，因此失败。

初步诊断：监察者检查了“该有的方法是否存在”，没有充分检查“是否额外提高了接口实现门槛”；自写局部测试通过不能证明对所有契约允许的实现兼容。不能把这解释为工程完成队列丢消息，也不应仅把Driver补给隐藏mock。本轮结束后才知道原生失败，不将其回灌到同次部署。

这是一个与错误闭合/代理证据不充分直接相关的反例。进一步改法须验证通用机制，不能在prompt硬写desktop.App不能嵌入fyne.App。

## 保留的能力与限制

- 监察者实际纠正URI路径处理、Bytes遗漏、多参数Set测试错误、不能报错的ErrorPropagation测试、若干编译回归以及未注册的菜单刷新机制。
- 错误状态保留要求这次在约99轮被重新指出，上轮U约300轮才处理；只是轨迹差异，不能归因为本次协议修复。
- 关于具体托盘实现的范围曾扩大，后续1788886699又明确缩小：“接口本身只需两方法，不要为此创造不存在的具体托盘实现”。有自我修订能力，但没有同步纠正多余接口继承。
- 文件位置提醒后发生重复NewAllStrings定义再删除；部分提醒可能引起返工。未逐条裁决全部18条干预的净收益。
- 本轮未出现上一轮长时间多报告收尾循环，但单次运行不能保证以后不会再出现。
- U read_with_sources调用0次；file_write1次，file_read5次，code_run154次，wait27次，intervene18次，allow_complete1次。不能把本轮正常收敛归功于U来源恢复。

## 用量

provider已归档统计，不含缺失usage的在途请求，不是中转最终账单：

|对象|usage记录|输入|输出|缓存口径|
|---|---:|---:|---:|---|
|监察者|130|16,659,018|32,471|输入包含cached_tokens=7,711,360，不重复相加|
|任务Agent|235|333,041|139,158|另列cache_creation=602,170、cache_read=4,387,163|

任务分列输入合计5,322,374。美元未估算。上轮105分钟/419轮、监察输入2400万；本轮45分钟/239轮、1666万输入。时长和累计输入下降是观察事实，不是严格降本增益：上一轮人为停止、轨迹不同，缺少重复和等预算对照。

## 本轮文件与下一步

运行前只给`method_discovery/prepare_grounded_u_run.py`增加run-suffix/output参数，拒绝覆盖旧manifest保持；没有修改监察策略或任务代码。运行记录、结果和CURRENT检查点已更新。

原始产物根目录：`long_context_bench/output/clean_monitor_real_tasks/fyn-2.2.0-roadmap/jobs/clean-monitor-fyn-2.2.0-roadmap-phase1-completion-semantics-u-20260909-r1/fyn-2.2.0-roadmap__v3BLdf2/`。
关键文件：result.json、verifier/test-stdout.txt、agent/research_events.jsonl、agent/monitor/runtime_receipts.jsonl、agent/monitor/monitor_private/audit/dialogue.jsonl及provider_usage.jsonl。

建议把本次完成协议修复保留为下一阶段工程起点，再审计接口反例以及哪些原有正确纠偏值得保留，独立设计R。不是整套方法冻结，不是U晋级，不自动运行下一题或修改隐藏测试。
