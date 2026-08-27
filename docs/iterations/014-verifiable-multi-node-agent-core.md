# 迭代 014：可验证、可降级的多节点 Agent 内核

> 日期：2026-08-27
> 版本：0.2.0
> 类型：Agent 编排、缺口分析、计划契约、可靠性
> 状态：已完成

## 1. 用户目标

在继续包装 Web 展示之前，确认 LLM 是否真正接入，并优先完善 Agent 核心。用户担心单智能体无法支撑精细化子任务，因此本轮需要给子模块明确职责、输入输出和失败边界。

## 2. 审计结论

0.1.2 已完成 LLM 的真实 Provider 接入、免费优先故障切换和 JSON Schema 行动计划，但模型只在 CLI `--use-llm` 时工作。旧链路还有三个关键缺口：

1. `POST /agent/runs` 不能显式启用 LLM；
2. Provider、网络或坏 JSON 会让整次 CLI 运行失败，确定性 Top-K 也随之丢失；
3. 行动计划只有“做什么”和“为什么”，缺少目标技能、产出物、验收标准和时间预算，也没有独立复核节点。

因此，LLM 是“已接通”，但 Agent 闭环仍不完整。

## 3. 为什么不是多个自主 Agent 群聊

本轮采用一个 Supervisor 加七类专业角色：

```text
Document Ingestor
  -> Candidate Analyst
  -> Job Analyst
  -> Matcher
  -> Gap Analyst
  -> Career Planner（显式 opt-in LLM）
  -> Plan Reviewer（确定性）
```

这些角色可以称为专业节点，因为每个节点都有独立领域输出和测试标准。它们暂不升级为互相对话的自主 Agent，原因是：

- 文档摄取、词表匹配和优先级计算是确定性问题；
- 自由对话会增加 Token、循环和故障定位成本；
- 当前没有持久化检查点，多自主 Agent 失败后无法可靠恢复；
- 只有 Planner 需要概率模型，Reviewer 必须保持确定性。

后续只有当子任务具备独立目标、上下文、工具和评测集时，才拆成真正独立的 Agent。

## 4. 多岗位缺口分析

新增 `CareerGapAnalysis`：

- 聚合当前 Top-K 中缺失的硬性技能和优先技能；
- 记录每项技能影响的岗位编号和 JD 原文证据；
- 硬性缺口按 1.0、优先缺口按 0.35 计算相对影响分；
- 输出 high、medium、low 三档确定性优先级；
- 汇总候选人在多少个 Top 岗位中已有技能证据。

该分数只用于当前 Top-K 内的相对排序，不表示技能学习难度、求职成功率或市场需求。

## 5. 受约束的行动计划

每项 `CareerPlanAction` 现在必须包含：

- 连续的优先级；
- 1–3 个目标技能；
- 具体行动和原因；
- 可检查的产出物；
- 验收标准；
- 1–80 小时时间预算。

模型上下文只包含规范化候选人技能、Top 岗位摘要、覆盖项和聚合缺口，不包含文件名、联系方式或简历原句。

## 6. 确定性 Reviewer

`Plan Reviewer` 不再相信“符合 JSON Schema”就等于计划可信。它继续检查：

1. 优先级是否从 1 开始连续；
2. 是否存在重复任务；
3. 目标技能是否来自候选人证据或 JD 缺口。

不合格计划不会进入 `action_plan`；运行状态改为 `degraded`，`action_plan_review` 保存拒绝原因，确定性 Top-K 和缺口分析仍可使用。

## 7. 可观测降级

Agent Run 新增两层状态：

- 运行级：`complete` 或 `degraded`；
- 步骤级：`complete`、`failed` 或 `skipped`。

Provider 未配置、网络失败、限流、服务错误、坏 JSON 或 Schema 不合格都被转换为可解释的 Planner 失败。应用层只捕获预期的 `CareerPlannerError`，不会用宽泛 `except Exception` 掩盖程序缺陷。

## 8. API 与隐私边界

`POST /agent/runs` 新增 `use_llm=false`：

- 默认值保持完全本地和确定性；
- 只有用户显式设置 `true` 才调用外部 Provider；
- API 与 CLI 复用同一 Planner、Reviewer 和降级路径；
- Web 首页没有新增上传或计划展示，避免在核心契约稳定前重复实现 UI。

## 9. 测试与实际修复

新增或扩展测试覆盖：

- required/preferred 缺口聚合和 high/medium/low 分档；
- 跨岗位证据去重与已有优势统计；
- 正常计划复核；
- 优先级不连续、重复行动和无证据技能拒绝；
- Provider 失败后的 `degraded` 状态；
- 默认 Provider 延迟构建；
- API `use_llm=true`；
- CLI 产出物、验收标准和时间预算。

开发中 Pyright 发现 dataclass 的空 `set/list` 默认工厂被推断为 `Unknown`。修复方式是显式构造 `set[int]` 和 `list[SourceEvidence]`，保持 strict 类型边界。

首次真实匿名计划探针返回 `degraded`。捕获的安全响应显示 Groq Qwen 3.6 默认先输出很长的 `<think>`，1024 Token 用尽时还没有生成最终 JSON。根据 Groq 官方参数，Provider 对该模型设置 `reasoning_effort=none` 和 JSON mode；其他 Provider 不接收 Groq 专属 reasoning 参数。解析器同时升级为扫描首个真正符合计划 Schema 的 JSON 对象，避免前置推理文本中的示例 Schema 被误认为结果。

修复后的同一匿名 Fixture 返回 `complete`：1 个岗位、1 项聚合缺口、3 项行动，Reviewer 为 `verified`，无失败步骤，共使用 896 Token。真实探针不包含私有简历、联系方式或原文证据。

Groq 参数依据：[Reasoning 指南](https://console.groq.com/docs/reasoning)与 [Chat Completions API Reference](https://console.groq.com/docs/api-reference)。

## 10. 当前边界与下一步

0.2.0 已经比“Prompt 包装器”更接近工程 Agent：有专业节点、类型化状态、模型条件边、证据复核和失败降级。但它仍缺少：

- 人工标注的技能抽取与 Top-K 排序评测；
- 文档、确认状态和 Agent Run 持久化；
- 检查点与断点恢复；
- 结构化语义抽取及引用跨度验证；
- 自然语言任务入口和真正动态工具规划。

下一步仍应先制作匿名 Gold Set，测量词表 Precision/Recall、Top-K 一致性和引用支持率，再引入持久化。前端、PDF 和爬虫继续后置。

## 11. 30 秒表达

> 0.1.2 已经接通多模型，但模型失败会中断整次运行，行动计划也无法验证。我把工作流拆成画像、岗位、匹配、缺口、计划和复核等专业节点；只有 Planner 使用 LLM，其余保持确定性。多个岗位的缺口先聚合成有证据的优先级，模型必须给出目标技能、产出物、验收标准和时间预算，再由 Reviewer 拒绝无证据技能。即使所有 Provider 都失败，Top-K 和缺口分析仍返回，状态明确标成 degraded。
