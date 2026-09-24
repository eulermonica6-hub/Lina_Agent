# 迭代 039：文档引用与候选确认版本

> 日期：2026-09-24
> 阶段：Phase 3A.3 输入版本关联
> 状态：Snapshot v2 可关联 metadata-only 文档引用与用户确认版本

## 1. 问题

Snapshot v1 只保存内容级 document UUID，并在 request 内嵌确认值。它无法区分“同一内容作为简历或 JD 上传”的角色，也无法把一次用户确认作为独立版本查询和比较。直接保存文件名或正文又会扩大敏感数据面。

## 2. DocumentReference

新增 metadata-only `DocumentReference`：

- `reference_id`：由 `document_id + kind` 生成的稳定 UUID5；
- `document_id`：由内容 hash 生成的稳定内容身份；
- SHA-256 content hash；
- format、kind、source 和 retention policy；
- byte / character / block count；
- observed_at。

不保存 source filename、正文、block text 或 offset。将 reference ID 与 document ID 分开，可让同一 bytes 分别作为 `candidate_resume` 和 `job_catalog` 被引用，而不发生主键/角色冲突。

## 3. CandidateConfirmationVersion

一次确认生成独立 version UUID，保存：

- availability；
- direction preferences；
- `user_confirmation` 来源；
- UTC created_at；
- 对规范化事实 JSON 计算的 SHA-256 facts hash。

相同事实重复确认会拥有不同 version ID，但 facts hash 相同，可在后续 diff 中识别“版本事件相同、内容未变”。无确认事实时不创建版本。

## 4. Snapshot 与 API

- 新 Snapshot 默认 `schema_version=2`；
- 保留 `schema_version=1` 读取兼容；
- 新增 candidate/job document reference ID；
- 新增 candidate confirmation version ID；
- POST Agent Run 保存两个引用、可选确认版本和 Snapshot；
- GET `/agent/documents/{reference_id}` 查询 metadata；
- GET `/agent/confirmations/{version_id}` 查询确认版本；
- 未知 ID 返回 404。

## 5. SQLite Schema v3

统一 schema 增加：

- `document_references`；
- `candidate_confirmation_versions`。

DocumentReference 使用 insert-if-absent，保持稳定引用不可变；确认版本使用独立 UUID 正常插入。所有 repository 连接统一确保五张表并设置 `user_version=3`。

## 6. 验证

- 同一内容作为 resume/JD 时 document ID 相同、reference ID 不同；
- DocumentReference 字段不含 `text` 或 `source_name`；
- 相同确认事实的两个版本 ID 不同、facts hash 相同；
- 空确认不创建版本，直接构造空版本被拒绝；
- Snapshot v2 跨 app 重启查询并关联两个引用和确认版本；
- sentinel 正文、私密文件名和 offset 不出现在 Snapshot/Reference；
- DocumentReference 重复保存不会覆盖首次 metadata；
- SQLite v1 可升级到 v3；Snapshot v1 仍可读取。

## 7. 失败与修复

初始设计拟直接用 `document_id` 作为带 kind 的引用主键。审查发现相同 bytes 可能同时作为简历和 JD，内容身份与使用角色不是同一概念。修复为独立 `reference_id = UUID5(document_id + kind)`，Snapshot 同时保留内容 ID 和引用 ID。

## 8. 知识与行为准则

- 内容身份、观察事件和业务角色应使用不同 ID，不要让一个主键承担三种语义。
- metadata-only 必须由模型字段白名单保证，不能依赖“调用方不要传正文”的约定。
- 用户确认是版本事件；version ID 表示事件，facts hash 表示内容。
- 不可变引用应使用 insert-if-absent，而不是 upsert 覆盖历史 metadata。
- schema 演进必须兼容读取旧 Snapshot，写入使用最新版本。
- Snapshot 可关联输入版本后，才能做可靠 diff；仍不能据此恢复节点执行。

## 9. 下一步

实现 Snapshot diff：比较两个 Run 的文档 content hash、确认 facts hash、匹配顺序、分数组件、gap 和计划变化；输出结构化差异，不加载原始正文。

## 10. 面试表达

我把文档内容身份、上传角色和用户确认事件拆成三种版本语义。DocumentReference 只保存 hash 和统计 metadata；相同内容作为简历/JD 会得到不同 reference ID。确认版本使用随机 version ID 和稳定 facts hash。Snapshot v2 关联这些版本，同时兼容读取 v1，从而为后续历史 diff 建立了不复制敏感正文的基础。
