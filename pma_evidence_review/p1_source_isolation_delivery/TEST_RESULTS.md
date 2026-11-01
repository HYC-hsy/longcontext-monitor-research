# 离线验收

执行命令（代码初版和远端固定源码各一次）：

```sh
PMA_TEST_STRICT_IMPORTS=1 LITELLM_LOCAL_MODEL_COST_MAP=True python -B pma_evidence_review/tools/run_p1_source_checks.py --report <fresh-report.json>
```

两次均为 31 tests，0 failures，0 errors；原 25 项及新增 6 项。初版本地 afcec47 与远端 9e05fe51ee7375f2c4f0a6127aa7519aa463faea 的完整 tree 相同。测试客户端全部为受网络守卫保护的假客户端，没有实际 provider 请求。

覆盖历史包装无损保留、未知内容隔离、代码字面值不删除、动作／回执配对、外层角色不破坏内层精确键集合、原始输入与投影分离、读源历史边界、未知工具不重试、一般范围提示契约、六工具哈希、冻结案例和 P2／默认路径字节身份。既有测试还覆盖来源关联、预算、续答真实客户端接口的假 provider 路径、工程失败回滚及终态。文本承诺断言不是模型行为评分。

未新增依赖替身；使用既有真实安装依赖。沿用严格 PMA runner 的 typing.TypedDict→typing_extensions.TypedDict 兼容，不声称所有第三方原生未补丁入口均通过。完整 472 项旧套件未跑，本轮只验 P1；已知旧 U/A official_source_git 夹具问题未修改，也未计为本轮失败或通过。

isolation-final-directed2.* 与 isolation-final-remote.* 是原始 stdout/stderr/JSON 的公开投影，仅将本机工作区根目录替换为 <WORKSPACE>。IDENTITIES.json 记录本机原件字节/hash；原件保留本机。MANIFEST.json 哈希针对上传投影。无 profile、凭据、私有端点、隐藏推理或签名。
