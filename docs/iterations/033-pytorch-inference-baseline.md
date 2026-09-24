# 迭代 033：PyTorch LLM 推理基线

> 日期：2026-09-24
> 阶段：Phase 2B.12 技能证据执行
> 状态：PyTorch CPU/MPS 基线完成

## 1. 目标

执行迭代 032 的第一项技能证据计划：建立可复现的 PyTorch 推理项目，冻结模型、输入和测量方法，记录吞吐、延迟、内存与跨设备数值误差。

## 2. 环境事实

- Python：`3.12.1`；
- 机器：Apple Silicon `arm64`；
- PyTorch：`2.14.0`；
- MPS：built / available 均为 `true`；
- CUDA：不可用。

PyTorch 和 NumPy 放在独立 `inference` extra，不进入 Lina 默认依赖和主 CI。手动 workflow 在 Ubuntu CPU 上运行实验测试与基线，避免默认跨平台质量门禁承担大型推理依赖。

## 3. 实现

- 新增 `experiments/pytorch_inference/`：
  - 两层 decoder-only causal Transformer；
  - 固定随机权重和 token 输入，不下载模型、不读取私有数据；
  - CPU/MPS/CUDA 自动设备发现；
  - warmup、每轮设备同步和固定迭代次数；
  - JSON 报告与可选文件输出。
- 报告字段：
  - median / p95 latency；
  - token throughput；
  - 参数、输入、输出和 accelerator allocation bytes；
  - output checksum；
  - 相对 CPU 最大绝对误差与 speedup。
- 新增专用测试和 VS Code `Experiment: PyTorch inference baseline` 任务。

## 4. 基线配置

| 参数 | 值 |
| --- | ---: |
| vocab size | `4096` |
| sequence length | `128` |
| batch size | `4` |
| model width | `128` |
| attention heads | `4` |
| layers | `2` |
| feed-forward width | `256` |
| warmup / measured iterations | `3 / 10` |
| seed | `20260924` |

模型参数内存约 `5.32 MB`，输出张量约 `8.39 MB`。

## 5. 实测结果

| 设备 | Median | P95 | Throughput | Speedup |
| --- | ---: | ---: | ---: | ---: |
| CPU | `17.77 ms` | `18.85 ms` | `28.8k tokens/s` | `1.00x` |
| MPS | `5.42 ms` | `6.44 ms` | `94.5k tokens/s` | `3.28x` |

MPS 当前分配约 `13.71 MB`；MPS 与 CPU 输出最大绝对误差为 `1.19e-6`，低于测试阈值 `1e-4`。

## 6. 失败与修复

1. 初次导入 PyTorch 时环境缺 NumPy，触发初始化告警。将 NumPy 与 PyTorch 一并纳入 `inference` extra。
2. `TransformerEncoder` 在 `norm_first=True` 时提示 nested tensor 优化不会生效。显式设置 `enable_nested_tensor=False`，避免误导性告警。
3. 大型 torch 依赖若进入默认依赖，会拖慢 Lina 主应用与双平台 CI。采用可选 extra 和手动 benchmark workflow 隔离。

## 7. 知识与行为准则

- accelerator benchmark 必须在计时前后同步，否则异步执行会虚报延迟。
- 不同设备必须使用同一 state dict 与输入，并报告数值误差，不能只比较速度。
- warmup、seed、模型形状和迭代次数必须进入报告，结果才可复现。
- 性能证据同时报告 median、p95、throughput 和内存，不用单一最快值。
- 合成小模型只证明 PyTorch 推理与测量能力，不代表生产 LLM serving 或 TensorRT 性能。
- 重型学习依赖应与产品默认依赖隔离，但仍进入 lockfile 和专用 CI。

## 8. 使用方式

```bash
uv sync --extra dev --extra inference --locked
uv run --extra inference --locked python experiments/pytorch_inference/benchmark.py \
  --devices auto \
  --output data/private/evaluation/pytorch_inference_baseline_v1.json
```

## 9. 下一步

实现 C++ PyTorch 扩展：选择一个可验证算子，提供 Python reference、C++ 实现、绑定、构建脚本和误差测试，并复用本基线的输入与 benchmark 结构。

## 10. 面试表达

我没有直接下载大模型跑一次耗时，而是构建固定权重和输入的小型 causal decoder，统一 CPU/MPS 的 state、同步和测量口径。MPS 达到 `3.28x` CPU throughput，最大数值误差为 `1.19e-6`。依赖通过 optional extra 与主 Agent 隔离，并用专用测试、手动 CI 和 JSON 报告保证可复现。
