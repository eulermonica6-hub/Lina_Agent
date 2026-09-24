import argparse
import json
import platform
import shutil
import statistics
import subprocess
from collections.abc import Callable
from time import perf_counter
from typing import Any

import torch
from torch import Tensor

from .extension import load_rms_norm_extension, rms_norm_cpp, rms_norm_reference


def benchmark_rms_norm(
    *,
    rows: int = 512,
    hidden_size: int = 1024,
    warmup_iterations: int = 5,
    measured_iterations: int = 30,
    seed: int = 20260924,
) -> dict[str, Any]:
    if rows < 1 or hidden_size < 1:
        raise ValueError("rows and hidden_size must be positive")
    if warmup_iterations < 0 or measured_iterations < 1:
        raise ValueError("warmup must be non-negative and iterations must be positive")

    generator = torch.Generator().manual_seed(seed)
    input_tensor = torch.randn(rows, hidden_size, generator=generator, dtype=torch.float32)
    weight = torch.randn(hidden_size, generator=generator, dtype=torch.float32)
    load_rms_norm_extension()

    python_result, python_output = _measure(
        "python_reference",
        lambda: rms_norm_reference(input_tensor, weight),
        warmup_iterations,
        measured_iterations,
    )
    cpp_result, cpp_output = _measure(
        "cpp_extension",
        lambda: rms_norm_cpp(input_tensor, weight),
        warmup_iterations,
        measured_iterations,
    )
    max_abs_error = float((cpp_output - python_output).abs().max().item())
    cpp_result["speedup_vs_python"] = float(python_result["median_latency_ms"]) / float(
        cpp_result["median_latency_ms"]
    )

    element_bytes = input_tensor.element_size()
    return {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "torch": torch.__version__,
            "python_compiler": platform.python_compiler(),
            "cxx_compiler": _cxx_compiler_version(),
            "torch_threads": torch.get_num_threads(),
        },
        "config": {
            "rows": rows,
            "hidden_size": hidden_size,
            "warmup_iterations": warmup_iterations,
            "measured_iterations": measured_iterations,
            "seed": seed,
        },
        "memory": {
            "input_bytes": input_tensor.numel() * element_bytes,
            "weight_bytes": weight.numel() * weight.element_size(),
            "output_bytes": input_tensor.numel() * element_bytes,
        },
        "max_abs_error": max_abs_error,
        "results": [python_result, cpp_result],
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
        latencies_ms: list[float] = []
        output = operation()
        for _ in range(measured_iterations):
            started = perf_counter()
            output = operation()
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


def _cxx_compiler_version() -> str | None:
    compiler = shutil.which("c++") or shutil.which("clang++") or shutil.which("g++")
    if compiler is None:
        return None
    completed = subprocess.run(
        [compiler, "--version"],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.splitlines()[0]


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Benchmark Python and C++ RMSNorm on CPU.")
    parser.add_argument("--rows", type=int, default=512)
    parser.add_argument("--hidden-size", type=int, default=1024)
    parser.add_argument("--iterations", type=int, default=30)
    parser.add_argument("--warmup", type=int, default=5)
    parser.add_argument("--output", type=str)
    parsed = parser.parse_args(arguments)
    report = benchmark_rms_norm(
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
