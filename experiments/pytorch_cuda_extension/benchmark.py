import argparse
import json
import platform
import statistics
from collections.abc import Callable
from time import perf_counter
from typing import Any

import torch
from torch import Tensor

from .environment import cuda_environment, require_cuda_environment
from .extension import load_rms_norm_cuda_extension, rms_norm_cuda, rms_norm_reference


def benchmark_cuda_rms_norm(
    *,
    rows: int = 4096,
    hidden_size: int = 1024,
    warmup_iterations: int = 10,
    measured_iterations: int = 100,
    seed: int = 20260924,
) -> dict[str, Any]:
    require_cuda_environment()
    if rows < 1 or hidden_size < 1:
        raise ValueError("rows and hidden_size must be positive")
    if warmup_iterations < 0 or measured_iterations < 1:
        raise ValueError("warmup must be non-negative and iterations must be positive")

    generator = torch.Generator().manual_seed(seed)
    input_tensor = torch.randn(rows, hidden_size, generator=generator).cuda()
    weight = torch.randn(hidden_size, generator=generator).cuda()
    load_rms_norm_cuda_extension()
    pytorch_result, pytorch_output = _measure(
        "pytorch_cuda_reference",
        lambda: rms_norm_reference(input_tensor, weight),
        warmup_iterations,
        measured_iterations,
    )
    kernel_result, kernel_output = _measure(
        "custom_cuda_kernel",
        lambda: rms_norm_cuda(input_tensor, weight),
        warmup_iterations,
        measured_iterations,
    )
    max_abs_error = float((kernel_output - pytorch_output).abs().max().item())
    kernel_result["speedup_vs_pytorch"] = float(pytorch_result["median_latency_ms"]) / float(
        kernel_result["median_latency_ms"]
    )
    return {
        "environment": {
            **cuda_environment(),
            "platform": platform.platform(),
            "device": torch.cuda.get_device_name(),
            "capability": list(torch.cuda.get_device_capability()),
        },
        "config": {
            "rows": rows,
            "hidden_size": hidden_size,
            "warmup_iterations": warmup_iterations,
            "measured_iterations": measured_iterations,
            "seed": seed,
        },
        "memory": {
            "input_bytes": input_tensor.numel() * input_tensor.element_size(),
            "weight_bytes": weight.numel() * weight.element_size(),
            "output_bytes": input_tensor.numel() * input_tensor.element_size(),
            "allocated_bytes": torch.cuda.memory_allocated(),
        },
        "max_abs_error": max_abs_error,
        "results": [pytorch_result, kernel_result],
    }


def _measure(
    name: str,
    operation: Callable[[], Tensor],
    warmup_iterations: int,
    measured_iterations: int,
) -> tuple[dict[str, float | str], Tensor]:
    with torch.inference_mode():
        for _ in range(warmup_iterations):
            operation()
        torch.cuda.synchronize()
        latencies_ms: list[float] = []
        output = operation()
        for _ in range(measured_iterations):
            torch.cuda.synchronize()
            started = perf_counter()
            output = operation()
            torch.cuda.synchronize()
            latencies_ms.append((perf_counter() - started) * 1000)
    median_latency_ms = statistics.median(latencies_ms)
    return (
        {
            "implementation": name,
            "median_latency_ms": median_latency_ms,
            "p95_latency_ms": _percentile(latencies_ms, 0.95),
            "rows_per_second": len(output) / (median_latency_ms / 1000),
            "output_checksum": float(output.mean().item()),
        },
        output,
    )


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * percentile), len(ordered) - 1)
    return ordered[index]


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Benchmark PyTorch and custom CUDA RMSNorm.")
    parser.add_argument("--rows", type=int, default=4096)
    parser.add_argument("--hidden-size", type=int, default=1024)
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--output", type=str)
    parsed = parser.parse_args(arguments)
    report = benchmark_cuda_rms_norm(
        rows=parsed.rows,
        hidden_size=parsed.hidden_size,
        warmup_iterations=parsed.warmup,
        measured_iterations=parsed.iterations,
    )
    payload = json.dumps(report, indent=2)
    if parsed.output:
        with open(parsed.output, "w", encoding="utf-8") as output_file:
            output_file.write(f"{payload}\n")
    print(payload)


if __name__ == "__main__":
    main()
