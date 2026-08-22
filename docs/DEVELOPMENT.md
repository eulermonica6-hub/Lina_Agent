# 开发指南

这份文档用于你亲手完成每个增量。每次任务都按“理解问题 -> 先写测试 -> 最小实现 -> 重构 -> 复述”推进。

## 环境准备

```bash
cp .env.example .env
uv sync --extra dev
uv run pytest
```

启动 API：

```bash
uv run uvicorn lina_agent.main:app --reload
```

访问 <http://127.0.0.1:8000/docs>，调用 `GET /health`。如果返回服务名和版本号，说明应用、路由、配置注入已经连通。

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
uv run ruff format .
uv run ruff check .
uv run pyright
uv run pytest --cov
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