# R9 专家审计：工程修复阶段

## 范围与结论

仅修复 typed receipt 的 review 边界分类及公开审阅包的嵌套提示导出。
不修改模型提示、PMA 作者代码、记忆表示、控制顺序、预算或当前语义续接路径。
根完成判断候选和 Judgment Record 尚未实现；未启动真实任务。

## 修改

- `monitor_agent_core/provider.py`：accepted 不再单独足以表示 review 结束。
  带类型回执须为已知控制动作；maintenance_complete 不构成 review 边界。
  无类型旧档案继续按已确认控制调用识别。工具调用/返回配对边界不变。
- `method_discovery/scripts/build_collaboration_bundle.py`：PMA cycle result
  只导出 operations、should_inject、context_for_action，其他字段只留 JSON
  UTF-8 序列化内容的 SHA-256。决策与工具观察仍通过原事件保留。
  当前源码 commit 动态读取；历史 R8/R9 源码身份保持原值。
- 增加维护 wait/allow_complete/intervene 交接、后续真实 wait、旧回执、
  工具配对和 R8/R9 导出白名单检查。

## 验证

在 GenericAgent-main 工作目录运行：

`D:\python\envs\ga_bench\python.exe -m pytest tests/test_monitor_provider.py tests/test_monitor_pma_fused.py ../method_discovery/test_collaboration_export.py -q`

79 passed。首次从根目录启动缺少 monitor_agent_core 导入路径，纠正执行目录后通过。
git diff --check 通过。没有真实 API 调用。

## 发布边界

本地完整归档不变；审阅副本可由脚本重新生成。过滤修复不是隐藏答案泄露
修复：发现的是完整公开题干/重复提示超出预定发布范围，不是在线访问 verifier。
仍保留核验所需的公开要求摘录和代码观察，不声称消除了所有任务语义。
本轮不推送远端、不改变仓库可见性、不重写历史；旧远端提交仍含先前发布内容。

## 下一阶段（待确认）

实现仅有效根完成提议下的判断合同候选，并与普通复核/公共检查提醒区分。
沿用原 bank、工具与预算；正确处理审议中提议出现、撤销与更换。
工程验证不能证明方法有效；真实启动仍需独立确认。
