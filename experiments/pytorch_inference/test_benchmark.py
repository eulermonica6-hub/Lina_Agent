import json

import pytest
import torch

from .benchmark import BenchmarkConfig, benchmark_devices, main


def _tiny_config() -> BenchmarkConfig:
    return BenchmarkConfig(
        vocab_size=128,
        sequence_length=8,
        batch_size=2,
        model_width=16,
        attention_heads=2,
        layers=1,
        feed_forward_width=32,
        warmup_iterations=1,
        measured_iterations=2,
    )


def test_cpu_benchmark_is_reproducible_and_reports_performance() -> None:
    first = benchmark_devices(_tiny_config(), ("cpu",))
    second = benchmark_devices(_tiny_config(), ("cpu",))

    result = first["results"][0]
    assert result["median_latency_ms"] > 0
    assert result["p95_latency_ms"] >= result["median_latency_ms"]
    assert result["tokens_per_second"] > 0
    assert result["model_parameter_bytes"] > 0
    assert result["max_abs_error_vs_cpu"] == 0
    assert result["speedup_vs_cpu"] == 1
    assert result["output_checksum"] == second["results"][0]["output_checksum"]


def test_rejects_unavailable_device() -> None:
    with pytest.raises(ValueError, match="unavailable benchmark devices"):
        benchmark_devices(_tiny_config(), ("not-a-device",))


def test_cli_writes_json_report(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    output_path = tmp_path / "report.json"

    main(
        [
            "--devices",
            "cpu",
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--output",
            str(output_path),
        ]
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert file_payload["results"][0]["device"] == "cpu"


@pytest.mark.skipif(not torch.backends.mps.is_available(), reason="MPS is unavailable")
def test_mps_output_matches_cpu_reference() -> None:
    report = benchmark_devices(_tiny_config(), ("cpu", "mps"))
    mps_result = report["results"][1]

    assert mps_result["max_abs_error_vs_cpu"] < 1e-4
    assert mps_result["accelerator_allocated_bytes"] > 0
    assert mps_result["speedup_vs_cpu"] > 0
