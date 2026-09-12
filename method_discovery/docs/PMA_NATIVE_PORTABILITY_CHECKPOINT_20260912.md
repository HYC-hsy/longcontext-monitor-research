# 官方完整入口准备：Linux 控制环境门禁

## 状态

本阶段未达“完整官方入口可启动”验收。已完成安装与源码身份核查、官方真实控制循环的假模型测试、外层事后评价适配；实际 Docker 夹具暴露 Windows 控制进程路径不兼容。下一步需要 Linux 原生控制环境，不应继续修改作者各处容器路径来假装原样复现。没有真实模型调用、没有真实 benchmark 任务。

## 完成的工作与证据

- 从固定上游本地 checkout 构建并安装原 memory-agent 0.1.0 / vendored Harbor 0.1.42。安装后逐字节比对 memory_agent 16 项、Harbor 167 项源码/资源，全部一致；上游 git 工作区仍干净。
- `bench_runtime/pma_native_venv` 是独立安装位置，但启用了 system-site-packages，复用 GA/用户目录的已安装依赖；不是完全隔离或锁定的复现环境。litellm 1.81.11 等本次补入独立 venv；没有修改 GA provider 或模型配置。Harbor 声明的其他云平台 SDK 尚未安装，不能声称 pip check 全绿。
- `test_pma_native_contract.py` 直接创建官方 baseline / PMA，并执行作者 `_run_agent_loop`、trigger、两阶段记忆及注入。仅替换模型与环境边界；2测试通过。初始化+普通一步共4次假memory call；两次完成声明之间不再记忆调用。未测试模型能力或完整压缩过程。
- `pma_native_trial.py` 是外层候选适配，不替换作者 Agent：Docker 代替 Enroot，task网络关闭，Agent停止后才运行作者 Verifier，缺评分文件记评价失败/null而非0。3项生命周期测试通过。当前是native-host-controller-offline-docker，不是既有Clean Unix-inference profile；尚未批准用此部署做正式公平比较。
- `preflight_pma_native.py` 核查安装内容并提供零API Docker夹具；不读取实际mykey。结果在 `artifacts/pma_native_20260912/r1` 和 `r2`。R1缺夹具Dockerfile；R2成功进入容器并执行假Agent，但事后评价失败。

## 实际阻塞证据

R2 verifier/test-stdout.txt：`bash: teststest.sh: No such file or directory`。
作者 Verifier 用 `str(Path('/tests') / ...)` 构造 Linux 容器命令，Windows Path 产生反斜杠，shell吃掉它们。相同风格也出现在Terminus/tmux容器路径中。因此不能只修一个评分命令就宣称Windows兼容。

作者原runner只读取reward.txt且缺失默认0，没有在该路径调用Verifier；这解释了为何本地移植必须显式补事后评价。并不据此断言作者论文结果错误，他们可能使用外部集群评分流程；该外部流程未由当前源码证明。

作者 Docker.stop(delete=True) 会使用 `down --rmi all`，可能清除夹具使用的共享镜像。本轮夹具曾调用原行为；适配已改成普通 down（delete=False），不再主动删除共享镜像。没有执行全局prune，不触及历史任务目录。需要时重新拉取Debian测试镜像即可。

## 下一重大环境选择

建议在独立 Linux 控制环境安装同一作者源码及所需依赖，保留原 Agent/循环/路径语义；外层只适配 Docker、事后评分与成本归档。需要明确其与现行Unix推理隔离的部署关系，不能静默让native路径成为绕开信息边界的入口。真实启动前还要确认原配置模型可用性、题目/版本/预算与评分条件。

当前Windows原生真实入口已fail-fast，只允许显式假Agent夹具；GA-PMA适配仍可用，不受此次native阻塞影响。不能因为GA适配能跑而宣布官方完整复现完成，也不能在修好Linux环境前启动native真实任务。
