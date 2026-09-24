import argparse
import json
import platform
import statistics
from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any

import torch
from torch import Tensor, nn


@dataclass(frozen=True)
class BenchmarkConfig:
    vocab_size: int = 4096
    sequence_length: int = 128
    batch_size: int = 4
    model_width: int = 128
    attention_heads: int = 4
    layers: int = 2
    feed_forward_width: int = 256
    warmup_iterations: int = 3
    measured_iterations: int = 10
    seed: int = 20260924


class TinyCausalDecoder(nn.Module):
    def __init__(self, config: BenchmarkConfig) -> None:
        super().__init__()
        self.token_embedding = nn.Embedding(config.vocab_size, config.model_width)
        self.position_embedding = nn.Embedding(config.sequence_length, config.model_width)
        layer = nn.TransformerEncoderLayer(
            d_model=config.model_width,
            nhead=config.attention_heads,
            dim_feedforward=config.feed_forward_width,
            dropout=0.0,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.decoder = nn.TransformerEncoder(
            layer,
            num_layers=config.layers,
            enable_nested_tensor=False,
        )
        self.output = nn.Linear(config.model_width, config.vocab_size, bias=False)

    def forward(self, token_ids: Tensor) -> Tensor:
        sequence_length = token_ids.shape[1]
        positions = torch.arange(sequence_length, device=token_ids.device)
        hidden = self.token_embedding(token_ids) + self.position_embedding(positions)
        causal_mask = torch.triu(
            torch.ones(
                sequence_length,
                sequence_length,
                dtype=torch.bool,
                device=token_ids.device,
            ),
            diagonal=1,
        )
        return self.output(self.decoder(hidden, mask=causal_mask))


def available_devices() -> tuple[str, ...]:
    devices = ["cpu"]
    if torch.backends.mps.is_available():
        devices.append("mps")
    if torch.cuda.is_available():
        devices.append("cuda")
    return tuple(devices)


def synchronize(device: str) -> None:
    if device == "mps":
        torch.mps.synchronize()
    elif device == "cuda":
        torch.cuda.synchronize()


def benchmark_devices(
    config: BenchmarkConfig,
    devices: tuple[str, ...],
) -> dict[str, Any]:
    if not devices:
        raise ValueError("at least one benchmark device is required")
    unsupported = tuple(device for device in devices if device not in available_devices())
    if unsupported:
        raise ValueError(f"unavailable benchmark devices: {', '.join(unsupported)}")

    torch.manual_seed(config.seed)
    reference_model = TinyCausalDecoder(config).eval()
    state = reference_model.state_dict()
    token_ids = torch.randint(
        config.vocab_size,
        (config.batch_size, config.sequence_length),
        generator=torch.Generator().manual_seed(config.seed),
    )

    results: list[dict[str, Any]] = []
    outputs: dict[str, Tensor] = {}
    for device in devices:
        result, output = _benchmark_device(config, state, token_ids, device)
        results.append(result)
        outputs[device] = output

    reference_device = "cpu" if "cpu" in outputs else devices[0]
    reference_output = outputs[reference_device]
    for result in results:
        output = outputs[str(result["device"])]
        result["max_abs_error_vs_cpu"] = float((output - reference_output).abs().max().item())

    cpu_result = next((result for result in results if result["device"] == "cpu"), None)
    if cpu_result is not None:
        cpu_latency = float(cpu_result["median_latency_ms"])
        for result in results:
            result["speedup_vs_cpu"] = cpu_latency / float(result["median_latency_ms"])

    return {
        "environment": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "torch": torch.__version__,
            "mps_built": torch.backends.mps.is_built(),
            "mps_available": torch.backends.mps.is_available(),
            "cuda_available": torch.cuda.is_available(),
        },
        "config": asdict(config),
        "results": results,
    }


def _benchmark_device(
    config: BenchmarkConfig,
    state: dict[str, Tensor],
    token_ids: Tensor,
    device: str,
) -> tuple[dict[str, Any], Tensor]:
    model = TinyCausalDecoder(config).to(device).eval()
    model.load_state_dict(state)
    device_tokens = token_ids.to(device)

    with torch.inference_mode():
        for _ in range(config.warmup_iterations):
            model(device_tokens)
        synchronize(device)

        latencies_ms: list[float] = []
        output = model(device_tokens)
        for _ in range(config.measured_iterations):
            synchronize(device)
            started = perf_counter()
            output = model(device_tokens)
            synchronize(device)
            latencies_ms.append((perf_counter() - started) * 1000)

    output_cpu = output.float().cpu()
    median_latency_ms = statistics.median(latencies_ms)
    p95_latency_ms = _percentile(latencies_ms, 0.95)
    tokens_per_second = config.batch_size * config.sequence_length / (median_latency_ms / 1000)
    parameter_bytes = sum(
        parameter.numel() * parameter.element_size() for parameter in model.parameters()
    )
    result = {
        "device": device,
        "median_latency_ms": median_latency_ms,
        "p95_latency_ms": p95_latency_ms,
        "tokens_per_second": tokens_per_second,
        "model_parameter_bytes": parameter_bytes,
        "input_bytes": device_tokens.numel() * device_tokens.element_size(),
        "output_bytes": output.numel() * output.element_size(),
        "accelerator_allocated_bytes": _accelerator_allocated_bytes(device),
        "output_checksum": float(output_cpu.mean().item()),
    }
    return result, output_cpu


def _percentile(values: list[float], percentile: float) -> float:
    ordered = sorted(values)
    index = min(round((len(ordered) - 1) * percentile), len(ordered) - 1)
    return ordered[index]


def _accelerator_allocated_bytes(device: str) -> int | None:
    if device == "mps":
        return torch.mps.current_allocated_memory()
    if device == "cuda":
        return torch.cuda.memory_allocated()
    return None


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Benchmark a tiny causal PyTorch decoder.")
    parser.add_argument(
        "--devices",
        nargs="+",
        default=["auto"],
        choices=("auto", "cpu", "mps", "cuda"),
    )
    parser.add_argument("--iterations", type=int, default=10)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--output", type=str)
    parsed = parser.parse_args(arguments)
    if parsed.iterations < 1 or parsed.warmup < 0:
        parser.error("iterations must be positive and warmup must be non-negative")
    devices = available_devices() if parsed.devices == ["auto"] else tuple(parsed.devices)
    config = BenchmarkConfig(
        measured_iterations=parsed.iterations,
        warmup_iterations=parsed.warmup,
    )
    report = benchmark_devices(config, devices)
    payload = json.dumps(report, indent=2)
    if parsed.output:
        with open(parsed.output, "w", encoding="utf-8") as output_file:
            output_file.write(f"{payload}\n")
    print(payload)


if __name__ == "__main__":
    main()
