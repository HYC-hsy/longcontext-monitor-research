# 监察者独立性补齐：内核与宿主适配边界

## 本轮授权

用户要求修复审计发现的耦合，收回适配层，并确认无参数工具 `_noargs` 的影响。
只做工程独立化和确定性验证，不启动完整真实任务、不改变研究问题或控制机制。

## 责任分离

1. core.configuration 只接受明确配置文件参数或 MONITOR_CONFIG_FILE。没有GA目录猜测、没有mykey回退。
2. ga_monitor_adapter.monitor_profile 负责本机/容器部署路径；agentmain只调用适配层。
3. GA公开事件的 internal_turn/response_content/tool_name 转换为通用 task_turn/text/name；summary标签解析也只在GA适配层。
   原始公开文本、工具参数和结果保留，不增加语义层；decision_context消费通用字段。
4. 任务侧可读的原要求副本由GA适配层创建；内核只接收路径，不再写任务工作区。
5. 根handoff提示不再假定“无工具调用”这种GA结束检测方式；宿主传入边界，模型判断内容。
6. 运行目录绑定显式task_id、原任务SHA256、工作区；不同身份或无身份旧目录拒绝恢复，检查发生在加载history之前。
   同身份恢复保持归档游标单调。重复并发占用同一目录不受支持，宿主仍需提供唯一运行目录。
7. core有独立pyproject，安装产物只含monitor_agent_core及其vendor，依赖requests，不安装GA及其GUI/self-evolution。
   源码暂仍保留在旧仓库目录，是代码组织位置，不是运行依赖。

## _noargs

前轮探针观察到空schema调用带 `_noargs: unused`，不足以断言正常或偶发。
本轮仅对已声明无参数的allow_complete接受空对象或单一_noargs占位；其他字段返回错误，不扩大参数工具的容忍范围。
原始工具调用仍留在history/工具记录中，只在执行入口解释无参占位；根完成有效性/时效检查不变。
没有因该现象放松intervene的message要求，也未给模型新增语义指令或约束。

## 验证与发现过程

第一轮24项测试失败：旧fixture仍直接向core传GA字段、或用缺任务参数的适配器stub、或要求core写任务文件。
按新契约迁移fixture；没有恢复旧字段兼容或删除有效行为测试。之后原有集合298项通过。
最终全部test_monitor*.py，加隔离传输与真实runner回归：350 passed（15.85秒）。
新增test_monitor_host_contract.py覆盖：
- 无损GA字段转换且不修改输入；显式配置；适配器拥有原任务文件；跨任务历史拒绝；_noargs边界。
- 在临时目录复制core、离线构建wheel、无依赖安装到独立目录，用python -I执行完整确定性生命周期。
  无GA源码可导入，初始化、事件发布、后续唤醒、退出均通过；任务工作区无写入；禁止模块均未加载。
  使用确定性provider替身，不声称本轮验证了真实模型效果。
- 原导入独立性测试由glob改rglob，覆盖vendor等子包。

源码文档：GenericAgent-main/monitor_agent_core/HOST_CONTRACT.md。
主要改动：core配置/runtime/decision_context/工具无参入口，GA适配器与启动接线、测试fixtures、独立包装、准备/探针配置路径。
旧工具审计中的大结果读取、增量code_run、review_context设计问题尚未在本轮修改。
各实现步骤均小于600行；未修改任务模型/密钥，未提交密钥或旧.gitignore改动。

## 剩余边界与启动

框架/API/配置/源码依赖已分离，不表示独立机器、容器或安全权限边界。
并发进程、宿主生命周期和中断回调是明确接口，不是借用GA推理核心。换框架只需实现宿主契约。
共享容器和code_run的OS权限仍按此前裁决保留，不能宣称硬文件系统隔离。
旧原始轨迹仍按旧格式归档；新运行使用新契约，不把旧schema历史当作新的续跑目录。
当前准备：method_discovery/artifacts/claude_monitor_20260913/fyne_independent_r1_manifest.json。
旧fyne_r1_manifest对应独立化前源码，只保留历史，不直接启动。新完整任务仍需单独确认。
