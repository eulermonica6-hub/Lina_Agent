# Lina 开发知识库

本索引记录每次可验收的产品迭代。代码、测试和文档是同一个交付物；缺少复盘记录的增量不视为完成。

## 迭代索引

| 编号 | 日期 | 主题 | 用户价值 | 详细记录 |
| --- | --- | --- | --- | --- |
| 001 | 2026-08-23 | 首个可操作 MVP | 在浏览器完成画像、岗位和硬条件匹配 | [MVP 实现日志](MVP_IMPLEMENTATION.md) |
| 002 | 2026-08-23 | JD 硬条件解析与证据预览 | 粘贴 JD 后自动填充明确门槛，并人工确认原文证据 | [JD 解析迭代](iterations/002-jd-constraint-extraction.md) |
| 003 | 2026-08-23 | 当前使用说明与文档治理 | 明确可用能力、操作步骤、限制和故障处理 | [使用文档迭代](iterations/003-current-usage-documentation.md) |
| 004 | 2026-08-23 | Demo 五轮验收与状态优化 | 验证五类匹配结果，修复新旧数据状态错位 | [五轮验收迭代](iterations/004-five-round-demo-validation.md) |
| 005 | 2026-08-23 | JD 解析离线评测基线 | 用 6 例标注集量化精度、召回和失败类型 | [评测基线迭代](iterations/005-jd-parser-evaluation-baseline.md) |
| 006 | 2026-08-23 | 推送前审查与正确性加固 | 修复偏好误判、地名切割、异步竞态和空评测 | [审查加固迭代](iterations/006-pre-push-review-hardening.md) |
| 007 | 2026-08-23 | 面向 Agent 工程评审的仓库叙事 | 从定向求职包装转为可信 Agent 工程试验场，并加入产品证据 | [README 定位迭代](iterations/007-agent-engineering-readme.md) |
| 008 | 2026-08-24 | 版本展示与发布记录 | 建立统一版本源、页面版本徽标和重大更新发布流程 | [版本治理迭代](iterations/008-versioning-and-release-notes.md) |
| 009 | 2026-08-24 | 代码现状与路线审计 | 统一真实能力、文档口径和后续阶段依赖 | [路线审计迭代](iterations/009-codebase-roadmap-audit.md) |
| 010 | 2026-08-24 | 文档治理与数据标注规范 | 建立重要文档契约、版本 Review 清单和 JD/简历标注流程 | [文档与标注迭代](iterations/010-documentation-and-annotation-governance.md) |
| 011 | 2026-08-26 | P0 工程基线与浏览器竞态自动化 | 保证 UTF-8、依赖和异步状态在 Linux/Windows 可重复验证 | [P0 工程基线迭代](iterations/011-p0-engineering-baseline.md) |
| 012 | 2026-08-26 | 首个证据驱动职业匹配 Agent | 从真实 DOCX 与 JD 生成可解释 Top-K，并可选生成匿名化智能计划 | [初步 Agent 核心迭代](iterations/012-initial-career-agent.md) |
| 013 | 2026-08-27 | 多 Provider 路由与 Git 连接诊断 | 增加 Agnes、多 Groq 凭据故障切换和可复现的网络分层定位 | [Provider 与连接迭代](iterations/013-provider-routing-and-connectivity.md) |
| 014 | 2026-08-27 | 可验证、可降级的多节点 Agent 内核 | 聚合多岗位能力缺口，约束并复核 LLM 计划，模型失败时保留确定性结果 | [多节点核心迭代](iterations/014-verifiable-multi-node-agent-core.md) |

## 文档入口

| 读者 | 首选文档 | 用途 |
| --- | --- | --- |
| 第一次使用 Lina | [当前版本使用手册](USER_GUIDE.md) | 安装、启动、操作、API、隐私和故障处理 |
| 浏览项目概况 | [项目 README](../README.md) | 当前能力、目标、技术路线和文档导航 |
| 参与开发 | [开发指南](DEVELOPMENT.md) | 环境、测试驱动流程和质量门禁 |
| 查看后续规划 | [Coding Plan](CODING_PLAN.md) | 阶段目标、验收标准和知识路线 |
| 复盘实现过程 | 本知识库的迭代索引 | 决策、失败、心得、验证和面试素材 |
| 查看岗位监控设计 | [岗位监控设计](JOB_MONITORING.md) | 尚未实现的来源、调度和可靠性方案 |
| 查看能力指标 | [JD 解析基线评测](evaluations/JD_PARSER_BASELINE.md) | 指标口径、基线结果与失败分类 |
| 管理重要文档 | [文档治理](DOCUMENTATION_GOVERNANCE.md) | 文档职责、事实来源和版本 Review 清单 |
| 准备评测数据 | [数据匿名化与标注指南](DATA_ANNOTATION.md) | JD/简历匿名化、Gold Label 和人工复核流程 |

## 每次迭代的完成标准

1. 写明真实用户问题和不做事项。
2. 用失败测试或失败操作固定验收标准。
3. 记录领域知识、关键概念和架构取舍。
4. 记录实际失败、根因和修复证据，而不是事后美化过程。
5. 运行聚焦测试、全量质量门禁和真实用户路径。
6. 写出开发心得、遗留风险和下一步升级条件。
7. 沉淀 30 秒介绍、STAR 素材和高频追问。

## 知识分类

- **确定性内核**：Pydantic 领域模型、硬条件规则、证据偏移、纯函数解析。
- **应用架构**：Repository Protocol、应用服务、FastAPI 契约、依赖注入。
- **Agent 工程**：概率性抽取、上下文构建、Verifier、Human-in-the-loop、评测。
- **产品工程**：工作台状态、可解释反馈、响应式布局、隐私边界。
- **可靠性**：契约测试、分支覆盖、类型检查、真实浏览器验收、失败案例。

后续新增迭代时，应先复制 [迭代日志模板](MVP_IMPLEMENTATION.md#11-后续日志模板)，完成后再把入口加入本索引。
