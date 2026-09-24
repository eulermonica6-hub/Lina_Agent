import pytest
import torch

from .extension import rms_norm_cpp, rms_norm_reference


@pytest.mark.parametrize("shape", ((2, 16), (4, 32, 64), (2, 8, 128)))
def test_cpp_rms_norm_matches_python_reference(shape: tuple[int, ...]) -> None:
    generator = torch.Generator().manual_seed(20260924)
    input_tensor = torch.randn(shape, generator=generator, dtype=torch.float32)
    weight = torch.randn(shape[-1], generator=generator, dtype=torch.float32)

    expected = rms_norm_reference(input_tensor, weight)
    actual = rms_norm_cpp(input_tensor, weight)

    torch.testing.assert_close(actual, expected, rtol=1e-5, atol=1e-6)


def test_cpp_rms_norm_supports_non_contiguous_input() -> None:
    input_tensor = torch.randn(4, 8, dtype=torch.float32).transpose(0, 1)
    weight = torch.ones(4, dtype=torch.float32)

    actual = rms_norm_cpp(input_tensor, weight)

    torch.testing.assert_close(actual, rms_norm_reference(input_tensor, weight))
    assert actual.shape == input_tensor.shape


def test_cpp_rms_norm_rejects_invalid_weight_shape() -> None:
    with pytest.raises(RuntimeError, match="weight length"):
        rms_norm_cpp(torch.randn(2, 8), torch.ones(7))
