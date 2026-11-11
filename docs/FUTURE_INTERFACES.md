# Lina 未来接口与扩展预留

> 适用版本：0.2.46
> 目的：把「当前已被代码固化、可以稳定依赖的端口」与「只存在于计划中的方向」分开记录，避免后续迭代把路线图写成已实现能力。

## 1. 稳定端口（可依赖，改动需走兼容迁移）

这些是当前代码中已经存在的、其他模块真实依赖的接口。新增实现应优先复用它们，而不是另起一套。

### 1.1 岗位来源适配器

```python
# application/job_discovery.py
class JobSourceAdapter(Protocol):
    source_id: str

    async def search(self, request: JobSearchRequest) -> JobSourceResult: ...
```

- 输入 `JobSearchRequest`（query / companies / locations / job_types / max_results）。
- 输出 `JobSourceResult`（source_id / status / fetched_at / leads / error_code）。
- 每个 `JobLead` 是唯一可去重、可排序、可监控的岗位单元；关键字段 `deduplication_key`、`application_key`、`verification_status`、`content_fingerprint`。
- 已有实现：`VerifiedSnapshotJobSource`、`NvidiaWorkdayJobSource`、`AshbyJobSource`。
- **新增一个 HTTPS 官方来源** 应参照 `AshbyJobSource`：parametrize `source_id / company / org / pool`，返回 `JobSourceResult`，HTTP/结构错误走 `JobSourceStatus`，绝不用空结果冒充失败来源。

### 1.2 来源目录（可审阅的事实来源）

```text
Infrastructure/job_sources/company_catalog.toml  →  MonitoredJobSource
```

- TOML 是唯一可审阅名单，`registry.load_company_catalog` 校验 `schema_version`、`source_id` 唯一、`company` 唯一。
- `MonitoredJobSource` 携带 `pool`（domestic_major / global_major / focused_ai）、`keywords`、`regions`、`market_cap_*`。
- 新增公司 = 在目录加一条 + 在 `main.py` 装配对应 `JobSourceAdapter`，两处必须同步。

### 1.3 文档摄取

```python
# domain/documents.py  →  DocumentFormat  StrEnum
# Infrastructure/document_loader.py  →  LocalDocumentLoader
```

- `DocumentFormat` 已含 `markdown / text / docx / pdf`。
- `LocalDocumentLoader.load_bytes(source_name, bytes) -> IngestedDocument` 按扩展名分派到 `_load_text / _load_docx / _load_pdf`。
- 统一产物 `IngestedDocument`（`SourceEvidence` / `DocumentBlock` / `content_hash` / 稳定 UUIDv5）。
- **新增文件格式** 应新增一个 `DocumentFormat` 值 + 一个 `_load_*` reader，仍返回同一 `IngestedDocument`，不要把自定义文本结构渗透到调用方。

### 1.4 存储与仓库

- `CandidatesProfileRepository`、`JobApplicationRepository`、`JobChangeRepository` 等 Protocol 定义在 `application/repositories.py`；内存与 SQLite 两个适配器已存在。
- Agent Run Snapshot / Confirmation Version / Document Reference 走 SQLite（schema 版本化管理）。

## 2. 预留但尚未实现的扩展方向

以下来自产品目标与当前能力边界，**尚未实现**，不要在文档/代码中写成已上线。

| 方向 | 现状 | 预留/依赖 |
| --- | --- | --- |
| 保存搜索 / Search Profile | 未实现 | 需要 `JobSearchRequest` + 订阅持久化与调度 |
| 语言语义技能抽取 | 未实现（当前为词表确定性匹配） | 必须挂 `SourceEvidence` 引用，幻觉不参与打分 |
| 扫描 PDF OCR / 版面 | 未实现（文本型 PDF 已支持） | 需要 OCR/版面 Provider + 隐私边界 |
| 公司/薪资证据源 | 未实现 | 需要授权与事实来源，不能只靠模型陈述 |
| PostgreSQL / 分布式调度 / 外部推送 | 未实现 | 依赖仓库协议与幂等键先稳定 |
| 辅助投递（外部写） | 未实现，禁止无人值守海投 | 需逐次预览 + 用户确认 + 审计 |

## 3. 新增能力的检查清单

新增一个来源 / 格式 / 仓库时，逐项确认：

1. 复用既有 Protocol，不新增平行接口，除非旧接口确实不够用且已有迁移说明。
2. 输出 Schema 有 Pydantic 契约，失败分类进统一 `status`/`error_code`。
3. 有内容指纹或稳定 ID，支持去重与变化检测。
4. 公开页面与认证页面的授权边界明确，登录态数据不进入 Git 或模型上下文。
5. 网络失败、结构变化与空结果三种情况有区分测试。
6. 同步 `company_catalog.toml` / `DocumentFormat` / 重要文档与 releaseNote。
7. 私有真实样本只放在 `data/private/`，不进入版本控制。