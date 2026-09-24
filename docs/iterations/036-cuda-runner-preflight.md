# 迭代 036：CUDA Runner Preflight 与安全注册

> 日期：2026-09-24
> 阶段：Phase 2B.15 外部 GPU 验收准备
> 状态：runner 契约完成；等待 NVIDIA Linux 主机注册

## 1. 问题

CUDA kernel、条件测试和 workflow 已完成，但当前环境没有 `gh` CLI、已注册 self-hosted runner、NVIDIA GPU、NVCC 或 CUDA PyTorch。直接触发 workflow 会无限排队或在未知主机上失败，且 runner 注册 token 属于敏感凭据，不能通过聊天或仓库传递。

## 2. 实现

- 新增 `runner_preflight.py`，统一检查：
  - Linux / x86_64；
  - 至少 20 GiB 可用磁盘；
  - Git、C++、Ninja；
  - CUDA-enabled PyTorch；
  - CUDA runtime、GPU device count、CUDA home、NVCC、nvidia-smi。
- `--require-ready` 在任一条件不满足时返回非零状态，workflow fail-fast。
- 增加当前环境可操作失败测试和模拟 ready Linux GPU runner 测试。
- 新增安全注册文档，规定 labels、preflight、workflow、artifact 验收和清理流程。
- CUDA workflow 在编译前运行完整 preflight。

## 3. 当前探针结果

当前 Mac：

- OS / arch：Darwin / arm64；
- Git、Apple clang、Ninja：可用；
- free disk：约 102.7 GiB；
- CUDA PyTorch：否；
- CUDA runtime / devices：不可用 / 0；
- CUDA home / NVCC / nvidia-smi：均不存在。

因此 `ready=false`，原因列表完整且与事实一致。

## 4. 验证

- preflight 单元测试：当前环境失败路径 + 模拟 ready 路径均通过；
- CUDA 本地源码/探针测试继续通过；
- `--require-ready` 已接入 self-hosted workflow；
- workflow YAML 与 VS Code task JSON 通过语法检查。

## 5. 知识与行为准则

- 外部硬件依赖应先做机器可读 preflight，再做编译和 benchmark。
- runner 注册 token 是敏感且短期凭据，只能在目标主机终端输入。
- self-hosted runner 应使用独立非 root 账号，且不运行不可信 fork PR。
- workflow queued 不代表实验开始；必须确认匹配 labels 的 online runner。
- artifact 必须绑定 commit、GPU 型号、软件版本和误差阈值，才能进入技能证据。
- 没有 GPU 凭据时，正确的代理行为是完成契约并明确外部阻塞，而不是索取或猜测秘密。

## 6. 下一步

用户在一台 NVIDIA Linux x64 主机上按 `docs/CUDA_RUNNER_SETUP.md` 注册 runner，并直接在该主机终端使用 GitHub 生成的临时 token。runner online 后，在 Actions 页面触发 `CUDA Benchmark`。

## 7. 后续阶段

1. 下载并审核 GPU artifact，记录误差、性能、显存和负结果。
2. 通过验收后回写匿名简历的 PyTorch/C++/CUDA 项目证据。
3. 复跑双 Gold，观察 NVIDIA 唯一逆序是否由真实证据改变。
4. 进入候选事实、JD、Agent Run、计划与 benchmark 持久化。

## 8. 面试表达

CUDA 代码完成后，我没有把“缺 GPU”当成模糊备注，而是实现了 runner preflight，把 OS、架构、磁盘、工具链、PyTorch CUDA build、NVCC 和驱动状态变成机器可读门禁。同时明确 self-hosted runner 的 token、账号和 fork 安全边界，使外部验收可重复且不会泄露凭据。
