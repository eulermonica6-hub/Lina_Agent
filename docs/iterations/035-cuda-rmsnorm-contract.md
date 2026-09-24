# 迭代 035：CUDA RMSNorm 实现与验证契约

> 日期：2026-09-24
> 阶段：Phase 2B.14 CUDA 技能证据
> 状态：源码、探针、测试与 GPU workflow 完成；NVIDIA 实测待运行

## 1. 目标

将 RMSNorm 从 Python reference 和 C++ CPU 扩展推进到 CUDA custom op，同时严格区分“代码已实现”和“GPU 已验证”。当前开发机是 Apple Silicon，没有 NVCC、NVIDIA 驱动或 CUDA PyTorch，因此不声明 CUDA 正确性或性能结果。

## 2. 本地环境事实

CUDA 探针结果：

- PyTorch：`2.14.0`，`torch.version.cuda=null`；
- `torch.cuda.is_available()`：`false`；
- device count：`0`；
- CUDA home / NVCC / nvidia-smi：均不存在。

阻塞原因被结构化记录为：PyTorch 非 CUDA build、CUDA runtime 不可用、NVCC 不存在。

## 3. 实现

- 新增 `experiments/pytorch_cuda_extension/`：
  - `binding.cpp` 注册 CUDA custom op；
  - `rms_norm_cuda.cu` 实现 kernel；
  - `extension.py` 负责 JIT/NVCC 构建；
  - `environment.py` 输出可操作环境探针；
  - GPU 条件测试和同步 benchmark；
  - 独立 README。
- Kernel 设计：
  - 一个 block 处理一行；
  - 每线程累加平方和；
  - shared memory 完成 block reduction；
  - `rsqrtf` 计算 inverse RMS；
  - 融合 weight scale 写回输出。
- 显式校验 CUDA device、float32、shape、weight 长度和 epsilon。
- benchmark 固定输入、seed、warmup、同步与迭代，比较 PyTorch CUDA reference 和 custom kernel。

## 4. 验证契约

在 NVIDIA runner 上必须满足：

- 3 组 shape 与 PyTorch reference 的 `rtol/atol <= 1e-5`；
- 非连续输入正确；
- 非法 weight shape 明确失败；
- 报告 GPU 型号、compute capability、PyTorch/CUDA/NVCC 版本；
- 报告 median、p95、rows/s、显存、speedup 和最大误差；
- 不要求 custom kernel 必然更快，负结果必须保留。

## 5. CI 与本地结果

- 新增 self-hosted workflow，runner labels：`self-hosted, linux, x64, gpu, cuda`；
- workflow 执行环境探针、GPU 测试、benchmark 并上传 JSON artifact；
- 本地组合测试结果：14 passed、6 skipped；
- 6 项 skip 全部由 CUDA 环境不可用触发，不是静默成功；
- 探针与 CUDA 源码契约测试在 macOS 上通过。

同时修复上一版本 `inference-benchmark.yml` 的测试步骤缩进错误；组合 workflow 契约重新检查。

## 6. 知识与行为准则

- 没有 NVCC 和 NVIDIA runtime 时，只能完成源码与验证契约，不能声称 CUDA Kernel 已验收。
- CUDA benchmark 必须在计时前后 `torch.cuda.synchronize()`，否则异步执行会虚报延迟。
- GPU 报告必须包含设备型号与 compute capability，不跨硬件直接比较裸延迟。
- 源码静态检查不能替代 NVCC 编译和 GPU 数值测试。
- 条件 skip 必须附带明确原因，并在 GPU runner 上转为实际执行。
- CUDA 性能若不优于 PyTorch reference，应保留结果并分析 kernel、shape 和 launch 开销。

## 7. 使用方式

本地探针：

```bash
uv run --extra inference --locked python -m experiments.pytorch_cuda_extension.environment
```

NVIDIA 环境：

```bash
uv run --extra dev --extra inference --locked pytest experiments/pytorch_cuda_extension
uv run --extra inference --locked python -m experiments.pytorch_cuda_extension.benchmark \
  --output data/private/evaluation/pytorch_cuda_rms_norm_v1.json
```

## 8. 下一步

在具备 NVIDIA GPU、CUDA PyTorch 和 NVCC 的 self-hosted runner 上执行 `CUDA Benchmark` workflow。只有 artifact 通过误差阈值后，才进入技能证据回写与排序复跑。

## 9. 后续阶段

1. **GPU 实测验收**：编译、误差、性能和显存报告。
2. **证据回写与重排**：将通过验收的 PyTorch/C++/CUDA 项目写入匿名简历，复跑 Gold。
3. **持久化**：保存候选事实、JD、Agent Run、计划、实验和版本关系。
4. **产品工作流**：状态图、岗位监控、简历定制、学习闭环和自然语言入口。

## 10. 面试表达

我在无 NVIDIA 硬件的开发机上没有伪造 CUDA 结果，而是实现了完整 kernel、PyTorch 注册、环境探针、条件测试和 self-hosted GPU workflow。macOS 上 14 项实验通过、6 项 CUDA 测试带原因跳过；下一步必须由真实 NVIDIA runner 产出误差与性能 artifact 后才能算完成。
