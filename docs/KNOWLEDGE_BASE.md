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
| 015 | 2026-08-27 | Agent 架构与数据流基线 | 明确双内核、完整输入输出、数据传输、实验脚本边界与后续收敛顺序 | [架构与数据流迭代](iterations/015-agent-architecture-dataflow-baseline.md) |
| 016 | 2026-08-27 | VS Code 工程框架与完整技术书 | 用统一工作区、调试任务、代码地图和演进规则降低后续接手与迭代成本 | [工程框架迭代](iterations/016-vscode-engineering-handbook.md) |
| 017 | 2026-09-03 | 公开真实 JD 摄取与匿名化 | 从官方来源建立 10 条正式岗负例候选 | [真实 JD 摄取迭代](iterations/017-public-jd-ingestion.md) |
| 018 | 2026-09-03 | 上海 AI 实习目标范围修正 | 区分正式岗负例与待资格核验的实习候选 | [上海实习范围迭代](iterations/018-shanghai-ai-internship-scope.md) |
| 019 | 2026-09-14 | 国内外大厂实习资格核验 | 用官网证据建立上海 AI 实习优先投递池 | [大厂实习核验](iterations/019-official-internship-verification.md) |
| 020 | 2026-09-14 | 技能证据与 Top-K Gold 基线 | 用真实匿名 Gold 量化抽取、引用、排序和权重边界 | [技能排序评测](iterations/020-career-matching-gold-baseline.md) |
| 021 | 2026-09-14 | 决策信号桥接与排序消融 | 验证硬条件与方向信息对人工 Top-K 的贡献 | [决策信号消融](iterations/021-decision-signal-ablation.md) |
| 022 | 2026-09-14 | 自动决策信号基线 | 用证据和未知状态连接简历/JD，并独立评测自动排序 | [自动信号基线](iterations/022-automatic-decision-signal-baseline.md) |
| 023 | 2026-09-14 | 硬条件逐项 Gold 与范围表达 | 用逐项状态和最小证据区分解析遗漏与用户事实缺失 | [逐项硬条件基线](iterations/023-hard-constraint-item-gold.md) |
| 024 | 2026-09-14 | 候选人投入确认领域契约 | 用独立确认来源补充到岗/时长事实，不伪造文档证据 | [投入确认契约](iterations/024-candidate-availability-confirmation-contract.md) |
| 025 | 2026-09-15 | 候选人投入确认 Gold 复跑 | 消除投入事实未知值，并定位剩余排序误差 | [确认后 Gold 复跑](iterations/025-confirmed-availability-gold-rerun.md) |
| 026 | 2026-09-15 | 排序并列与逆序对分析 | 尊重同优先级偏好，并将排序误差定位到具体分量 | [并列与逆序分析](iterations/026-ranking-ties-and-inversion-analysis.md) |
| 027 | 2026-09-21 | 候选人方向偏好确认契约 | 用带来源的方向强度消除离散重叠率歧义 | [方向偏好确认](iterations/027-direction-preference-confirmation-contract.md) |
| 028 | 2026-09-24 | 方向偏好入口接线 | 在 Agent、API、CLI 使用同一确认契约并防止静默丢参 | [方向偏好入口](iterations/028-direction-preference-entry-wiring.md) |
| 029 | 2026-09-24 | 多冻结 Gold 套件基线 | 分离方向族覆盖、样本规模、宏平均和最差集稳定性 | [多 Gold 套件](iterations/029-multi-gold-suite-baseline.md) |
| 030 | 2026-09-24 | 第二个冻结 Gold 与官方 JD 回归 | 用真实测试自动化措辞发现方向召回缺口并补 coverage 指标 | [第二 Gold 回归](iterations/030-second-gold-official-jd.md) |
| 031 | 2026-09-24 | 国内外大厂 JD 扩展与硬门槛排序 | 用 5 条新增官方 JD 修复多城市、范围、方向和 hard veto | [国内外 JD 扩展](iterations/031-domestic-global-jd-expansion.md) |
| 032 | 2026-09-24 | 确定性技能证据计划 | 将 NVIDIA 排序逆序转化为 PyTorch/C++/CUDA 可验收项目 | [技能证据计划](iterations/032-deterministic-skill-evidence-plan.md) |
| 033 | 2026-09-24 | PyTorch LLM 推理基线 | 用固定 causal decoder 量化 CPU/MPS 延迟、吞吐、内存和误差 | [PyTorch 推理基线](iterations/033-pytorch-inference-baseline.md) |
| 034 | 2026-09-24 | PyTorch C++ RMSNorm 扩展 | 从 `0.38x` 负结果优化到 `1.60x`，保持误差 `1.91e-6` | [C++ RMSNorm 扩展](iterations/034-pytorch-cpp-rmsnorm-extension.md) |
| 035 | 2026-09-24 | CUDA RMSNorm 实现与验证契约 | 在无 NVIDIA 环境下完成 kernel、探针、条件测试和 GPU workflow，不伪造性能结果 | [CUDA RMSNorm 契约](iterations/035-cuda-rmsnorm-contract.md) |
| 036 | 2026-09-24 | CUDA Runner Preflight 与安全注册 | 将外部 GPU、工具链、labels 和 token 安全转化为机器可读门禁 | [CUDA Runner Preflight](iterations/036-cuda-runner-preflight.md) |
| 037 | 2026-09-24 | SQLite 结构化状态持久化 | 让 Web 画像与岗位跨重启恢复，同时保留 Agent Run 的独立版本边界 | [SQLite 持久化](iterations/037-sqlite-structured-state-persistence.md) |
| 038 | 2026-09-24 | 版本化 Agent Run Snapshot | 用脱敏投影保存 Run 历史，不复制原文 evidence 与私密文件名 | [Agent Run Snapshot](iterations/038-versioned-agent-run-snapshots.md) |
| 039 | 2026-09-24 | 文档引用与候选确认版本 | 分离内容、角色与确认事件 ID，用 metadata/facts hash 支持历史关联 | [输入版本关联](iterations/039-document-and-confirmation-versions.md) |

## 文档入口

| 读者 | 首选文档 | 用途 |
| --- | --- | --- |
| 第一次使用 Lina | [当前版本使用手册](USER_GUIDE.md) | 安装、启动、操作、API、隐私和故障处理 |
| 浏览项目概况 | [项目 README](../README.md) | 当前能力、目标、技术路线和文档导航 |
| 参与开发 | [开发指南](DEVELOPMENT.md) | 环境、测试驱动流程和质量门禁 |
| 系统学习完整代码 | [工程代码技术书](ENGINEERING_HANDBOOK.md) | 分层、领域契约、数据流、VS Code 调试、扩展方法和未来行动 |
| 查看后续规划 | [Coding Plan](CODING_PLAN.md) | 阶段目标、验收标准和知识路线 |
| 理解当前数据流 | [Agent 架构与数据流](AGENT_ARCHITECTURE.md) | 入口、领域契约、节点方向、脚本和架构债务 |
| 复盘实现过程 | 本知识库的迭代索引 | 决策、失败、心得、验证和面试素材 |
| 查看岗位监控设计 | [岗位监控设计](JOB_MONITORING.md) | 尚未实现的来源、调度和可靠性方案 |
| 查看能力指标 | [JD 解析基线评测](evaluations/JD_PARSER_BASELINE.md) | 指标口径、基线结果与失败分类 |
| 查看技能排序指标 | [技能证据与 Top-K 基线](evaluations/CAREER_MATCHING_BASELINE.md) | 技能、匹配、引用、排序和权重校准结果 |
| 管理重要文档 | [文档治理](DOCUMENTATION_GOVERNANCE.md) | 文档职责、事实来源和版本 Review 清单 |
| 维护决策信号 | [决策信号行为准则](DECISION_SIGNAL_RULES.md) | 抽取、证据、Gold、评测与发布约束 |
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
