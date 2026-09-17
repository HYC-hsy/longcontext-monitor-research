# Root-decision Fyne R1：专家审阅入口

执行代码 eb6d7cd；本次为异常终止，不是完成的效果实验。
任务执行约 804.70 秒（13分25秒），verifier 未运行，没有 reward。
不能把汇总器 error trial 的 mean=0 当作原生任务零分。

根判断候选已加载，但所有已记录选择都是 ordinary，root 触发 0 次。
第八次 review 在 comparison 首次请求准备时压缩续接失败：
HistoryCapacityError('Monitor continuation failed; history preserved: ValueError')。
维护阶段已提出 wait，未执行；判断阶段尚未得到正常响应。
续接请求 HTTP 200，usage 已返回；没有成功写出 continuation note。
具体 ValueError 需进一步诊断，当前不认定是网络故障或候选无效。
运行时记录 monitor unavailable，最终停止并归档工作区，未进行 native verifier。

## 后续简单对照（尚未运行）

已准备同一 Fyne 任务、同模型/源码/预算的公共构建和相关测试提醒对照。
只改变根判断指导，保留 PMA 两阶段、bank、工具、History 和调度。
不会看过候选结果后调整对照来追求预定结论。先排查本次工程故障，若必须修复
共享底座，两组都使用相同修复；本次不能充当有效的候选效果结果。
真实启动仍另行确认。

## 本包内容和限制

`evidence/root_decision_fyne_r1/`：筛选监察决策、调用用量、review、压缩元数据、
运行时失败回执、公开任务命令与最终 bank、启动 manifest。
不存在 reward/成功 continuation，因此不创建虚构空文件或结果。
原始完整 history、题干与失败工作区仍留本地；不上传隐藏测试、凭据或完整题干。
旧 R8/R9 嵌套 phase 提示已从当前导出移除，但正常提交不会删除旧 Git 历史。

希望专家区分：候选没有被实际触发；普通监察的既有行为问题；续接工程故障。
审计进行中，后续补充精确因果边界和关键轨迹锚点。
