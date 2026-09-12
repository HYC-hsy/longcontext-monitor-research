# 活跃工作认识：真实入口检查与待启动规格

用户要求测试；按真实启动独立门禁，先检查入口并准备具体规格。本轮没有模型API、Docker真实任务或效果结果。

发现并修复启动遗漏：GA adapter有新开关，但Harbor FORWARDED_ENV_VARS没有，真实容器会默认关闭候选。补容器转发及manifest受控环境清理集合，防止开关丢失或跨条件残留。新增回归核对两处集合。此前151项核心测试不覆盖此宿主到容器边界，不能据它们声明整个真实接线已完成。

新增prepare_active_working_run.py，复用clean启动门禁，不启动模型。生成 `method_discovery/artifacts/active_working_20260912/fyne_r1_manifest.json`，状态prepared_not_executed。

待批准启动：
- Fyne 2.2 / roadmapbench:fyn-2.2.0-roadmap，method_dev。
- 独立Clean Monitor + active working context；其他UWRBA、tool_feedback、PMA关闭。
- 原参照配置：Opus4.8任务、GPT-5.6-sol high监察；500轮、10000秒Agent预算，原生评价只在结束后。
- no-network-unix-inference-v1；不挂旧轨迹、不取目标版本参考答案。
- 目标：笔记是否自主更新、最新认识是否实用于判断、旧认识是否强化错误；同时检查连续纠偏、根范围、时延和成本。
- 历史公共base仅诊断参照：题目相同但旧网络/工程条件不同，不可称严格配对。新隔离control需另批准。
- 时间参考旧base约50分钟，但本次可能达到10000秒上限；旧监察输入累计约1063万token，仅说明费用可能较大，不是新版本预测。没有可靠美元账单估计，记录实际usage。

验证：运行入口、Harbor adapter、隔离转发相关94项通过（1.46秒）；新manifest已生成。Docker engine、当前模型连通与容器实际配置仍需启动前实时预检；此文不宣称通过了尚未执行的检查。生产默认仍关闭候选。

本轮修改两个入口模块、一项入口回归、新准备脚本及本文/checkpoint；代码增删小于600行。未清理用户旧产物。停止并报告具体预算，待用户确认真实启动。
