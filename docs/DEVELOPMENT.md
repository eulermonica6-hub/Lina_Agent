# 开发指南

这份文档用于你亲手完成每个增量。每次任务都按“理解问题 -> 先写测试 -> 最小实现 -> 重构 -> 复述”推进。

## 环境准备

推荐从已提交的 VS Code 工作区开始：

```powershell
code Lina_Agent.code-workspace
```

工作区提供 FastAPI、匿名文件 Agent 和当前 pytest 文件三组调试入口，以及依赖同步、快速测试、Playwright 和完整质量门禁任务。VS Code 测试侧栏默认跳过浏览器测试以缩短红绿循环；提交前仍必须执行完整门禁。Windows 与 WSL 应分别选择各自的 Python 虚拟环境。代码地图、断点顺序与扩展规范见 [工程代码技术书](ENGINEERING_HANDBOOK.md)。

```bash
uv sync --extra dev --locked
uv run --extra dev --locked playwright install chromium
uv run --extra dev --locked pytest --browser chromium
```

`uv.lock` 是 Linux 与 Windows 共用的精确依赖图，但 `.venv` 不是跨平台产物。在 Windows 与 WSL 间切换时应分别创建环境，或用 `UV_PROJECT_ENVIRONMENT` 指向不同目录。不要手工编辑锁文件；修改 `pyproject.toml` 后运行 `uv lock`，提交前使用 `uv lock --check` 验证同步状态。Linux 首次安装浏览器时使用 `playwright install --with-deps chromium`。

启动应用：

```bash
uv run --locked uvicorn lina_agent.main:app --app-dir src --reload --port 8000
```

访问 <http://127.0.0.1:8000/> 使用 Lina 工作台；访问 <http://127.0.0.1:8000/docs> 调用 `GET /health`。如果返回服务名和版本号，说明应用、路由、配置注入已经连通。

本地文件 Agent 的最短验证路径：

```bash
uv run --locked lina-match \
  --resume tests/fixtures/resume_anonymized.md \
  --jobs tests/fixtures/job_catalog_anonymized.md \
  --top 3
```

默认不联网。Provider 测试必须使用 `httpx.MockTransport`，不能在单元测试中消耗真实额度。真实连通性探针只能使用无隐私提示；真实简历的派生数据也不得在缺少明确授权时发送给外部模型。

工作台的最短验证路径：

1. 点击“载入匿名示例”。
2. 点击“从描述提取硬条件”，确认显示 `2027 届`、`本科及以上学历` 和 `工作地点：上海` 三段证据。
3. 依次保存候选人画像和目标岗位。
4. 点击“运行匹配”。
5. 页面应显示“暂不满足硬条件”和“毕业年份不符合”。

完整实现过程、技术取舍、失败记录和面试表达见 [MVP 实现日志](MVP_IMPLEMENTATION.md)。
每次迭代的知识点和开发心得统一收录在 [开发知识库](KNOWLEDGE_BASE.md)。
面向使用者的字段解释、API 示例、数据生命周期和故障处理见 [当前版本使用手册](USER_GUIDE.md)。

## 质量门禁

```bash
uv lock --check
uv run --extra dev --locked ruff format --check .
uv run --extra dev --locked ruff check .
uv run --extra dev --locked pyright
uv run --extra dev --locked pytest --browser chromium --tracing=retain-on-failure \
    --cov=lina_agent --cov-branch --cov-fail-under=100
```

浏览器测试启动真实 FastAPI 工作台，并控制 API 响应返回时机，验证保存、抽取和匹配请求的过期成功与失败响应都不能覆盖用户修改后的新状态。失败 Trace 写入 `test-results/`；该目录不进入 Git，CI 会在失败时上传它供调试。

## 版本发布流程

当前版本为 `0.2.9`。版本号按可验收用户能力和响应契约变化递增。

重大更新推送前必须：

1. 同步更新 `src/lina_agent/__init__.py` 与 `pyproject.toml` 中的版本号。
2. 在 [Release Notes](../releaseNote.md) 顶部新增版本记录，说明新增能力、重要修复、验证结果和已知限制。
3. 运行 `tests/test_versioning.py`，确认项目元数据、运行时版本和发布记录一致。
4. 启动工作台，确认左上角版本徽标正确；该徽标由运行时版本自动渲染。
5. 按 [文档治理清单](DOCUMENTATION_GOVERNANCE.md) 统一 Review README、使用手册、Coding Plan、开发指南、专题设计、评测报告和知识库。
6. 完成全量质量门禁、提交和推送，保证代码、重要文档与 release note 位于同一个 commit。

## 先理解当前骨架

请按以下顺序阅读：

1. `tests/test_health.py`：先看外部期望行为。
2. `src/lina_agent/main.py`：观察应用工厂如何装配路由和配置。
3. `src/lina_agent/api/routes/health.py`：观察 FastAPI 依赖注入与响应 Schema。
4. `tests/domain/test_models.py`：观察领域约束如何被测试。
5. `src/lina_agent/domain/models.py`：观察 Pydantic 如何把输入边界变成类型。

思考并写下答案：

- 为什么 `create_app` 接收 `Settings`，而不是在函数内直接读取环境变量？
- 为什么岗位硬条件应该放在 `domain`，而不是 API 路由或 Agent Prompt 中？
- 如果模型返回负数工作年限，应该在哪一层最早失败？

## 第一个任务：硬条件匹配器

> 状态：已完成第一版。实现位于 `src/lina_agent/domain/matching.py`，测试位于 `tests/domain/test_matching.py`。

Repository、统一文档摄取、技能证据排序、有界 Supervisor、匿名 Gold、人工消融、自动决策信号、逐项证据评测、候选人投入确认和排序逆序诊断已完成。下一步建立类型化方向偏好确认。

### 目标

不调用 LLM，判断候选人是否满足岗位的硬条件，并返回所有失败原因。这个任务对应目标 JD 中的“需求理解、结果验证与可靠性”，也是后续 Agent 工作流中的确定性节点。

### 你要创建的代码

- `src/lina_agent/domain/matching.py`
- `tests/domain/test_matching.py`

建议定义两个对象：

```python
class HardConstraintResult(BaseModel):
    is_eligible: bool
    reasons: tuple[str, ...]


def evaluate_hard_constraints(
    candidate: CandidateProfile,
    job: JobPosting,
) -> HardConstraintResult: ...
```

你可以调整命名，但应保持函数无网络、无数据库、无 LLM 调用。相同输入必须得到相同输出。

### 第一版规则

1. `graduation_years` 非空时，候选人毕业年份必须在集合中。
2. `minimum_years_of_experience` 存在时，候选人工作年限必须达到要求。
3. `minimum_education` 存在时，按高中、大专、本科、硕士、博士的顺序比较。
4. `locations` 非空时，应与候选人的意向地点存在交集。
5. 一次返回全部失败原因，不在遇到第一项失败时提前结束。
6. 岗位没有任何约束时，应当通过。

### 先写这些测试

使用 `pytest.mark.parametrize` 覆盖：

- 无约束岗位通过；
- 2027 届候选人匹配仅限 2027 届岗位；
- 毕业年份不匹配；
- 本科学历满足本科要求，但不满足硕士要求；
- 工作年限不足；
- 意向城市无交集；
- 同时违反三个条件时返回三个原因。

先让测试失败，再写最小实现让它通过。不要先设计通用规则引擎；当第二类筛选规则出现后，再判断是否值得抽象。

### 完成标准

```bash
.venv/bin/ruff format .
.venv/bin/ruff check .
.venv/bin/pyright
.venv/bin/python -m pytest --cov --cov-branch
```

四条命令必须全部通过。然后用 5 分钟口头回答：

1. 为什么这部分不用 LLM？
2. 如何保证新增规则不会破坏旧规则？
3. 为什么结果要返回全部原因，而不是只有 `True/False`？

## 这一阶段的方法论

Agent 工程不是把所有问题都交给模型。先将系统拆成三类：

- **确定性规则**：可明确计算和验证，例如毕业年份、学历门槛。
- **概率性判断**：需要理解语义，例如项目经历是否能证明上下文工程能力。
- **人工决策**：风险高或偏好强，例如是否投递、是否采用简历改写。

面试时可以这样概括当前取舍：

> 我先实现确定性领域内核，把硬条件过滤从 LLM 中剥离，并用参数化测试固定业务语义。这样 Agent 只处理真正需要语义推理的部分，结果更稳定、成本更低，也更容易定位错误。

## 完成后记录

在开发日志中保留四项内容：

- 最初如何理解规则；
- 哪个测试最先失败；
- 实现中做过什么取舍；
- 如果需求增加“学历不限”或“地点远程”，当前模型要如何演进。

这会成为后续代码 Review 和面试复盘的输入。
