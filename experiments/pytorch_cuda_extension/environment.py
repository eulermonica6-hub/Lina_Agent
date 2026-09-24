import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import torch
from torch.utils.cpp_extension import CUDA_HOME


def cuda_environment() -> dict[str, Any]:
    nvcc = _nvcc_path()
    nvidia_smi = shutil.which("nvidia-smi")
    reasons: list[str] = []
    if torch.version.cuda is None:
        reasons.append("installed PyTorch is not a CUDA build")
    if not torch.cuda.is_available():
        reasons.append("torch.cuda.is_available() is false")
    if nvcc is None:
        reasons.append("nvcc was not found")
    return {
        "ready": not reasons,
        "torch": torch.__version__,
        "torch_cuda_version": torch.version.cuda,
        "cuda_available": torch.cuda.is_available(),
        "device_count": torch.cuda.device_count(),
        "cuda_home": None if CUDA_HOME is None else str(CUDA_HOME),
        "nvcc": nvcc,
        "nvcc_version": _first_version_line(nvcc),
        "nvidia_smi": nvidia_smi,
        "nvidia_smi_version": _first_version_line(nvidia_smi),
        "reasons": reasons,
    }


def require_cuda_environment() -> None:
    environment = cuda_environment()
    if not environment["ready"]:
        raise RuntimeError("CUDA environment is not ready: " + "; ".join(environment["reasons"]))


def _nvcc_path() -> str | None:
    if CUDA_HOME is not None:
        candidate = Path(CUDA_HOME) / "bin" / "nvcc"
        if candidate.is_file():
            return str(candidate)
    return shutil.which("nvcc")


def _first_version_line(executable: str | None) -> str | None:
    if executable is None:
        return None
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout or completed.stderr
    return output.splitlines()[0] if output else None


def main() -> None:
    print(json.dumps(cuda_environment(), indent=2))


if __name__ == "__main__":
    main()
