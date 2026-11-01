# 交接：仅 Phase A 离线验收

完整源码已公开于 `8e687fd8fdec50d928ccde5235342bfd0cc81cfa`，与已验收本地 `450a22f8` 的完整 tree 相同。使用最终回复的固定远端交付 SHA 检出、核对 MANIFEST 和案例 INDEX 后，仅做离线复验。不要使用旧中间版本；也不要启动真实 P1、Task、P2、原生评价或旧方法对照，不要改动其他线程任务。
本轮仅完成实现、25 项离线工程检查和六例冻结。未来真实 P1 的案例、数量、参数和授权由父线程另行指定；默认 scripted 或 CLI 中存在真实模式开关均不构成运行许可。

使用既有真实依赖和 Python 3.12 环境，复验命令为：

```bash
python -B pma_evidence_review/tools/run_p1_source_checks.py --report /new/local/p1-checks.json
```

测试 runner 沿用已有 PMA TypedDict→typing_extensions.TypedDict 导入兼容，不替换可选依赖。实际 profile/LiteLLM 路径的证明来自安装库加假 provider；尚未验证真实服务或原生 messages 工具续轮。scripted CLI 可直接运行；同一环境还直接验证了不做 TypedDict 替换的客户端构造和假 provider 转换；其他 Python/Pydantic 组合未覆盖。
单案例入口 `pma_evidence_review/tools/run_p1_source_case.py` 一次只接收一个冻结 JSON，输出目录必须新建且不能自动重试。当前六例位于 cases/，核对 INDEX.json SHA 后使用，不能根据后续模型输出改题再追认冻结。
本轮保留所有本地报告、请求、可见响应、来源回执、bank_after、run_config 和 terminal。公开发布前排除私有 profile、凭据、端点、隐藏推理、签名及隐藏测试正文；PUBLICATION_SCOPE.json 只说明被拒载荷的公开来源，不是重试许可。
