# 文献机制适配：真实实验启动前交接

## 当前交付

研究与实现详见 LITERATURE_TRANSFER_RESEARCH_AND_IMPLEMENTATION_20260913.md；执行计划见 LITERATURE_TRANSFER_PLAN_20260913.md。上轮live-awareness不再作为拟启动主体。本轮提供按需决策视图和自主有限暂停，两开关独立，不是已有效的最终方法。

版本链：

- 回退tag `pre-literature-mechanism-transfer-20260913` → 771bc85。
- dc54c1b：本轮计划及研究边界。
- e0d8ecf：PMA检索原码和许可。
- 4647ebd：LivePlan类型、格式化原码和许可；仅导入路径适配。
- 0ec6638：决策视图桥接及源码对照测试。
- b70e862：有限暂停、现有GA取消/续接适配、并发恢复测试。
- c11679b：隔离入口开关、实际暂停耗时记录、AGENTS研究约束更新。
- 362395f：完整假模型工具循环与研究报告。

每个代码步骤少于600行新增+删除，第三方复制也按步骤拆分。没有提交无关.gitignore变化、密钥或实验旧产物。仓库状态不要求整体清空。

## 验证

- 最终 `test_monitor*.py`、`test_clean_monitor*.py`、`test_task_interruption.py`：**288 passed**。
- `test_isolated_transport.py`、`test_run_ultralong_m12_proofs.py`：**64 passed**。
- 新增源码一致性、同一会话重建→暂停→更新认识→纠偏→读反应→静默、租约到期、显式恢复、实际GA loop暂停前不调用模型、原始中断回归均通过。假模型调用不是效果证据。
- Fyne固定镜像内 `--network none`，仅挂载独立核心及本地Python依赖，模块导入、作者BM25检索、未暂停gate运行通过；容器自动删除，未挂载研究仓库/隐藏测试/旧任务。
- 最终runner `--preflight-only` 通过；GA源码 `d6980f93327c41deb4ab2b48b69a14b771ab050f96330babf605ebfcf14b3fba`，原Fyne任务和镜像身份未改。原题task tree `928e4d98926e9c6038f2538ec960be19fa1fb199bfc11f06e3fe01a7d50259d6`。
- **零模型API，零完整真实任务启动**。实时API可用性未重新确认；不能把静态模型配置解析称连通性通过。

## 唯一拟启动分支

`method_discovery/artifacts/literature_transfer_20260913/fyne_r1_ready_manifest.json` 是最终版本。此前同目录`fyne_r1_manifest.json`是测试追加前的准备文件，不使用；旧live-awareness manifest也不启动。

- ID：`roadmapbench:fyn-2.2.0-roadmap`，method_dev，未改题。
- run：`clean-monitor-fyn-2.2.0-roadmap-literature-transfer-20260913-r1`。
- condition：Clean + active working context + decision_context + hybrid_control；live_awareness及其他旧候选/PMA关闭。
- 任务Claude Opus4.8；监察GPT-5.6-sol high；500turn/10000秒，沿用上一轮任务和模型。
- 无网络任务容器+固定Unix推理通道；native verifier仅结束后评分，无旧轨迹或研究资料挂载。
- 历史同题仅诊断比较。此轮先看组合使用与实际行为，不将收益归于任一单项；后续相同母体关闭各开关才是组件判别，未授权追加对照自动运行。
- 费用无法根据日卡准确预估；没有新增维护模型，但工具调用与暂停可能增加时长和token。上轮89分钟尚未完成，监察成功调用约2092万输入token，不能承诺这次便宜或更快。

## 真实轨迹要回答什么

1. 监察是否用重建视图恢复根任务和之前判断，而不是每次从巨量日志盲找？是否实际打开相关测试验证依据？
2. 是否把纠偏后的理解/动作与原问题联系起来，而非只等待完成声明？
3. 是否只在具体问题会扩散时暂停；能否及时发送/恢复，还是滥用暂停、继续长调查？
4. 任务质量、错误闭合、返工与成本如何变化？暂停等待时长由task侧monitor_pause_wait事件记录；发送/交接由原回执记录；真正理解仍看行为。

停止条件：异常失败、持续无进展或足以判断候选方向的重大结果按既有门禁处理；不在后台自行换规则、换题或连续重跑。现在只等待这条真实启动确认。

## 明确未完成的内容

没有复现Wink/COCO完整运行，未找到其作者可执行代码；没有复制EmbodiedAct未明确许可代码。LivePlan整体规则执行器、PMA完整bank双phase未迁入Clean；只迁入实际需要且已核验的组件。没有获得自动监察达到人工水平、降低成本、混合优于纯并发的证据。相关不确定性进入实验，而非继续无界静态拼装。
