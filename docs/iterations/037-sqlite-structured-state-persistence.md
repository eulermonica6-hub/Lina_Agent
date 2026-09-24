# 迭代 037：SQLite 结构化状态持久化

> 日期：2026-09-24
> 阶段：Phase 3A.1 持久化基础
> 状态：Web 候选人画像与岗位可跨重启恢复

## 1. 目标

先持久化已有结构化 Web 决策链中的 `CandidateProfile` 与 `JobPosting`，验证 Repository 边界能够替换存储适配器；不在缺少版本契约时把文件 Agent Run、原始文档、证据和计划塞进同一个 JSON 表。

## 2. 实现

- 新增标准库 SQLite repository adapter，实现现有 `save/get/list_all` Protocol；
- 领域对象使用 Pydantic JSON 序列化与验证，UUID、枚举和集合可完整恢复；
- UUID 字符串作为主键，`INSERT ... ON CONFLICT DO UPDATE` 保持 upsert 语义；
- 每次 async 操作通过 `asyncio.to_thread` 使用独立 SQLite 连接；
- 启用 WAL、5 秒 busy timeout 和 schema `user_version=1`；
- 延迟建表，导入应用不会立即创建数据库文件；
- development / production 默认使用 `data/lina.db`；
- `environment=test` 或 `database_path=None` 使用内存 adapter；
- `LINA_DATABASE_PATH` 可覆盖路径；数据库、WAL、SHM 文件均被 Git 忽略。

## 3. 验证

- 一个 repository 实例保存，另一个新实例可读取；
- JobPosting upsert 跨实例保持最新值；
- 未知 UUID 返回 `None`；
- 10 条候选画像并发写入后全部可恢复；
- 第一个 FastAPI app 保存画像和岗位，第二个 app 使用同一数据库后可直接执行匹配；
- 测试环境继续使用内存，不污染本地数据库；
- 环境变量路径解析与显式禁用持久化均有测试。

## 4. 知识与行为准则

- Repository Protocol 是持久化替换点，路由和用例不应感知 SQLite。
- async API 中不能长期复用默认线程绑定的 SQLite connection；小型本地负载使用 `to_thread + per-operation connection`。
- 测试必须证明跨实例恢复，而不是在同一对象上 save/get。
- JSON payload 适合冻结现有小型结构化实体，但 Agent Run 需要独立版本、索引和生命周期字段。
- 本地 SQLite 文件包含个人求职信息，默认不进 Git；当前没有静态加密，不应放入共享目录。
- WAL 适合本地单用户并发，不等于生产多节点数据库方案。

## 5. 当前边界

已持久化：

- Web `CandidateProfile`；
- Web `JobPosting` 与结构化硬条件。

尚未持久化：

- 原始/匿名文档和 offset 证据；
- 候选投入与方向确认；
- 文件 Agent Run、步骤 Trace、Top-K、gap 和 action plan；
- benchmark artifact 元数据；
- Web 抽取预览与保存实体之间的证据关联。

## 6. 配置

```env
LINA_ENVIRONMENT=development
LINA_DATABASE_PATH=data/lina.db
```

`LINA_DATABASE_PATH` 必须是有效文件路径；嵌入式调用可在代码中传 `database_path=None` 回退到内存 adapter，自动化测试由 `environment=test` 强制隔离。

## 7. 下一步

定义版本化 `AgentRunSnapshot`：保存 run ID、输入文档引用、候选确认版本、岗位目录版本、确定性结果、可选计划、状态与创建时间；先完成 schema 和 repository，再接 API 查询，不存原始敏感文件正文。

## 8. 面试表达

我没有从路由直接写 SQLite，而是复用已有 Repository Protocol，增加 JSON adapter 并保持内存实现用于测试。验收不是同一对象 save/get，而是新 repository 和新 FastAPI app 跨重启读取；同时用 WAL、busy timeout、独立连接和并发测试固化本地单用户语义。Agent Run 因版本和隐私边界不同，被明确留到下一张表和下一次迁移。
