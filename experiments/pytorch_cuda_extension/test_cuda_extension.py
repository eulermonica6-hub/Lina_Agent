import pytest
import torch

from .environment import cuda_environment
from .extension import rms_norm_cuda, rms_norm_reference

_CUDA_READY = bool(cuda_environment()["ready"])
pytestmark = pytest.mark.skipif(not _CUDA_READY, reason="CUDA build/runtime is unavailable")


@pytest.mark.parametrize("shape", ((2, 16), (4, 32, 64), (512, 1024)))
def test_cuda_rms_norm_matches_pytorch_reference(shape: tuple[int, ...]) -> None:
    generator = torch.Generator().manual_seed(20260924)
    cpu_input = torch.randn(shape, generator=generator, dtype=torch.float32)
    cpu_weight = torch.randn(shape[-1], generator=generator, dtype=torch.float32)
    input_tensor = cpu_input.cuda()
    weight = cpu_weight.cuda()

    expected = rms_norm_reference(input_tensor, weight)
    actual = rms_norm_cuda(input_tensor, weight)

    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-5)


def test_cuda_rms_norm_supports_non_contiguous_input() -> None:
    input_tensor = torch.randn(4, 8, device="cuda").transpose(0, 1)
    weight = torch.ones(4, device="cuda")

    actual = rms_norm_cuda(input_tensor, weight)

    torch.testing.assert_close(actual, rms_norm_reference(input_tensor, weight))
    assert actual.shape == input_tensor.shape


def test_cuda_rms_norm_rejects_invalid_weight_shape() -> None:
    with pytest.raises(RuntimeError, match="weight length"):
        rms_norm_cuda(torch.randn(2, 8, device="cuda"), torch.ones(7, device="cuda"))
