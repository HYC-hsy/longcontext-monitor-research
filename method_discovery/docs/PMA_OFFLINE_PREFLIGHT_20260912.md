# PMA 隔离依赖与零 API 预检

## 本阶段结果

已补齐 Linux 运行环境 shortuuid 1.0.13；无网络容器 PMA smoke 与既有隔离传输夹具通过。未启动任务 Agent，未调用真实模型，没有方法效果证据。Clean Monitor 策略及 PMA 原版机制未修改。

## 可复用依赖准备

宿主 pip 从 PyPI 下载 `shortuuid==1.0.13` 的 `py3-none-any` wheel，随后以 `--no-index --no-deps --no-compile --target` 安装到 `bench_runtime/m2/linux/ga-env/lib/python3.12/site-packages`。该包为纯 Python，实际 Linux Python 3.12 导入通过；未复制 Windows 二进制，也未让任务联网安装。

- wheel：`bench_runtime/pma_wheels/shortuuid-1.0.13-py3-none-any.whl`
- SHA-256：`a482a497300b49b4953e15108a7913244e1bb0d41f9d332f5e9925dba33a3c5a`
- 固定版本入口：`GenericAgent-main/pma_baseline/requirements.txt`
- wheel/已安装运行环境为本地依赖产物，不进源码 Git。新机器需要下载并核对上述摘要、离线安装后重新预检。

## 验收证据

1. `artifacts/pma_offline_20260912/r2/result.json`：Linux 无网络、只读源码/运行环境，4 次假 provider 调用覆盖两轮 phase1 更新→phase2 读更新后的 bank→一次性提醒；新任务空 bank、日志写入通过。没有挂载真实 mykey 或完整历史工作区。
2. `artifacts/pma_offline_20260912/transport/result.json`：复用既有 Docker 夹具，通过 Unix 双段流式回传、只有 loopback、零 capabilities、IPv4/IPv6/宿主直连阻断、任意抓取及 hosted search 拒绝、私密 gateway 配置不可见。
3. PMA/上游一致性/Clean runtime：20 passed，另 3 subtests；隔离传输回归：18 passed。
4. Docker 临时容器和专属卷已清理。保留 Engine、Debian 镜像、wheel 和运行环境；未删除历史任务资源。

R1 在镜像身份查询时失败，未执行 PMA，原始失败记录保留。随后直接查询及 R2 成功；首轮根因未确认，不称作 PMA 方法失败或声称已修复 Docker 根因。新增脚本改善失败 stderr 记录，便于再次发生时定位。

## 文件范围

- 新增 `method_discovery/preflight_pma_offline.py`：可重复零 API Docker 预检；假 provider、固定无网、只挂 PMA 包与运行环境、明确一次性资源清理。
- 更新恢复入口与本报告，保存三份无密钥结果。
- 原样纳入 Git 两份此前未跟踪的历史文件：`long_context_bench/adapters/isolated_transport.py`、`long_context_bench/scripts/check_isolated_transport_docker.py`。二者本轮已完整阅读且测试通过；是历史依赖归档，不是本阶段新机制或新开发成果。

## 下一门禁

本阶段只验证组件和隔离通道，并非完整 Harbor 真实启动预检通过。仍需针对单次任务冻结 task ID/版本、模型、500 turn/最终时间预算、对照和费用，核对任务镜像本地依赖与信息边界、当前源码身份，并测试真实模型工具往返。当前 API 有效性未知；没有生成真实密钥 bundle 或批准运行六题面板。用户确认下一阶段及单次真实启动后才执行。
