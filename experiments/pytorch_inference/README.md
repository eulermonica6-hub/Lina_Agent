# PyTorch LLM Inference Baseline

This experiment creates reproducible PyTorch evidence for the NVIDIA AI Computing internship gap. It uses a small causal Transformer with fixed random weights and inputs, so no model download or private data is required.

## Run

```bash
uv sync --extra dev --extra inference --locked
uv run --extra inference --locked python experiments/pytorch_inference/benchmark.py \
  --devices auto \
  --output data/private/evaluation/pytorch_inference_baseline_v1.json
```

`auto` always benchmarks CPU and also benchmarks MPS or CUDA when available. Each device receives the same model state and token IDs. Timings include device synchronization around every measured forward pass.

## Test

```bash
uv run --extra dev --extra inference --locked pytest \
  experiments/pytorch_inference/test_benchmark.py
```

## Report Contract

The JSON report includes:

- Python, platform, PyTorch, and accelerator availability;
- fixed model and input dimensions;
- median and p95 forward latency;
- token throughput;
- parameter, input, output, and accelerator allocation bytes;
- output checksum and maximum absolute error versus CPU;
- accelerator speedup versus CPU.

This is a synthetic inference baseline, not evidence of production LLM serving. The next stage adds a C++ extension against the same reference output, followed by a CUDA kernel benchmark.
