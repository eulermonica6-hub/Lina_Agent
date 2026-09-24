# 迭代 034：PyTorch C++ RMSNorm 扩展

> 日期：2026-09-24
> 阶段：Phase 2B.13 C++ 技能证据执行
> 状态：CPU C++ extension、误差与性能基线完成

## 1. 目标

执行 NVIDIA 技能证据计划的第二项：实现带 Python reference、C++ 算子、PyTorch 注册、构建测试和 benchmark 的扩展，并在固定输入上验证数值误差与性能。

## 2. 环境

- Apple Silicon `arm64`；
- Python `3.12.1`；
- PyTorch `2.14.0`；
- C++ compiler：Apple clang `21.0.0`；
- Ninja `1.13.2`；
- PyTorch CPU threads：`5`。

Ninja 加入 `inference` optional extra；编译产物位于实验目录 `.build/`，不进入 Git。

## 3. 实现

- 使用 `TORCH_LIBRARY` / `TORCH_LIBRARY_IMPL` 注册 `lina_rms_norm::forward` CPU op；
- 输入为 float32 CPU tensor 和一维 weight，最后一维为 hidden size；
- C++ 实现按行计算 RMS 并融合 scale，支持非连续输入；
- 对设备、dtype、维度、weight 长度与 epsilon 做显式校验；
- Python reference 使用 PyTorch `square -> mean -> rsqrt -> scale`；
- JIT loader 使用 Ninja、`-O3` 与 `-ffast-math`；
- benchmark 固定 shape、seed、warmup 和迭代，报告 median/p95、rows/s、memory、checksum、speedup 与最大误差。

## 4. 实测配置

| 参数 | 值 |
| --- | ---: |
| rows | `512` |
| hidden size | `1024` |
| warmup / measured iterations | `5 / 30` |
| input / output bytes | `2,097,152 / 2,097,152` |
| weight bytes | `4,096` |

## 5. 实测结果

| 实现 | Median | P95 | Rows/s |
| --- | ---: | ---: | ---: |
| Python / ATen reference | `0.217 ms` | `0.502 ms` | `2.35M` |
| C++ fused extension | `0.136 ms` | `0.170 ms` | `3.78M` |

C++ 相对 Python 加速 `1.60x`；最大绝对误差 `1.91e-6`，低于验收阈值 `1e-5`。

## 6. 失败与优化

### 6.1 首轮 C++ 更慢

首轮 C++ median `0.601 ms`，Python `0.226 ms`，只有 `0.38x`。原因是 double 累加、通用并行 grain 和缺少快速数学向量化，使自定义循环输给成熟 ATen kernel。

只做一次有边界优化：

- 改为 float 累加，匹配 float32 输入；
- 增加 `-ffast-math`；
- parallel grain 固定为 `16`；
- 保持误差测试不变。

优化后加速提升至 `1.60x`，误差保持 `1.91e-6`。若优化仍慢，本轮也会保留负结果，不通过测试阈值包装性能。

### 6.2 组合测试模块冲突

两个实验目录都有 `test_benchmark.py` 和裸 `benchmark` import，分别运行通过，但同一 pytest 进程收集时模块冲突。将 `experiments` 与子目录包化，改用相对 import 和 `python -m` 入口；组合 12 项测试通过。

## 7. 知识与行为准则

- C++ extension 不天然比 Python 快；Python 调用的 ATen 已是优化 C++ kernel，必须实测。
- 性能优化必须保持同一输入、reference 和误差阈值，不能用精度变化换速度而不报告。
- 首轮负结果应记录并定位，只允许有明确假设的有限优化循环。
- 自定义 op 必须验证设备、dtype、shape 和参数边界，不把非法输入交给裸指针循环。
- 单目录测试通过不等于 CI 组合通过；多个实验必须在同一 pytest 进程验证模块命名。
- 报告必须区分 Python 构建编译器与实际 C++ 编译器。

## 8. 使用方式

```bash
uv sync --extra dev --extra inference --locked
uv run --extra dev --extra inference --locked pytest \
  experiments/pytorch_inference experiments/pytorch_cpp_extension
uv run --extra inference --locked python -m experiments.pytorch_cpp_extension.benchmark \
  --output data/private/evaluation/pytorch_cpp_rms_norm_v3.json
```

## 9. 后续阶段

1. **CUDA Kernel**：在 NVIDIA 环境实现 RMSNorm CUDA kernel，与 C++ CPU/Python reference 做误差和吞吐对比。
2. **证据回写与重排**：只有项目验收后才把 PyTorch/C++/CUDA 写入匿名简历，复跑 Gold，观察 NVIDIA 逆序是否由真实证据消失。
3. **持久化**：保存候选确认、JD 快照、Agent Run、计划与 benchmark 版本，支持恢复和审计。
4. **产品工作流**：可解释状态图、岗位监控、简历定制、学习闭环和自然语言入口。

## 10. 面试表达

我实现了一个 PyTorch C++ RMSNorm custom op。首轮 C++ 只有 Python/ATen 的 `0.38x`，我没有隐藏负结果，而是定位 double 累加和向量化问题。有限优化后达到 `1.60x`，最大误差 `1.91e-6`。整个实验包含输入校验、非连续张量测试、JIT 构建、组合 CI 和可复现 JSON 报告。
