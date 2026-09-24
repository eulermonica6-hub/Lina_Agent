# CUDA Self-Hosted Runner Setup

This guide provisions the external NVIDIA environment required by the `CUDA Benchmark` workflow. Registration credentials are short-lived secrets: enter them directly on the GPU host, never place them in repository files, chat, screenshots, shell history, or benchmark artifacts.

## 1. Host Requirements

- Linux x86_64;
- NVIDIA GPU and a compatible driver;
- CUDA Toolkit with `nvcc`;
- at least 20 GiB free disk;
- Git, a C++ compiler, Python 3.12, uv, and outbound HTTPS access;
- a dedicated non-root OS account for the runner.

A cloud VM, dedicated workstation, or controlled lab server is acceptable. Do not register an untrusted shared machine because self-hosted runners execute repository workflow code.

## 2. Register The Runner

1. Open the repository on GitHub.
2. Go to **Settings → Actions → Runners → New self-hosted runner**.
3. Select Linux and x64.
4. Run GitHub's generated download and verification commands directly on the GPU host.
5. Run the generated `config.sh` command with these additional labels:

```text
gpu,cuda
```

The final runner labels must include:

```text
self-hosted, linux, x64, gpu, cuda
```

Use the ephemeral registration token only in the GPU host terminal. After registration, configure the runner as a service using GitHub's generated service commands.

## 3. Prepare The Repository

On the GPU host, use the runner account:

```bash
git clone <repository-url>
cd Lina_Agent
uv sync --extra dev --extra inference --locked
```

The Linux PyTorch wheel must be a CUDA build. Installing a CPU-only wheel will make preflight fail.

## 4. Run Preflight

```bash
uv run --extra inference --locked python \
  -m experiments.pytorch_cuda_extension.runner_preflight \
  --require-ready
```

A ready host reports:

- `system=Linux`, `machine=x86_64`;
- Git, C++, and Ninja paths and versions;
- CUDA-enabled PyTorch;
- `torch.cuda.is_available()=true` and at least one device;
- CUDA home, NVCC, and `nvidia-smi`;
- at least 20 GiB free disk;
- an empty `reasons` list.

Do not bypass a failed preflight. Fix the host, driver, CUDA Toolkit, or PyTorch build first.

## 5. Trigger The Workflow

In GitHub, open **Actions → CUDA Benchmark → Run workflow** on `main`.

The workflow:

1. syncs locked `dev` and `inference` dependencies;
2. runs preflight with `--require-ready`;
3. compiles the CUDA extension with NVCC;
4. runs correctness and boundary tests;
5. runs the synchronized benchmark;
6. uploads `pytorch-cuda-rms-norm.json`.

## 6. Acceptance Criteria

The GPU artifact is accepted only when:

- all CUDA tests execute rather than skip;
- maximum error versus PyTorch CUDA reference is at most `1e-5`;
- the report includes GPU model, compute capability, PyTorch/CUDA/NVCC versions;
- median and p95 latency, rows/s, memory, and speedup are present;
- the workflow commit matches the commit recorded with the artifact.

The custom kernel does not need to outperform PyTorch. A slower result is valid evidence when its shape, launch overhead, and bottleneck analysis are recorded.

## 7. Security And Cleanup

- restrict runner access to this repository;
- use a dedicated account without unrelated credentials;
- do not run pull requests from untrusted forks on the runner;
- keep driver and OS security updates current;
- remove the runner from GitHub and delete its work directory when the experiment ends;
- never upload private resumes, raw JD snapshots, API keys, registration tokens, or runner diagnostics containing secrets.
