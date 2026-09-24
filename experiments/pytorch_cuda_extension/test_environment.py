from pathlib import Path

from .environment import cuda_environment


def test_cuda_environment_probe_is_actionable() -> None:
    environment = cuda_environment()

    assert isinstance(environment["ready"], bool)
    assert isinstance(environment["reasons"], list)
    if not environment["ready"]:
        assert environment["reasons"]


def test_cuda_source_contract_is_present() -> None:
    root = Path(__file__).parent
    kernel = (root / "rms_norm_cuda.cu").read_text(encoding="utf-8")
    binding = (root / "binding.cpp").read_text(encoding="utf-8")

    assert "__global__ void rms_norm_kernel" in kernel
    assert "C10_CUDA_KERNEL_LAUNCH_CHECK" in kernel
    assert "input must be a CUDA tensor" in kernel
    assert "TORCH_LIBRARY_IMPL(lina_rms_norm_cuda, CUDA" in binding
