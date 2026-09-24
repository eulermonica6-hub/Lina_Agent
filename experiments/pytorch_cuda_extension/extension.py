from pathlib import Path

import torch
from torch import Tensor
from torch.utils.cpp_extension import load

from .environment import require_cuda_environment

_EXTENSION_LOADED = False
_EXPERIMENT_ROOT = Path(__file__).parent
_BUILD_DIRECTORY = _EXPERIMENT_ROOT / ".build"


def load_rms_norm_cuda_extension(*, verbose: bool = False) -> None:
    global _EXTENSION_LOADED
    if _EXTENSION_LOADED:
        return
    require_cuda_environment()
    _BUILD_DIRECTORY.mkdir(exist_ok=True)
    load(
        name="lina_rms_norm_cuda",
        sources=[
            str(_EXPERIMENT_ROOT / "binding.cpp"),
            str(_EXPERIMENT_ROOT / "rms_norm_cuda.cu"),
        ],
        extra_cflags=["-O3"],
        extra_cuda_cflags=["-O3", "--use_fast_math"],
        build_directory=str(_BUILD_DIRECTORY),
        with_cuda=True,
        is_python_module=False,
        verbose=verbose,
    )
    _EXTENSION_LOADED = True


def rms_norm_reference(input_tensor: Tensor, weight: Tensor, epsilon: float = 1e-6) -> Tensor:
    inverse_rms = torch.rsqrt(input_tensor.square().mean(dim=-1, keepdim=True) + epsilon)
    return input_tensor * inverse_rms * weight


def rms_norm_cuda(input_tensor: Tensor, weight: Tensor, epsilon: float = 1e-6) -> Tensor:
    load_rms_norm_cuda_extension()
    return torch.ops.lina_rms_norm_cuda.forward.default(input_tensor, weight, epsilon)
