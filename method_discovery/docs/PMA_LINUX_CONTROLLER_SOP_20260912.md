# PMA Linux 控制环境：准备完成与启动 SOP

## 结果与范围

2026-09-12 用户批准约5GB E盘空间、2CPU/2GB运行配额后完成本阶段。Docker数据盘位于 `E:/Docker/wsl-data`；构建上下文与工作产物位于 `E:/LongContext/bench_runtime/pma_linux_controller`。没有安装新WSL发行版，没有修改Windows/GA环境、旧监察机制或作者源码。

镜像：`longcontext-pma-native:20260912-r1`。
身份：`sha256:6731421eb17a89e7a11d435697fe0770ab685471c520980966cbef52296da4b3`。
Docker image inspect报告Size为376544602字节（约359MiB）；该字段不能替代Docker虚拟盘实际占用。Docker整体Images相对之前报告从114.3GB变成116.2GB，Build Cache从1.857GB变成3.404GB，存在共享层，不应简单相加当独占物理空间。E盘准备后空闲52365299712字节（约48.8GiB），未触及5GB预留风险。未实际创建5GB占位文件，预留是容量预算而非磁盘配额。

## 安装与保真

- Python3.12 Linux与Docker CLI基础镜像固定digest，见native_controller/Dockerfile。
- 使用作者本地源码构建两个包，并安装完整声明依赖；pip check通过。这次不继承Windows system-site-packages。
- 原memory_agent 16项、Harbor167项源码/资源与安装内容逐字节一致。
- 完整当前依赖版本见native_controller/dependency_snapshot.json。这是本次解析/安装快照，不是作者论文当时的锁文件；Dockerfile仍遵循作者依赖范围，未来重新构建可能解析到不同传递依赖。复用当前镜像身份可保持当前安装版本，重建必须重新对比快照并验收。
- 镜像只包含作者源码、配置、通用资源和4份已核查测试/编排脚本；不含mykey、旧实验轨迹或GA工作区。

## 已执行的零 API 验证

1. 无网络、2CPU/2GB、只读镜像、临时/tmp内执行5项测试全部通过：官方工厂与完整记忆循环，普通步骤/完成边界，一次性注入及事后评分生命周期。模型和终端结果为假对象，不声称真实任务效果。
2. 用作者DockerEnvironment创建真实的Debian夹具容器。模型仍为假Agent，但实际执行文件操作，并在它停止后由作者Verifier上传夹具test.sh并运行，成功读取1.0。该1.0仅为夹具断言通过，绝不是benchmark分数。
3. 验证任务容器只有lo、没有Docker socket、在Agent阶段没有/tests/test.sh。Linux消除了上一轮Windows Path导致的teststest.sh错误，无需修改作者路径代码。
4. 上述容器生命周期夹具的控制容器cgroup内存峰值66551808字节（约63.5MiB）。不是包含真实模型长history或长程任务的峰值；保留2GB限额等待真实使用确认。
5. 所有临时控制/任务容器已退出清理；Docker ps为空。不删除镜像或全局缓存，不停止Engine。

原始结果：bench_runtime/pma_linux_controller/work/linux_r1/result.json，控制stdout/stderr在linux_r1-controller.json。本阶段Git保留一份PMA_LINUX_CONTROLLER_CHECK_RESULT_20260912.json。

## 可重复操作

先 `docker info`，不可因Docker进程存在就跳过Engine检查。

准备上下文（必须新目录，拒绝覆盖）：
`D:/python/envs/ga_bench/python.exe method_discovery/prepare_pma_linux_controller.py --output bench_runtime/pma_linux_controller/build_NEW`

构建：`docker build --tag longcontext-pma-native:NEW bench_runtime/pma_linux_controller/build_NEW`。
本轮先发生一次Docker Hub认证超时；显式拉取两官方基础镜像后成功，不采用不可信镜像源替代。

不接Docker接口的离线单测：
`docker run --rm --network none --cpus 2 --memory 2g --read-only --tmpfs /tmp:rw,size=256m longcontext-pma-native:20260912-r1`

带真实Docker环境的零API夹具：
`D:/python/envs/ga_bench/python.exe method_discovery/run_pma_linux_preflight.py --label UNIQUE_LABEL`

关键路径：控制器的工作目录映射到与Docker Desktop daemon相同的 `/run/desktop/mnt/host/e/LongContext/bench_runtime/pma_linux_controller/work`，保证作者发给daemon的bind路径实际指向E盘，而不是另一个空目录。此约定仅验收过本机E盘，不宣称跨平台通用。

## 权限与尚未完成的真实启动门禁

控制器通过Docker socket编排同级任务容器，它是可信研究基础设施，不是模型可用的code_run工具。Docker socket不是受限权限接口；不得挂给任务容器，也不得把当前控制器复用为不可信通用agent的执行工作区。

本轮controller也无网络、没有密钥；模型使用假响应。正式推理的受控通道还没有在这个native控制器中完成连通验证；不能为了联网把任务容器放回公网。它不是当前Clean Monitor的Unix部署profile，不得据此宣布所有条件部署已统一。

环境准备阶段已完成；官方PMA方法效果复现未完成。下一步为单次启动准备：确认task/版本/模型/预算，检查任务预装tmux/asciinema等依赖，接通并验证推理通道，完整记录task与memory用量；正式真实题仍需独立确认。不会因为此夹具通过自动开跑PMA或六题面板。
