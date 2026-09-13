# PMA maintenance R1 live

用户明确批准本次真实启动。源码commit 73d0d4d。
run: clean-monitor-fyn-2.2.0-roadmap-pma-memory-20260913-r1
trial: fyn-2.2.0-roadmap__mYXZWg6
runner session: 16199
manifest: method_discovery/artifacts/pma_memory_20260913/fyne_r1_manifest.json
两方独立Claude Opus4.8，500turn/10000秒，无网络Unix推理隔离，事后native评价。

启动前第一次预检被源码摘要阻止，未创建trial或调用模型。manifest早于最终补测；
工作区生产代码与提交一致，刷新未执行manifest至
1e9b90fa4bec65fd476c5c8c70154caa2fce3b90e096cf39229d62456b4131d3后预检通过。
17:36容器就绪；17:38确认两方响应，首次pma_memory.json已生成，任务开始执行。
后续按10分钟轮询；启动成功不等于方法效果成立。

## 最终结果

17:36:20–18:07:23（31分02.74秒），83轮，runner正常退出0；validation_errors为空，
native事后2/7，reward0.18181818181818182，无exception_info；容器自动清理。
与tools-repair-r2的25分32秒/52轮/4项0.4545相比，本次更慢、分数更低；单次比较不证明因果退化。
6次纠偏，5处任务工具Stopped；本轮未注入人工纠偏、未修改运行代码。

通过5 Toolbar、7 Desktop。
1/4以及6的container部分因原有dummyApp未补Metadata导致测试包编译失败；
2因themedApp未补Metadata导致测试包编译失败；3缺StringToStringWithFormat。
不能把被编译失败挡住的主题/菜单行为直接判成每项语义都错。
6的widget、validation子测试通过，尤其SetMinRowsVisible/默认行数通过，是局部积极结果，
但不能据此宣称PMA独立增益（本次监察者明确提醒MinSize关联，上一分支实现不同）。

## 维护链和关键反例

19次维护全部status=updated，累计464.36秒（不是净新增wall time的因果估计）。
每次bank维护已进入后续正常请求，原持续调查和即时纠偏仍运行，未见本次链路协议失败。
初始化保留12条知识，包含所有App实现须更新，以及StringToStringWithFormat的明确要求。
结束时这两条仍在pma_memory.json中；因此本次重要缺陷不是要求没有被存下来。
但维护status逐步写为ALL SEVEN TARGETS IMPLEMENTED，最终监察输出列出七项和六次纠偏均完成，
以cursor160 BUILD SUCCESS exit0放行，completion receipt cursor161 allow。
说明“记忆保存并提供给模型”与“按要求逐项检验完成推断”是两件事。
该候选没有消除此前识别的‘修复本轮清单=>全部功能成立’推断；库甚至同时保留要求与过强状态。
这只是本次真实反例，不能据此否定PMA所有机制或断言必须固定逐项checker。

## 用量

全部监察105条request_usage：input720355/output54973/cache_read1979357/cache_creation3760442。
其中维护19条：input491416/output19686/cache_read920/cache_creation14565。
维护输入主要不是缓存命中；该成本必须计入，不能把维护当免费。
维护用量已经包含在总量内，不得再累加。美元账单及任务侧用量尚未合并，原遥测保留。

## 停止点

候选已完成一次真实验证，但未晋级为接受版本。不继续运行或加新机制。
下一步建议审计为何知识仍可见却未进入完成判定，并区分维护输入适配和判断策略的影响。
启动前摘要失配教训：最终测试完成后再生成manifest，不能在补测前冻结源码摘要。
