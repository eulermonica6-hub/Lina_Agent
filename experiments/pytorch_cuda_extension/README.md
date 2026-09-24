# PyTorch CUDA RMSNorm Extension

This experiment implements a float32 RMSNorm CUDA kernel with one block per row and shared-memory reduction. It requires Linux, an NVIDIA GPU, a CUDA-enabled PyTorch build, and NVCC.

## Probe

```bash
uv run --extra inference --locked python -m experiments.pytorch_cuda_extension.runner_preflight
```

The probe reports the PyTorch CUDA build, runtime availability, device count, CUDA home, NVCC, `nvidia-smi`, and actionable reasons when the environment is not ready.

## GPU Test And Benchmark

```bash
uv run --extra dev --extra inference --locked pytest experiments/pytorch_cuda_extension
uv run --extra inference --locked python -m experiments.pytorch_cuda_extension.benchmark \
  --output data/private/evaluation/pytorch_cuda_rms_norm_v1.json
```

On non-CUDA machines, source/probe tests run and GPU tests skip. The self-hosted workflow requires runner labels `self-hosted`, `linux`, `x64`, `gpu`, and `cuda`.

A CUDA performance claim is not valid until the GPU workflow reports device model, compute capability, CUDA/PyTorch versions, latency, throughput, memory, speedup, and error versus the PyTorch CUDA reference.
