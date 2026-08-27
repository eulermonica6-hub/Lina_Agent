# 迭代 015：Agent 架构与数据流基线

> 日期：2026-08-27
> 版本：0.2.0（文档与安全边界增量，不改变运行时版本）
> 状态：已完成

## 1. 目标

在继续开发前，把当前 Agent 项目的入口、脚本、领域模型、输入输出、数据传输方向和真实架构债务整理成一个可维护基线，避免后续在两套并行模型上继续堆功能。

## 2. 关键发现

### 2.1 当前有两个并行内核

- Web 工作台使用 `CandidateProfile + JobPosting`，只做单 JD 硬条件判断并保存在进程内；
- 文件 Agent 使用 `CandidateDocumentProfile + CatalogJob`，只做技能证据 Top-K、缺口和计划，结果不保存。

因此当前一次运行不能同时回答“硬条件是否通过”和“在多个岗位中技能证据如何排序”。后续必须先定义 mapper 或统一聚合，不能继续增加第三套候选人/岗位模型。

### 2.2 Agent Run 只有输出，没有状态存储

`CareerAgentRun` 已经包含 run ID、节点状态、匹配、缺口、计划和 Reviewer，但只进入 stdout 或 HTTP response。服务端没有 AgentRun Repository、文档 Repository 或检查点，run ID 目前不能用于查询和恢复。

### 2.3 本地岗位采集仍是实验脚本

工作区中的 CJS 脚本连接已经登录的 Chrome CDP，访问招聘网站并把完整页面正文写入 JSON。它们：

- 未进入 Git 和 CI；
- 没有 Node 依赖锁；
- 输入输出文件名和日期硬编码；
- 没有统一 Source Adapter、Schema、幂等或失败分类；
- 不在 Agent Trace 中。

因此它们不能被称为当前 Agent Tool。正式化前继续保持人工触发，并把浏览器 Profile 与认证页面输出排除在 Git 之外。

## 3. 形成的基线

新增 [Agent 工程架构与数据流](../AGENT_ARCHITECTURE.md)，覆盖：

- 9 个运行入口的输入、输出和副作用；
- 模块目录与期望依赖方向；
- 两套候选人和岗位模型的差异；
- 文件 Agent 七个节点的逐步数据流；
- LLM 外传字段和禁止外传字段；
- `CareerAgentRun` 字段来源；
- Web 结构化链的保存与匹配方向；
- 错误、降级、状态生命周期和脚本自动化；
- 当前 P0/P1/P2 架构缺口；
- Gold Set、模型桥接、持久化、语义抽取、Source Adapter 和 UI 的推荐顺序。

## 4. 安全改动

`.gitignore` 新增：

- `.browser-profile-jobs/`；
- `data/authenticated_job_pages_*.json`；
- `data/boss_authenticated_job_pages_*.json`。

这些规则不删除本地文件，只防止包含登录状态或认证页面正文的产物被误提交。CJS 源码仍保持未跟踪，等待正式 Tool 设计后再决定是否纳入工程。

## 5. 下一步

1. 制作匿名技能/JD/Top-K Gold Set，并冻结 `CareerAgentRun` JSON Fixture；
2. 定义 `CandidateAggregate`、`JobAggregate` 或过渡 mapper；
3. 将硬条件过滤接入文件 Agent；
4. 定义持久化 Repository 和迁移，再实现检查点；
5. 之后才接语义抽取、采集 Source Adapter 和新 Web。

## 6. 30 秒表达

> 我没有在 0.2.0 后继续堆新功能，而是先追踪所有入口的数据流，发现项目实际上有一条 Web 硬条件链和一条文件技能证据链，两套候选人/岗位模型尚未统一。Agent Run 虽然有完整 Trace，但没有持久化；本地采集 CJS 也只是复用登录浏览器的实验，不是正式 Tool。我把这些边界固化成架构基线，并先阻止浏览器 Profile 和认证页面快照误进 Git。下一步用 Gold Set 冻结契约，再合并模型和做持久化。
