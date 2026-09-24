# 迭代 038：版本化 Agent Run Snapshot

> 日期：2026-09-24
> 阶段：Phase 3A.2 Agent 历史持久化
> 状态：脱敏 Snapshot 可跨重启保存与查询

## 1. 问题

`CareerAgentRun` 包含候选人/JD evidence text、字符 offset 和源文件名，直接序列化入库会复制敏感原文。与此同时，只保存最终分数会丢失请求确认、步骤状态、gap 与计划，无法支持历史比较和审计。

## 2. Snapshot 契约

新增 `AgentRunSnapshot(schema_version=1)`，保存：

- run ID 与 UTC 创建时间；
- candidate / job catalog 文档 UUID 引用；
- 请求参数、投入确认与方向偏好；
- run state 和岗位计数；
- 匹配分数、hard/direction 分量及技能名称摘要；
- gap 优先级与受影响岗位编号；
- action plan 与 deterministic review；
- step 的 name / role / status；
- warning 数量。

明确不保存：

- Base64 请求内容；
- 原始/匿名简历与 JD 正文；
- evidence text 与 start/end offset；
- 源文件名；
- step summary 和 warning 原文。

## 3. Repository 与 API

- 新增 `AgentRunSnapshotRepository`；
- 内存与 SQLite adapter 均支持 save/get/list_recent；
- SQLite schema 从 v1 统一升级为 v2，确保三张表并防止 repository 连接回写旧版本；
- POST `/agent/runs` 成功后异步保存 Snapshot，但即时响应仍是完整 `CareerAgentRun`；
- GET `/agent/runs/{run_id}` 返回单条 Snapshot；
- GET `/agent/runs?limit=20` 按 `created_at` 降序返回最近记录；
- 未知 run ID 返回 404。

## 4. 验证

- 使用唯一简历/JD sentinel 和私密文件名创建 Run；
- 新 FastAPI app 使用同一数据库后可查询 Snapshot；
- 响应中不存在 sentinel、文件名、`start_offset` 或 `end_offset`；
- recent limit 与 created_at 排序正确；
- SQLite Snapshot 跨 repository 实例恢复；
- v1 数据库打开后升级到 user_version 2 并补齐三张表；
- test 环境继续使用内存 Snapshot repository。

## 5. 失败与修复

1. 初版 SQLite 各 repository 只创建自己的表并写 `user_version=1`。新增 Snapshot 后，旧 repository 连接可能把版本降回 1。修复为所有连接统一确保完整 schema 并设置 v2。
2. recent 若按 rowid，upsert 和乱序写入会破坏时间语义。修复为解析 Snapshot 后按 UTC `created_at` 降序排序。
3. Agent API 测试 fixture 曾调用默认 development app，会写本地 SQLite。修复为显式 `environment=test`，保持自动化隔离。

## 6. 知识与行为准则

- 持久化 Run 前必须先定义脱敏投影，不能复用完整响应模型。
- Snapshot 的 schema version、created_at 和文档引用是历史迁移与比较的最小基础。
- 原始证据应通过独立 Document Repository 管理，Snapshot 只保存稳定引用。
- recent 语义必须由时间字段定义，不能依赖数据库物理插入顺序。
- schema migration 必须由统一初始化器推进，不能让每个 repository 自行声明版本。
- “可查询历史”不等于“可恢复执行”；检查点和重放仍是后续能力。

## 7. 当前边界

已完成：结构化画像/岗位、脱敏 Agent Run Snapshot 跨重启持久化。

未完成：原始文档仓库、确认事实版本、Snapshot 之间 diff、执行检查点、Run 重放与恢复。

## 8. 下一步

定义 `DocumentReference` 和 `CandidateConfirmationVersion`：文档正文保留在私有文件/对象存储边界，SQLite 只保存 hash、document ID、来源类型、版本和保留策略；Snapshot 引用这些版本，支持可解释历史比较。

## 9. 面试表达

我没有直接持久化包含原文 evidence 的 Agent 响应，而是设计 schema-versioned 脱敏 Snapshot。测试用 sentinel 证明重启后可查询 run，同时数据库响应不含原文、offset 或私密文件名。SQLite 从 v1 迁移到 v2，并按 created_at 而非 rowid 定义 recent，为后续文档版本、diff 和恢复保留演进空间。
