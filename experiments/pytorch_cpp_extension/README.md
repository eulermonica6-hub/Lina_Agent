# PyTorch C++ RMSNorm Extension

This experiment implements a fused float32 CPU RMSNorm loop as a PyTorch C++ custom operator. It compares the extension against a Python/ATen reference using fixed random inputs.

## Build And Test

```bash
uv sync --extra dev --extra inference --locked
uv run --extra dev --extra inference --locked pytest \
  experiments/pytorch_cpp_extension
```

The first run JIT-compiles `rms_norm.cpp` with the local C++ compiler and Ninja. Build artifacts stay under `.build/` and are ignored by Git.

## Benchmark

```bash
uv run --extra inference --locked python -m experiments.pytorch_cpp_extension.benchmark \
  --output data/private/evaluation/pytorch_cpp_rms_norm_v1.json
```

The report includes median/p95 latency, rows per second, tensor memory, output checksums, C++ speedup versus Python, and maximum absolute error.

This CPU extension demonstrates C++/ATen registration, validation, binding, and benchmarking. It is not a CUDA implementation; the next experiment ports a selected kernel to an NVIDIA environment.
