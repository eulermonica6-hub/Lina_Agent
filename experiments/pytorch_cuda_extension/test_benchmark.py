import pytest

from .benchmark import benchmark_cuda_rms_norm
from .environment import cuda_environment


@pytest.mark.skipif(not cuda_environment()["ready"], reason="CUDA build/runtime is unavailable")
def test_cuda_benchmark_reports_error_and_latency() -> None:
    report = benchmark_cuda_rms_norm(
        rows=32,
        hidden_size=64,
        warmup_iterations=1,
        measured_iterations=2,
    )

    assert report["max_abs_error"] < 1e-5
    assert [result["implementation"] for result in report["results"]] == [
        "pytorch_cuda_reference",
        "custom_cuda_kernel",
    ]
    assert all(result["median_latency_ms"] > 0 for result in report["results"])
    assert report["results"][1]["speedup_vs_pytorch"] > 0
