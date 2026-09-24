import json

import pytest

from .benchmark import benchmark_rms_norm, main


def test_rms_norm_benchmark_reports_error_and_latency() -> None:
    report = benchmark_rms_norm(
        rows=8,
        hidden_size=16,
        warmup_iterations=1,
        measured_iterations=2,
    )

    assert report["max_abs_error"] < 1e-5
    assert [result["implementation"] for result in report["results"]] == [
        "python_reference",
        "cpp_extension",
    ]
    assert all(result["median_latency_ms"] > 0 for result in report["results"])
    assert report["results"][1]["speedup_vs_python"] > 0


def test_benchmark_rejects_invalid_shape() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        benchmark_rms_norm(rows=0)


def test_benchmark_cli_writes_json(tmp_path, capsys: pytest.CaptureFixture[str]) -> None:
    output_path = tmp_path / "cpp-report.json"

    main(
        [
            "--rows",
            "8",
            "--hidden-size",
            "16",
            "--iterations",
            "1",
            "--warmup",
            "0",
            "--output",
            str(output_path),
        ]
    )

    stdout_payload = json.loads(capsys.readouterr().out)
    assert stdout_payload == json.loads(output_path.read_text(encoding="utf-8"))
