# PMA原生FBR：PATH与终局归档修复验收

## 范围与边界

修复R1审计确认的两个工程问题，不改变PMA记忆、提示、同步调度、模型、50轮、温度、任务要求或隐藏评价边界。作者memory_agent及Harbor源码仍逐字一致（16+167项）。旧R1轨迹、0分和旧镜像完整保留，不追改成绩。

## 修复前后

### 实际任务终端的工具路径

修复前：镜像有Go，Terminus2的`bash --login`经`/etc/profile`重置PATH后找不到它。

修复后：依赖镜像构建时由`native_controller/preserve_image_path.py`读取基础镜像PATH，生成`/etc/profile.d/99-native-image-path.sh`，在登录shell中保留这些工具目录。没有改作者shell、工具命令或给模型额外提示，也没有联网重新安装Go。

`TaskDependencies.Dockerfile`增加上述构建步骤。新镜像`longcontext-pma-fbr-deps:20260912-r2`：
`sha256:a6fa79e2dd6cf93c27ebae40cf35852b7aca0e61c3305600c1b41dfa75a24de0`。
旧r1继续保留；`prepare_pma_native_fbr_run.py`后续新manifest使用r2固定身份，不改历史manifest。当前Dockerfile仍针对已核对的Debian/root/FBR工具环境，不宣称所有benchmark镜像都适用。

### 结束后的代码保存

修复前：native trial在评分后清理任务容器，未保存完整最终代码；只能依赖终端/轨迹回溯。

修复后：`pma_native_archive.py`在Agent返回或超时取消后、隐藏测试上传前，将`/app`完整打包到`workspace.before-verifier.tar.gz`，包括.git和未跟踪文件。下载完成后按流计算SHA256，写入native_result。不是只有git diff，删除/新增文件均保留为完整快照。范围是声明的工作区/app，不是整个容器文件系统；不会跟随符号链接额外收集外部目录。

正常完成和已启动环境中的异常退出均尝试归档。归档失败时明确记录失败、跳过评分，使用作者DockerEnvironment已有keep_containers路径停止但不删除容器，留待恢复。没有把失败包装为成功，也不会在归档失败后先上传隐藏测试污染待恢复代码。成功时仍按原流程评分和清理。

归档是停止Agent后的文件快照，不是能保证任意用户后台进程一致性的文件系统事务；tar发现改动导致失败时走保留分支。原生API内部重试计量限制仍在，本轮未扩大修复范围。

## 验收结果

1. 冻结Linux控制器中12项测试通过：原版机制/配置/工具请求、计量、生命周期、归档SHA、拒绝根目录归档、归档失败跳过评分并保留容器。
2. 实际断网tmux + asciinema终端中执行：
   - `command -v go`返回`/usr/local/go/bin/go`；
   - `go version`返回`go1.22.12 linux/amd64`；
   - `go test ./utils -run '^$' -count=1`通过，显示`[no tests to run]`。这会编译公开utils包及测试代码，不调用隐藏checker，不是完成FBR。
3. 完整终端夹具之后的归档成功，25,589,040字节，SHA256 `9ac939406ad587165a75594a991b8e21afccb6a9ffa92d4f8a2375cbd33590d6`。打开tar确认`public-archive-fixture`及`public-toolchain-fixture`存在，评分后才写入的`hidden-evaluation-fixture`不存在；模拟Verifier评分正常。
4. 原始产物：`bench_runtime/pma_linux_controller/work/path_archive_r2/result.json`、同级`path_archive_r2-controller.json`、`trial/agent/terminus_2.pane`及`trial/workspace.before-verifier.tar.gz`。控制器挂载新`build_r8/scripts`，保持原依赖镜像，不重装作者Python依赖。

新增/修改范围：镜像路径准备2文件；归档模块与trial接线；预检与2份测试；控制器脚本清单、FBR准备脚本；本报告和恢复入口。各实现步骤低于600行。12测试及真实终端夹具是工程验收，不是方法效果。无模型API调用、无真实重跑；原有第三方序列化warning未作为本轮扩张理由。

## 后续

工程修复已完成，下一步可用r2镜像、原Sonnet4.5/Opus4.6、50轮/7200秒重新运行同题PMA。新建运行包，勿复用R1 runtime快照。随后才能考虑与同环境无PMA的Terminus2比较；不因修复而改变原模型或算法。
