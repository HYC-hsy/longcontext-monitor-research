# 源码、许可与复现边界

本包复制现有实现，不在整理过程中修复它的研究或工程缺陷。核心源自本地 d95ed58 工作树，R8 使用 2a2cc9e；逐文件 hash 见 manifest。历史可选模块仍保留，不能仅凭文件存在判断机制启用。

阅读入口：agent.py → pma_fused.py → vendor/pma_memory/memory_agent.py；runtime.py 管理生命周期；provider.py 管理模型协议与 History；workspace.py 和 process_runner.py 提供观察/执行能力。

PMA 作者仓库 https://github.com/yifannnwu/proactive-memory-agent ，固定 commit 89e5c0d6aadfe531a1aee42fd290d48be89973dd，Apache-2.0。复用记忆库、操作、提示构造及 process；本地 transport 将两次调用扩展为工具循环，并替换判断输出控制。因此是机制适配，不是原实验原样复现。

LivePlan 作者仓库 https://github.com/Intelligent-CAT-Lab/Agent-Planner ，固定 commit c16797a09b964f901b34fe3da430ee011a5cc660，MIT。仅凭 vendor 中 types/formatters 的存在不得声称复用其完整控制器或并发调度。

GA 衍生部分保留原 MIT 许可 third_party/GENERICAGENT_LICENSE。PMA/LivePlan 许可在核心 vendor 目录。vendor/NOTICE.md 为原快照，其部分旧运行方式已过时；当前路径以本说明和源码为准，不修改来源快照来掩盖历史。

原创研究文档与新增代码的对外许可尚未指定；私有讨论授权不等于公开开源授权。benchmark 与日志中嵌入源码的再分发尚需发布前核查。没有重新给第三方代码换许可证。

当前只承诺代码审阅和选定离线测试；完整 GA/Harbor 运行环境未导出。适配层 research_runtime 依赖有意未伪装成已满足。历史审计引用未打包路径应按 manifest 本地追溯；若专家需要某段完整原始证据，可补充审核后的材料。
