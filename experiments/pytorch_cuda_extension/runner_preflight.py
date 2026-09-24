import argparse
import json
import platform
import shutil
import subprocess
from typing import Any

from .environment import cuda_environment

_MINIMUM_FREE_GIB = 20.0
_REQUIRED_TOOLS = ("git", "c++", "ninja")


def runner_preflight() -> dict[str, Any]:
    reasons: list[str] = []
    system = platform.system()
    machine = platform.machine()
    if system != "Linux":
        reasons.append(f"runner must use Linux, found {system}")
    if machine not in {"x86_64", "AMD64"}:
        reasons.append(f"runner must use x86_64, found {machine}")

    tools = {
        name: {
            "path": executable,
            "version": _tool_version(executable),
        }
        for name in _REQUIRED_TOOLS
        if (executable := shutil.which(name)) is not None
    }
    missing_tools = tuple(name for name in _REQUIRED_TOOLS if name not in tools)
    if missing_tools:
        reasons.append("missing required tools: " + ", ".join(missing_tools))

    free_gib = shutil.disk_usage(".").free / 1024**3
    if free_gib < _MINIMUM_FREE_GIB:
        reasons.append(
            f"runner needs at least {_MINIMUM_FREE_GIB:.0f} GiB free, found {free_gib:.1f} GiB"
        )

    cuda = cuda_environment()
    reasons.extend(f"CUDA: {reason}" for reason in cuda["reasons"])
    return {
        "ready": not reasons,
        "system": system,
        "machine": machine,
        "free_gib": free_gib,
        "minimum_free_gib": _MINIMUM_FREE_GIB,
        "tools": tools,
        "cuda": cuda,
        "reasons": reasons,
    }


def _tool_version(executable: str) -> str | None:
    completed = subprocess.run(
        [executable, "--version"],
        check=False,
        capture_output=True,
        text=True,
    )
    output = completed.stdout or completed.stderr
    return output.splitlines()[0] if output else None


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Validate a Lina CUDA self-hosted runner.")
    parser.add_argument("--require-ready", action="store_true")
    parsed = parser.parse_args(arguments)
    report = runner_preflight()
    print(json.dumps(report, indent=2))
    if parsed.require_ready and not report["ready"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
