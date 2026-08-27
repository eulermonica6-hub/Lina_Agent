# Lina 0.2.0 发布测试操作手册

> 适用版本：`0.2.0`
> 核心范围：多节点缺口分析、LLM 计划、确定性复核和失败降级
> 展示边界：Web 工作台不新增文件上传或计划展示

## 1. 准备独立 Windows 环境

Windows 与 WSL 不应共用虚拟环境：

```powershell
$root = (Resolve-Path ".").Path
$env:UV_PROJECT_ENVIRONMENT = Join-Path $root ".venv-windows"
$env:UV_CACHE_DIR = Join-Path $root ".uv-cache-windows"
uv sync --extra dev --locked
uv run --locked playwright install chromium
```

后续命令在同一 PowerShell 终端执行。WSL 应使用 `.venv-wsl` 和 `.uv-cache-wsl`。

## 2. 验证版本与 Git 同步

```powershell
git rev-parse HEAD
git rev-parse origin/main
uv run --locked python -c "import lina_agent; print(lina_agent.__version__)"
```

预期：前两个 SHA 相同，运行时版本为 `0.2.0`。

## 3. 执行完整工程门禁

```powershell
uv lock --check
uv run --extra dev --locked ruff format --check .
uv run --extra dev --locked ruff check .
uv run --extra dev --locked pyright
uv run --extra dev --locked pytest `
  --browser chromium `
  --tracing=retain-on-failure `
  --cov=lina_agent `
  --cov-branch `
  --cov-report=term-missing `
  --cov-fail-under=100
```

0.2.0 基线：

- 100 个测试通过；
- 1076 条语句、154 个分支全部覆盖；
- 语句与分支覆盖率均为 100%；
- Pyright strict 为 0 errors；
- 8 个 Chromium Playwright 异步竞态场景通过。

## 4. 验证默认确定性主路径

```powershell
uv run --locked lina-match `
  --resume tests/fixtures/resume_anonymized.md `
  --jobs tests/fixtures/job_catalog_anonymized.md `
  --top 2 `
  --format json
```

验收点：

- `state=complete`；
- 2 个岗位、1 个参与排序、1 个下线岗位被排除；
- Top-1 为匿名 Agent 工程师，覆盖分为 80；
- `gap_analysis` 包含 LangGraph 优先缺口，`priority_score=35.0`；
- Trace 包含 `gap_analyst`；
- `action_plan=null`，因为默认不调用模型。

## 5. 验证真实 DOCX 的本地路径

```powershell
uv run --locked lina-match `
  --resume "data/private/简历_研1.docx" `
  --jobs "data/private/AI_Agent_JD.md" `
  --top 5 `
  --format json
```

验收点：

- 状态为 `complete`；
- 简历读取 42 个证据块并识别候选人技能；
- JD 解析 29 个岗位，默认 28 个参与排序；
- 返回 Top-5 与聚合能力缺口；
- 不产生私有输出文件，不调用 LLM。

## 6. 验证真实匿名 LLM 计划

```powershell
uv run --locked lina-match `
  --resume tests/fixtures/resume_anonymized.md `
  --jobs tests/fixtures/job_catalog_anonymized.md `
  --top 2 `
  --use-llm `
  --format json
```

验收点：

- `state=complete`；
- `action_plan` 非空；
- 每项行动包含 `target_skills`、`deliverable`、`acceptance_criteria` 和 `time_budget_hours`；
- `action_plan_review.status=verified`；
- `generate_action_plan` 和 `verify_action_plan` 均为 `complete`；
- `total_tokens` 大于 0。

发布探针实际使用 Groq `qwen/qwen3.6-27b`，生成 3 项行动并通过复核。Provider、模型和 Token 会随路由与模型响应变化，不应写成固定断言。

## 7. 验证降级而不是整次失败

自动化用例：

```powershell
uv run --extra dev --locked pytest `
  tests/application/test_career_agent.py `
  tests/infrastructure/test_llm_career_planner.py `
  -q
```

它覆盖：

- Provider 网络错误转为安全的 Planner 错误；
- 坏 JSON 和 Schema 不合格；
- 无证据技能、重复任务和不连续优先级被 Reviewer 拒绝；
- 运行返回 `degraded`，但 Top-K 和 `gap_analysis` 仍然保留；
- 没有匹配结果时 Planner 为 `skipped`，不会调用模型。

## 8. 验证 API opt-in

启动服务：

```powershell
uv run --locked uvicorn lina_agent.main:app --app-dir src --port 8001
```

检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8001/health
$schema = Invoke-RestMethod http://127.0.0.1:8001/openapi.json
$schema.components.schemas.CareerAgentRequest.properties.use_llm
```

预期健康版本为 `0.2.0`，OpenAPI 中 `use_llm` 是默认 `false` 的布尔值。

`POST /agent/runs` 的两个文件仍使用 Base64。请求不包含 `use_llm` 或设置为 `false` 时完全本地运行；只有显式设置为 `true` 才调用模型。

## 9. 理解 Web 展示边界

- <http://127.0.0.1:8001/> 仍是原有手工画像/JD 工作台；
- 页面左上角版本徽标应显示 `v0.2.0`；
- 新增缺口、计划和 Reviewer 结果目前在 CLI、JSON API 和 `/docs` 中验证；
- 首页没有文件上传并非同步或缓存错误，而是本轮主动后置前端包装。

## 10. 发布清单

- [ ] `HEAD` 与 `origin/main` 一致；
- [ ] 运行时、`pyproject.toml`、`uv.lock`、页面徽标和 Release Notes 均为 0.2.0；
- [ ] Ruff、Pyright、pytest、Playwright 和 100% 覆盖率通过；
- [ ] 默认路径完全本地；
- [ ] 匿名 LLM 路径生成正式计划并通过 Reviewer；
- [ ] 模型失败路径保留 Top-K 与缺口分析；
- [ ] 真实 DOCX 不离开本机；
- [ ] Git 状态不包含私有简历、key、Trace 或临时诊断脚本。

完成以上步骤后，才可以声称 0.2.0 的 Agent 核心通过发布验收。下一阶段优先建立匿名 Gold Set 与持久化，不先重做前端。
