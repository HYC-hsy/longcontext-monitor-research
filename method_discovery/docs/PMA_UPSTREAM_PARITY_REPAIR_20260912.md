# PMA原样复用核查与修正

用户要求公开实现尽量直接复用。本阶段不改变研究方案、不启动真实任务。

## 已修正

1. 恢复原universal_memory.py的shortuuid.uuid()[:8]，删除此前stdlib UUID替代。ga_bench安装shortuuid 1.0.13，新增requirements.txt固定版本；网络仅用于安装依赖，没有模型API调用。
2. 轨迹格式恢复原[Recent Trajectory]标题、段落分隔、空字段省略、可选plan和命令截断表述。首个执行步骤改为Step2，与原初始化Step1对应。
3. 更新NOTICE，不再声称存在UUID替代；原Apache许可证保留。

## 原样程度的实际证据

三份核心模块memory_agent.py、universal_memory.py、bm25_search.py与固定原仓库文本逐项比较通过（忽略换行/文件末尾空白）。原模型可见提示、bank工具、BM25逻辑、status长度、XML解析和随机ID生成均不改。

轨迹排版测试直接抽取原memory_enabled_agent的两个纯格式化函数，比较空窗口、单步、超过8步情形的完整文本；没有只测我们自己写的期待值。GA公开response没有独立plan解析，默认仍整体作为analysis；原格式可以接收plan，不凭空为GA推断隐藏意图。

## 模型调用边界

原MemoryAgent两phase分别传prompt/system/tools，没有message_history参数。另检查本地Harbor缓存LiteLLM.call，其缺省history为空，每次拼接当前prompt；因此不应自行加入Clean持续history。适配测试确认每phase独立provider实例和当前两条system/user消息，第二phase从更新的bank重建信息。

限制：本地Harbor缓存不是已经证明与论文运行完全一致的依赖锁；不能据此宣称原LiteLLM对system/cache/重试的底层处理与当前provider逐项相同。仍保留必要的GA模型/协议接线，并在论文中标注机制适配，不把它写成原作者原始结果复现。未将注释里“shared conversation”当成额外隐式history实现依据。

## 验证与运行前遗留

PMA、源码一致性及Clean并发回归共20项通过，另3个源文件子项通过。未使用原生隐藏评价、Docker或模型API；没有修改Clean机制。

shortuuid只确认安装在宿主ga_bench，尚未确认隔离容器的ga-env存在该依赖。真实启动前必须从可信离线包补入/验证容器运行时，不能让无网络任务自行pip联网，也不能临时退回UUID替代。这个是已知依赖准备项，不声称现在已经能直接启动。

文件改动：PMA universal_memory/runtime/NOTICE/requirements；新增test_pma_upstream_parity；更新恢复入口。本阶段独立Git保存，旧实现可回退。下一步可以进行不调用模型的隔离依赖准备与预检，真实任务仍需独立批准。
