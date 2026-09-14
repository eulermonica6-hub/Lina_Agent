# Lina 当前版本使用手册

> 适用版本：0.2.5
> 使用方式：本地文件 Agent、单用户 Web 工作台或 HTTP API
> 数据存储：进程内存，服务重启后清空

## 1. 当前能力边界

Lina 当前是求职 Agent 的确定性产品基线，还不是可以自由对话、联网搜索和自主选择工具的完整 Agent。

| 功能 | 当前状态 | 说明 |
| --- | --- | --- |
| 候选人画像录入 | 可用 | 手工填写结构化字段 |
| JD 文本硬条件提取 | 可用 | 只识别明确表达，并返回原文证据 |
| 岗位保存 | 可用 | 保存到当前服务进程的内存 |
| 硬条件匹配 | 可用 | 判断毕业年份、学历、经验和地点 |
| 匿名示例 | 可用 | 用于快速体验和验证 |
| 本地简历/JD Agent | 可用 | 读取 TXT、Markdown、DOCX，输出证据 Top-K 和 Trace |
| 智能行动计划 | 可选 | CLI `--use-llm` 或 API `use_llm=true` 显式启用 |
| 多岗位能力缺口 | 可用 | 聚合 Top-K 的硬性/优先缺口、影响岗位与证据优势 |
| 计划复核与降级 | 可用 | 无证据技能被拒绝；模型失败时保留确定性分析 |
| 自然语言对话 | 不可用 | 尚无会话状态和开放式工具选择 |
| 联网岗位和公司查询 | 不可用 | 尚无 Search Provider 或来源适配器 |
| DOCX 简历解析 | 可用 | 支持正文、表格和文本框中的文字 |
| PDF/OCR | 不可用 | 尚不处理 PDF、扫描件和图片内文字 |
| 官方 JD 离线摄取 | 开发工具 | 人工运行脚本，输出仅保存到 Git 忽略的私有目录 |
| 数据持久化 | 不可用 | 重启后画像和岗位会丢失 |

## 2. 启动 Lina

### 2.1 首次安装

要求 macOS、Linux、Windows 或 Windows WSL，并安装 Python 3.12+ 与 uv。

```bash
cp .env.example .env
uv sync --extra dev --locked
uv run --extra dev --locked playwright install chromium
```

Linux 首次安装浏览器时，将最后一条命令改为 `playwright install --with-deps chromium`，同时安装 Chromium 所需系统库。

### 2.2 启动服务

在项目根目录运行：

```bash
uv run --extra dev --locked uvicorn lina_agent.main:app --app-dir src --reload --port 8000
```

保持终端运行，然后访问：

- 工作台：<http://127.0.0.1:8000/>
- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/health>

健康检查应返回类似：

```json
{
  "status": "ok",
  "service": "Lina Career Agent",
  "version": "0.2.5"
}
```

## 3. 一分钟体验

1. 打开工作台。
2. 点击“载入匿名示例”。
3. 在“目标岗位”区域点击“从描述提取硬条件”。
4. 确认页面显示 `2027 届`、`本科及以上学历` 和 `工作地点：上海` 原文证据。
5. 点击“保存候选人画像”。
6. 检查岗位字段后，点击“保存目标岗位”。
7. 点击“运行匹配”。
8. 页面应显示“暂不满足硬条件”和“毕业年份不符合”。
9. 需要测试其他岗位时，点击“开始新一轮”，无需刷新页面。

原因是匿名候选人的毕业年份是 2028，而示例岗位只接受 2027 届。

## 4. 使用自己的数据

### 4.1 填写候选人画像

| 字段 | 填写方式 |
| --- | --- |
| 毕业年份 | 填预计或实际毕业年份，例如 `2027` |
| 最高学历 | 选择高中、大专、本科、硕士或博士 |
| 工作经验 | 以年为单位，可填写小数，例如 `0.5` |
| 意向地点 | 多个地点使用中文或英文逗号分隔 |
| 技能关键词 | 多个技能使用中文或英文逗号分隔 |

点击“保存候选人画像”后，页面显示“已保存”。如果之后修改任何字段，状态会变成“有修改”，需要重新保存才能匹配。

修改已保存字段后，Lina 会立即禁用匹配并清空旧结论，避免新表单内容与旧的后端实体混用。

### 4.2 粘贴和解析 JD

先填写岗位名称、公司和岗位描述。建议粘贴包含完整职责与要求的原文，不要只粘贴标题。

点击“从描述提取硬条件”后，Lina 会尝试填写：

- 要求毕业年份；
- 最低学历；
- 最低工作经验；
- 工作地点。

抽取结果不会自动保存。必须检查结构化字段和“抽取证据”，必要时手工修正，再点击“保存目标岗位”。当前工作台把这次显式保存视为用户确认，但后端尚未单独保存确认状态或证据关联。

### 4.3 当前支持的典型表达

| 类型 | 示例 |
| --- | --- |
| 单毕业年份 | `2027 届毕业生` |
| 多毕业年份 | `2027、2028 届毕业生` |
| 最低学历 | `本科及以上学历`、`硕士以上` |
| 最低经验 | `3 年以上工作经验`、`0 年工作经验` |
| 工作地点 | `工作地点：上海` |

解析器采用高精度保守规则。对于“优秀者可放宽”“应届优先”“base 上海”“接受远程”等表达，当前可能无法识别，应以人工检查为准。

### 4.4 理解匹配结果

Lina 一次返回所有不满足的硬条件：

| 原因码 | 页面文案 | 含义 |
| --- | --- | --- |
| `graduation_year` | 毕业年份不符合 | 候选人年份不在岗位允许集合中 |
| `education` | 学历未达到要求 | 最高学历低于岗位最低学历 |
| `experience` | 工作经验不足 | 经验年限低于岗位要求 |
| `location` | 意向地点不匹配 | 意向地点与岗位地点没有交集 |

“硬条件通过”只表示满足当前已录入的四类门槛，不代表技能匹配、面试成功率或最终录用概率。

### 4.5 运行本地文件 Agent

推荐把真实资料放在 Git 已忽略的 `data/private/`。默认运行完全本地，不调用模型：

```bash
uv run --locked lina-match \
  --resume "data/private/your-resume.docx" \
  --jobs "data/private/AI_Agent_JD.md" \
  --top 5
```

也可以运行 `uv run --locked python -m lina_agent.cli ...`。支持的简历格式是 UTF-8 `.txt`、`.md` 和 `.docx`；JD 目录标题格式为 `### 序号. 岗位 | 公司`，半角或全角竖线均可。

默认报告中的“证据覆盖分”由明确要求、优先项和职责上下文覆盖率加权生成。它不是录取概率；学历、毕业时间和经验年限仍需人工确认。报告还会聚合 Top-K 的能力缺口：硬性缺口权重高于优先项，`priority_score` 只表示该技能影响当前 Top-K 的相对范围，不表示学习难度。

实验性自动综合排序需要显式启用：

```bash
uv run --locked lina-match \
  --resume "data/private/your-resume.docx" \
  --jobs "data/private/AI_Agent_JD.md" \
  --auto-decision-signals
```

该模式会抽取毕业届次、学历、地点、每周到岗天数、持续月份和岗位方向，返回逐项双侧证据。缺少候选人证据的硬条件保持 `unknown` 并进入警告，不会被默认为兼容。当前 5 JD 基线上硬条件覆盖率为 `0.6`，因此默认仍使用 skill-only。

### 4.6 配置经济型模型 Provider

只有 CLI 加入 `--use-llm` 或 API 明确设置 `use_llm=true` 才会生成智能行动计划。默认路由是多个 Groq 凭据、Agnes、NVIDIA；免费服务都失败时不会自动调用付费 DeepSeek。

密钥可以放在被 Git 忽略的 `data/private/LLM api key.txt`：

```text
deepseek=sk-placeholder
nvidia=nvapi-placeholder
groq=gsk_placeholder
agnes=sk-placeholder
```

也可以使用 `LINA_LLM_GROQ_API_KEY`、`LINA_LLM_AGNES_API_KEY`、`LINA_LLM_NVIDIA_API_KEY`、`LINA_LLM_DEEPSEEK_API_KEY` 环境变量。环境变量会替换同一 Provider 的文件凭据。常用选择：

```bash
# 显式只用 NVIDIA
LINA_LLM_PROVIDER=nvidia uv run --locked lina-match ... --use-llm

# 允许免费服务失败后付费回退；请自行承担费用
LINA_LLM_ALLOW_PAID_FALLBACK=true uv run --locked lina-match ... --use-llm
```

模型节点只接收候选人技能标签、Top 岗位标题/公司、覆盖项以及聚合缺口，不接收简历文件名、联系方式或原文证据。模型计划必须返回目标技能、产出物、验收标准和时间预算；确定性 Reviewer 会拒绝无证据技能、重复任务或不连续优先级。技能组合仍可能构成个人派生数据；启用 LLM 前应确认接受将这些字段发送给所选 Provider。

## 5. API 使用

API 的交互式 Schema 和试用入口位于 <http://127.0.0.1:8000/docs>。

### 5.1 解析 JD，不保存

```bash
curl -X POST http://127.0.0.1:8000/jobs/parse \
  -H 'Content-Type: application/json' \
  -d '{
    "description": "工作地点：上海。要求 2027 届本科及以上学历，具备 2 年以上工作经验。"
  }'
```

响应包含 `constraints`、`evidence` 和 `warnings`。`evidence` 中的偏移满足：

```python
description[start_offset:end_offset] == evidence_text
```

### 5.2 创建候选人

```bash
curl -X POST http://127.0.0.1:8000/profiles \
  -H 'Content-Type: application/json' \
  --data @tests/fixtures/candidate_profile.json
```

保存响应中的 `id`。

### 5.3 创建岗位

```bash
curl -X POST http://127.0.0.1:8000/jobs \
  -H 'Content-Type: application/json' \
  --data @tests/fixtures/target_job.json
```

保存响应中的 `id`。解析接口不会自动创建岗位，仍需调用本接口。

### 5.4 执行匹配

```bash
curl -X POST http://127.0.0.1:8000/matches \
  -H 'Content-Type: application/json' \
  -d '{
    "candidate_id": "f7ea0c79-f85e-43f7-afd4-7cb1df360000",
    "job_id": "1d46a09b-3be0-41ce-95bf-9d1768db0000"
  }'
```

如果服务重启过，需要重新创建候选人和岗位，否则旧 ID 会返回 `404`。

### 5.5 文件 Agent API

`POST /agent/runs` 接收两个 Base64 文档：`resume` 支持 TXT/Markdown/DOCX，`job_catalog` 使用结构化 Markdown。响应包含候选人技能证据、Top-K、聚合能力缺口、步骤 Trace 和警告。为避免服务端任意路径读取，API 不接受本地文件路径；请求 Schema 可在 `/docs` 直接查看和试用。

请求默认 `auto_decision_signals=false`、`use_llm=false`，完全本地运行。设置 `auto_decision_signals=true` 会启用本地确定性综合排序，并在 `decision_signal_extractions` 返回逐项证据；只有明确设置 `use_llm=true` 才会调用经济型 Provider。Provider 或 Schema 失败时 HTTP 请求仍返回确定性结果，`state` 为 `degraded`，失败节点的 `status` 为 `failed`。这表示模型增强失败，不表示 Top-K 和缺口分析失败。

## 6. 数据与隐私

- 数据只保存在 Uvicorn 进程内存中；停止或重启服务后清空。
- 当前没有登录和访问控制，只应在本机使用，不要直接暴露到公网。
- 原始真实简历应放在 `data/private/`，该目录被 Git 忽略。
- 提交代码前运行 `git status`，确认没有个人姓名、手机号、邮箱或完整简历进入版本控制。
- 工作台和默认文件 Agent 不调用 LLM。只有 CLI `--use-llm` 或 API `use_llm=true` 会发送第 4.6 节列出的最小化结构字段。
- key 文件必须保留在 `data/private/` 或使用环境变量；任何日志、异常和 Git 提交都不应包含 key。

## 7. 常见问题

### 端口 8000 已被占用

先访问 <http://127.0.0.1:8000/health>。如果返回 Lina 信息，说明服务已经运行，无需重复启动。否则改用其他端口：

```bash
uv run --extra dev --locked uvicorn lina_agent.main:app --app-dir src --reload --port 8001
```

然后访问 <http://127.0.0.1:8001/>。

### 点击“运行匹配”仍然不可用

候选人画像和目标岗位都必须显示“已保存”。修改任一已保存字段后，需要重新保存。

### 如何开始分析另一个岗位

点击首屏的“开始新一轮”。它会清空候选人、岗位、抽取证据和匹配结论。点击“载入匿名示例”也会先废弃当前已保存 ID，示例数据必须重新保存后才能匹配。

### JD 没有提取出任何条件

解析器只识别当前支持的明确表达。查看页面警告，并手工填写岗位约束。没有提取结果不代表岗位没有要求。

### 返回 `404`

通常是候选人或岗位 ID 不存在，或者服务重启导致内存数据清空。重新创建两个实体后再匹配。

### 返回 `422`

请求未通过 Pydantic 校验。检查必填字段、年份范围、负数经验、UUID 格式和学历枚举；也可以在 `/docs` 查看准确 Schema。

### DOCX 读取为空或顺序异常

Lina 会读取正文、表格单元格和文本框文字，真正无文本时显式失败。页眉页脚、批注、扫描图片和复杂双栏版面不在当前支持范围；这类文件先另存为 UTF-8 文本，或等待 PDF/OCR 与版面解析阶段。

### 免费模型限流

Groq 单个凭据出现 401/403、429、网络错误、无效响应或部分 5xx 时，会按文件顺序尝试下一个 Groq 账号，再降级到 Agnes 和 NVIDIA。只应配置自己有权使用的账号；同一 organization 的多个 key 不会增加官方组织级额度。DeepSeek 只有显式选择或允许付费回退时启用。

## 8. 质量检查

提交变更前运行：

```bash
uv lock --check
uv run --extra dev --locked ruff format --check .
uv run --extra dev --locked ruff check .
uv run --extra dev --locked pyright
uv run --extra dev --locked pytest --browser chromium --tracing=retain-on-failure \
  --cov=lina_agent --cov-branch --cov-fail-under=100
```

当前阶段的实现与复盘见 [MVP 实现日志](MVP_IMPLEMENTATION.md)和 [JD 解析迭代日志](iterations/002-jd-constraint-extraction.md)。

## 9. 运行 JD 解析评测

开发者可以对固定的 6 例匿名标注集运行离线评测：

```bash
uv run --locked python -m lina_agent.evaluation.job_parser \
  tests/fixtures/job_parser_evaluation.json
```

当前基线：字段 Precision `100%`、Recall `62.5%`、整条 JD Exact Match `50%`。这表示解析器倾向于少提取、不乱提取，但仍会漏掉一些常见替代表达。详细口径与失败案例见 [JD 解析基线评测报告](evaluations/JD_PARSER_BASELINE.md)。
