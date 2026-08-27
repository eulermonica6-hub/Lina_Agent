# Lina 0.1.2 发布测试操作手册

> 功能基线提交：`f3bde29`（`Expand economic provider failover`）及其后的 0.1.2 文档/测试增强提交
> 适用版本：`0.1.2`
> 测试平台：Windows 11；CI 同时覆盖 Windows 与 Ubuntu

## 1. 先理解本版本在哪里可见

0.1.2 包含两个产品入口，能力并不相同：

| 入口 | 当前能力 | 是否展示文件 Agent |
| --- | --- | --- |
| Web 首页 `/` | 原有画像、单条 JD 硬条件提取和匹配 | 否 |
| OpenAPI `/docs` | 原有接口和 `POST /agent/runs` | 是 |
| CLI `lina-match` | DOCX/TXT/Markdown、Top-K、Trace、可选模型计划 | 是 |

因此，首页仍显示旧工作台不代表 GitHub 未同步。判断新版本是否运行，应同时检查 `/health` 的版本和 OpenAPI 中是否存在 `/agent/runs`。

GitHub 当前是 `main` 分支代码发布，没有创建 `v0.1.2` tag、GitHub Release、GitHub Pages 或在线部署。`http://127.0.0.1:8001/` 是本机 Uvicorn 服务，不由 GitHub 托管。

## 2. 准备测试环境

在项目根目录执行：

```powershell
$root = (Resolve-Path ".").Path
$env:UV_PROJECT_ENVIRONMENT = Join-Path $root ".venv-windows"
$env:UV_CACHE_DIR = Join-Path $root ".uv-cache-windows"
uv sync --extra dev --locked
uv run --locked playwright install chromium
```

作用：

- `--locked` 保证严格使用 `uv.lock`，避免测试机临时解析出不同版本；
- 安装 Chromium 是运行 8 个真实浏览器竞态测试的前提；
- 环境变量只对当前 PowerShell 终端生效，后续测试命令应在同一终端执行；
- `.venv` 不能在 Windows 和 WSL 间共用。这里显式使用 `.venv-windows`；WSL 应改用 `.venv-wsl` 和 `.uv-cache-wsl`。

如果出现 `.venv/lib64` 拒绝访问，通常是 Windows 正在接触 WSL 创建的虚拟环境。不要让 `uv` 修复或覆盖该目录，确认已设置上述 `UV_PROJECT_ENVIRONMENT` 后重新执行。

## 3. 验证代码与版本同步

```powershell
git rev-parse HEAD
git rev-parse origin/main
git merge-base --is-ancestor f3bde29 HEAD
$LASTEXITCODE
uv run --locked python -c "import lina_agent; print(lina_agent.__version__)"
```

预期：前两个完整 SHA 完全相同；`git merge-base` 的退出码为 `0`；运行时版本为 `0.1.2`。例如功能基线刚发布时的输出为：

```text
f3bde29d0b5bedb7d9addb6f681257ae919adc54
f3bde29d0b5bedb7d9addb6f681257ae919adc54
0
0.1.2
```

如果 `origin/main` 不是最新值，先执行 `git fetch origin` 再比较。私有仓库不会被公共搜索引擎稳定索引，不能用搜索结果判断是否同步。

## 4. 运行工程静态门禁

依次执行，不要只运行最后一条：

```powershell
uv lock --check
uv run --extra dev --locked ruff format --check .
uv run --extra dev --locked ruff check .
uv run --extra dev --locked pyright
git diff --check
```

预期：

- 锁文件无需更新；
- Ruff 没有格式或 lint 错误；
- Pyright strict 为 `0 errors`；
- Git 没有尾随空格或冲突标记。

## 5. 运行完整自动化测试

```powershell
uv run --extra dev --locked pytest `
  --browser chromium `
  --tracing=retain-on-failure `
  --cov=lina_agent `
  --cov-branch `
  --cov-report=term-missing `
  --cov-fail-under=100
```

0.1.2 发布基线：

- 88 个测试通过；
- 906 条 Python 语句全部覆盖；
- 114 个分支全部覆盖；
- 语句和分支覆盖率均为 100%；
- 8 个 Playwright 场景验证候选人保存、岗位保存、抽取和匹配的旧成功/失败响应不能覆盖新状态。

失败时查看 `test-results/` 中保留的 Playwright Trace。

## 6. 启动并验证 8001 服务

先停止旧 Uvicorn 进程，再从当前仓库启动：

```powershell
uv run --locked uvicorn lina_agent.main:app --app-dir src --port 8001
```

另开终端执行：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
$schema = Invoke-RestMethod http://127.0.0.1:8001/openapi.json
$null -ne $schema.paths.'/agent/runs'
```

预期：

```text
status  service            version
------  -------            -------
ok      Lina Career Agent  0.1.2

True
```

浏览器检查：

- <http://127.0.0.1:8001/> 左上角显示 `v0.1.2`；
- <http://127.0.0.1:8001/docs> 显示 `POST /agent/runs`；
- 首页仍是原有手工画像工作台，这是当前设计边界，不是缓存错误。

如果 `/health` 是旧版本，说明旧进程没有停止；如果版本正确但没有 `/agent/runs`，检查启动命令是否包含 `--app-dir src`。

## 7. 验证公开匿名 CLI 主路径

```powershell
uv run --locked lina-match `
  --resume tests/fixtures/resume_anonymized.md `
  --jobs tests/fixtures/job_catalog_anonymized.md `
  --top 2
```

预期关键结果：

- 状态为 `complete`；
- 识别出 Agent、RAG、Python、SQL 等技能；
- 共 2 个岗位、1 个参与排序；
- Top-1 为“Agent 工程师 | 示例科技”；
- 证据覆盖分为 `80.0`；
- 默认排除 1 个下线岗位。

该分数是当前词表证据覆盖度，不是录取概率。

## 8. 验证真实文件的本地确定性路径

以下命令不会调用模型：

```powershell
uv run --locked lina-match `
  --resume "data/private/简历_研1.docx" `
  --jobs "data/private/AI_Agent_JD.md" `
  --top 5
```

验收点：

- DOCX 不为空且生成候选人技能；
- JD 解析为 29 个岗位；
- 默认 28 个岗位参与排序；
- 报告包含 Top-K、明确技能覆盖与缺口；
- `data/private/` 中没有新增输出文件，`git status` 不出现简历或 key。

发布验证中 7/7 份真实 DOCX 均解析成功，每份得到 42–104 个证据块。

## 9. 验证文件 Agent API

在服务运行时执行：

```powershell
$resumePath = Resolve-Path "tests/fixtures/resume_anonymized.md"
$jobsPath = Resolve-Path "tests/fixtures/job_catalog_anonymized.md"

$body = @{
  resume = @{
    filename = (Split-Path -Leaf $resumePath.Path)
    content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($resumePath.Path))
  }
  job_catalog = @{
    filename = (Split-Path -Leaf $jobsPath.Path)
    content = [Convert]::ToBase64String([IO.File]::ReadAllBytes($jobsPath.Path))
  }
  top_k = 2
  include_inactive = $false
} | ConvertTo-Json -Depth 5

$run = Invoke-RestMethod `
  -Uri http://127.0.0.1:8001/agent/runs `
  -Method Post `
  -ContentType 'application/json' `
  -Body $body

$run | Select-Object state,total_jobs,considered_jobs,excluded_inactive_jobs
$run.steps | Select-Object name,summary
```

预期：`state=complete`、`total_jobs=2`、`considered_jobs=1`、`excluded_inactive_jobs=1`，并返回摄取、抽取、目录解析和排序步骤。

API 使用 Base64 而不是服务端文件路径，避免任意路径读取。当前 `/agent/runs` 不调用 LLM。

## 10. 验证 Provider 配置但不输出 key

```powershell
uv run --locked python -c "from collections import Counter; from lina_agent.infrastructure.llm_provider import resolve_provider_configs; c=resolve_provider_configs(); print(Counter(x.provider.value for x in c)); print([(x.provider.value,x.model,x.cost_tier) for x in c if x.provider.value!='groq'])"
```

本机当前预期：

- 10 个 Groq 配置；
- 1 个 Agnes `agnes-2.5-flash`；
- 1 个 NVIDIA；
- 本机 `.env` 已授权时，最后包含 1 个付费 DeepSeek。

禁止打印 `api_key`、`model_dump()` 的未审查结果或完整 key 文件。

Provider 聚焦测试：

```powershell
uv run --extra dev --locked pytest tests/infrastructure/test_llm_provider.py -q
```

它覆盖多 Groq key 去重与顺序、Agnes、付费开关、401/403、429、网络失败、无效响应、5xx 降级和 400 立即失败。

## 11. 验证智能行动计划

先使用匿名 Fixture：

```powershell
uv run --locked lina-match `
  --resume tests/fixtures/resume_anonymized.md `
  --jobs tests/fixtures/job_catalog_anonymized.md `
  --top 2 `
  --use-llm
```

预期报告新增“智能行动计划”，Trace 新增 `generate_action_plan`。

`--use-llm` 会把候选人技能标签、Top 岗位标题/公司、覆盖项和缺口发送给外部 Provider，但不会发送文件名、联系方式或简历原句。对真实简历运行前，必须确认接受这些派生数据外传。

DeepSeek 是付费 Provider。仓库默认不自动启用；本机只有在 `.env` 明确设置 `LINA_LLM_ALLOW_PAID_FALLBACK=true` 后才作为最终回退。

## 12. 失败路径抽查

至少抽查以下情况：

1. 将 `.pdf` 作为简历：应返回“不支持的文档类型”，不能静默读取；
2. 使用损坏 DOCX：应返回“不是可解析的 DOCX”；
3. 使用空 TXT/DOCX：应返回“没有可读取的文本”；
4. JD 没有受支持的岗位标题：应明确报错；
5. 所有岗位均下线：匹配列表为空，并解释跳过智能计划；
6. Provider 返回 400：立即失败；返回 401/403/429 或可重试 5xx：尝试下一配置。

这些路径已自动化，不应为了演示成功而吞掉异常。

## 13. 发布验收清单

- [ ] 本地 `HEAD`、`origin/main` 和发布提交一致；
- [ ] 运行时、`pyproject.toml`、页面徽标和 Release Notes 都是 0.1.2；
- [ ] `uv lock --check` 通过；
- [ ] Ruff、Pyright、pytest、Playwright 和 100% 覆盖率通过；
- [ ] 首页旧工作台仍可用；
- [ ] `/docs` 中存在 `/agent/runs`；
- [ ] 匿名 CLI 和 API 主路径通过；
- [ ] 真实 DOCX 只在本地确定性路径处理；
- [ ] Provider 测试不输出 key，DeepSeek 付费行为已明确；
- [ ] `git status` 里没有私有简历、key、Trace 或临时代理脚本。

完成以上步骤，才可以声称 0.1.2 代码版本通过发布验收。首页文件上传与智能计划可视化属于下一项前端开发，不属于本版本已交付能力。
