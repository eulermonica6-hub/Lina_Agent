# Lina 功能、操作与技术说明

> 适用版本：0.2.45  
> 验证日期：2026-11-10  
> 本文说明当前代码实际提供的能力，不将规划功能描述为已实现功能。

## 1. 快速启动

在仓库根目录执行：

```powershell
uv sync --extra dev --locked
uv run --extra dev --locked uvicorn lina_agent.main:app --app-dir src --host 127.0.0.1 --port 8000
```

访问：

| 地址 | 用途 |
| --- | --- |
| `http://127.0.0.1:8000/` | 机会首页 |
| `http://127.0.0.1:8000/workbench` | 结构化决策工作台 |
| `http://127.0.0.1:8000/inbox` | 岗位变化 Inbox |
| `http://127.0.0.1:8000/docs` | FastAPI 交互式 API 文档 |
| `http://127.0.0.1:8000/health` | 服务健康检查 |

默认使用本地 SQLite `data/lina.db` 保存画像、岗位、投递记录和变化记录。测试环境使用内存 Repository。

## 2. 功能与操作手册

### 2.1 机会首页与岗位搜索

1. 打开首页，浏览当前推荐岗位。
2. 使用关键词、公司、地点和岗位类型筛选。
3. 点击官方入口复核岗位详情。
4. 投递后点击“标记已投递”；推荐会排除该岗位。
5. 需要恢复推荐时，在手动搜索结果中撤销已投递状态。

对应 API：

- `GET /opportunities`：首页推荐 Feed。
- `POST /opportunities/search`：按查询条件搜索。
- `POST /opportunities/recommended`：按偏好生成推荐。
- `GET /applications`、`POST /applications`：查询或保存投递记录。
- `DELETE /applications/{source_id}/{external_id}`：撤销投递记录。

推荐不是简单随机抽样：系统先排除已投递和非 `LIVE` 岗位，再按公司池、偏好、地点、岗位类型和轮换日期排序，并保留不同公司池的配额。

### 2.2 候选人画像、JD 提取与硬条件匹配

在 `/workbench` 中：

1. 输入或载入候选人画像。
2. 粘贴 JD，点击“从描述提取硬条件”。
3. 检查毕业年份、学历、经验和地点，以及每个字段对应的原文证据。
4. 保存候选人画像和目标岗位。
5. 点击“运行匹配”，查看全部不满足原因。

对应 API：

- `POST /profiles`
- `POST /jobs/parse`
- `POST /jobs`
- `POST /matches`

提取只接受明确表达。例如“2027 届，本科及以上学历，3 年以上工作经验，工作地点：上海”会提取为结构化约束；模糊表达会保留警告并要求人工确认。提取本身不会自动保存。

### 2.3 文件 Agent

文件 Agent 支持 TXT、Markdown 和 DOCX 简历，以及 Markdown JD 目录：

1. 选择简历文件。
2. 使用首页官方核验快照，或上传自己的 JD 目录。
3. 设置 Top-K。
4. 可选开启自动信号；LLM 行动计划必须显式开启。
5. 查看岗位匹配、技能证据、Gap、警告和脱敏运行历史。

命令行入口：

```powershell
uv run --locked lina-match --help
```

文件内容只在本地请求处理中使用。脱敏 Snapshot 不保存 Base64、原文、字符偏移或私密文件名。

### 2.4 对话助手

首页对话栏支持单轮岗位搜索、动态查询、岗位比较和流程引导。对话工具使用确定性意图路由，默认不需要模型 API key。

API：

```http
POST /assistant/messages
Content-Type: application/json

{"message":"帮我找上海的 AI 实习岗位"}
```

当前没有跨请求多轮记忆；需要完整证据匹配时应使用结构化工作台或文件 Agent。

### 2.5 岗位变化 Inbox

打开 `/inbox` 查看已记录的岗位新增、更新、关闭和重开事件。可对事件执行收藏、忽略或标记待比较等操作。

- `GET /inbox/events`
- `PATCH /inbox/events/{event_id}`

当前变化跟踪重点是 NVIDIA 官方来源；外部推送、邮件通知和完整公司范围的实时变化订阅尚未实现。

### 2.6 每周来源监控

手动生成来源健康报告：

```powershell
uv run --locked lina-monitor --output artifacts/weekly-monitor.json
```

GitHub Actions 每周一 01:00 UTC（北京时间 09:00）运行一次，检查官方入口可访问性并上传 JSON artifact。它是来源健康监控，不等同于所有公司岗位的实时采集，也不会读取个人简历。

### 2.7 沙箱执行与修复循环

调用 `POST /sandbox/runs`，请求包含初始 Python 源码和最多两个修复候选。系统会：

1. 对源码做 AST 校验；
2. 在临时目录启动独立 Python 子进程；
3. 不经过 shell，限制标准库导入、危险函数、超时和输出大小；
4. 初始执行失败后按顺序运行修复候选；
5. 返回每轮退出码、输出、错误和最终源码。

这是进程级受控执行，不是 Docker、Job Object、seccomp 或虚拟机级隔离，不应向不可信公网用户开放任意代码提交。

## 3. 技术实现

### 3.1 分层结构

```text
Web / CLI / HTTP API
        |
API routes + dependency wiring
        |
Application services
        |
Domain models, parsers, matching and ranking
        |
Repository and official-source adapters
        |
SQLite / in-memory storage and external Careers endpoints
```

- `api/`：FastAPI 路由、请求模型和依赖注入。
- `application/`：搜索、推荐、变化跟踪、文件 Agent 和对话用例。
- `domain/`：Pydantic 领域模型、约束解析、资格判断和证据结构。
- `infrastructure/`：SQLite/内存 Repository、官方招聘来源、沙箱和文件解析。
- `cli/`：`lina-match` 与 `lina-monitor`。
- `web/`：无构建链浏览器工作台。

### 3.2 岗位来源与推荐

`JobDiscoveryService` 并行概念上的来源聚合由顺序异步调用完成，随后按 `deduplication_key` 去重并平衡公司池。当前应用启动时配置：

- `VerifiedSnapshotJobSource`：固定、可复现的岗位快照。
- `NvidiaWorkdayJobSource`：调用 NVIDIA Workday CXS 官方 JSON 接口，分页获取列表，并按岗位详情接口补充信息。

搜索结果保留每个来源的 `status`、`fetched_at` 和岗位列表，因此调用方可以区分成功、限流、阻断和失败，而不是把失败伪装成零岗位。

### 3.3 证据化匹配

JD 解析器使用受限正则识别明确的毕业年份、学历、经验和地点，并记录原文 `start_offset`、`end_offset` 和 `document_id`。匹配器对学历、年份、经验和地点分别计算确定性结果，返回全部失败原因，不依赖模型自由判断。

### 3.4 持久化与隐私

Repository 协议隔离业务逻辑和存储实现。开发环境默认 SQLite，测试使用内存实现。Agent Run Snapshot 只存脱敏摘要、输入哈希、分数、Gap 和步骤状态，不保存简历正文及 Base64 文件内容。

### 3.5 测试与质量门禁

当前仓库验证命令：

```powershell
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked pyright
uv run --locked pytest --no-cov
```

2026-11-10 本地结果：

- `289 passed`
- Web/API/领域/基础设施测试全部通过
- CI 另要求分支覆盖率 100%，当前主 CI 已通过

## 4. 岗位更新是否实时

结论：**不是全量实时；是“固定快照 + 部分官方实时源”的混合模式。**

### 4.1 已验证行为

2026-11-10 本地调用 `POST /opportunities/search` 查询 NVIDIA 时，返回：

| 来源 | 状态 | `fetched_at` | 含义 |
| --- | --- | --- | --- |
| `verified-snapshot-2026-09-28` | success | 2026-09-28 00:00 UTC | 固定验证快照，不会随请求刷新 |
| `nvidia-careers` | success | 2026-11-10 12:20:02 UTC | 请求时访问 NVIDIA Workday 官方接口 |

因此 NVIDIA 搜索路径属于请求级实时查询，但仍受官方接口可用性、分页、限流和解析成功与否影响。

### 4.2 不应误解为实时的部分

- `GET /opportunities` 首页推荐包含 2026-09-28 固定快照。
- 其他公司没有统一实时列表解析器。
- 每周监控每周运行一次，不是持续监听。
- Inbox 只会记录已接入来源实际产生的变化。
- 岗位关闭、页面变化或投递资格必须点击官方链接再次确认。

### 4.3 实际使用建议

申请前应按以下顺序确认：

1. 使用手动搜索查看来源状态和 `fetched_at`。
2. 点击岗位官方详情页。
3. 检查岗位仍可申请、地点、截止时间和资格要求。
4. 再标记已投递或进入后续材料准备。

