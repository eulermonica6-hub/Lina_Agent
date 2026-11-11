# Lina 功能介绍与案例跑通

> 适用版本：0.2.46
> 说明：本文只描述当前真实可运行的功能，并用两份**匿名** PDF 简历演示从「文档摄取 → 证据画像 → 技能匹配 → 决策」的闭环。案例中的人名、联系方式与可识别信息已隐去。

## 1. 当前闭环可以做什么

Lina 现在是「确定性地面向证据」的求职 Agent，而不是可自由对话的黑箱。当前闭环由两条链组成：

1. **文件 Agent 证据链**：读取 TXT / Markdown / DOCX / PDF 简历，拆成带字符偏移的证据块，识别规范化技能，与 JD 目录做覆盖排序，聚合能力缺口。
2. **岗位发现与投递链**：从公司目录 + NVIDIA Workday + Ashby（Notion / Linear / Persona）刷新岗位，按画像推荐 Top-K，标记已投递并走状态时间线。

关键可用能力（0.2.46）：

- 简历/JD 本地匹配（`lina-match` / 浏览器文件 Agent / `POST /agent/runs`）。
- 文本型 PDF 简历解析（新增）；扫描件 OCR 仍不可用。
- 岗位发现、手动搜索、Top 6 推荐、来源监控、投递时间线与变化 Inbox。
- 确定性硬条件（毕业年 / 学历 / 经验 / 地点）+ 证据技能覆盖。

## 2. 案例：两份匿名 PDF 简历跑通

候选人为「候选人 L」：管科硕士研二，AI Agent 实习方向。两份简历均为真实 PDF，放在被 Git 忽略的 `data/private/`，未进入版本控制。

### 2.1 PDF 摄取插入统一证据模型

用 `LocalDocumentLoader` 直接读取两份 PDF（本轮新增 `.pdf` 支持）：

| 简历（匿名） | 格式 | 证据块数 | 规范化正文字符 |
| --- | --- | --- | --- |
| 简历 A（英文实习简历） | pdf | 52 | 4295 |
| 简历 B（中文管科硕士简历） | pdf | 53 | 3267 |

无效 PDF 与无文字层 PDF 会分别抛出「不是可解析的 PDF 文档」和「没有可读取的文本」，不会静默吞掉为空。

### 2.2 全链路匹配跑通

用简历 A 通过 `lina-match` 跑完整证据链（对匿名 JD 目录，Top-3）：

- 运行状态：`complete`。
- 简历 A 识别出 18 项规范化技能（含 Agent、Multi-Agent、RAG、LLM、LangGraph、Tool Calling、Knowledge Graph、Python、SQL、FastAPI、Pydantic、Docker、Git、PyTorch、Transformers 等，仅列匿名技能词）。
- 最佳匹配：`Agent 工程师`，证据覆盖分 100.0，已覆盖明确技能 RAG、Python，无未覆盖明确技能。
- 默认排除了 1 个已下线岗位。

这证明：**文本型 PDF 与 TXT/Markdown/DOCX 走同一条证据路径**，不再需要预先转成文本。

## 3. 本轮修复与新增

| 项目 | 内容 |
| --- | --- |
| PDF 摄取 | `DocumentFormat` 新增 `pdf`；`LocalDocumentLoader` 新增 `_load_pdf`（`pypdf`），并补齐 `pyproject` 依赖与失败分支测试。 |
| Ashby 来源 | 新增 `AshbyJobSource`，接入 Notion / Linear / Persona 的公开 Ashby 板，并纳入实时岗位发现与推荐。 |
| 来源目录 | `company_catalog.toml` 新增 3 个 global_major 来源，目录从 60 → 63。 |
| 文档同步 | 新增本文与《未来接口与扩展预留》；同步 USER_GUIDE、AGENT_ARCHITECTURE、releaseNote 中的格式/来源说明。 |

## 4. 验证

- 自动化测试：`pytest -m 'not browser'` → 272 passed（27 个浏览器用例单独运行）。
- 静态类型：被改动的 `src` 与 `tests` 文件 `pyright` 0 errors。
- 目录契约：`load_company_catalog` 校验通过，63 个来源 `source_id` 与 `company` 唯一。
- 版本一致性：`__version__` / `pyproject` / `releaseNote` 同步为 0.2.46。

## 5. 已知边界

- PDF 只支持文本层；扫描件、图片内文字仍需要 OCR（见《未来接口与扩展预留》）。
- 技能匹配仍是确定性词表，覆盖分不是录取概率；学历、年限、毕业时间仍需人工确认。
- Ashby 来源为远程/全球优先，上海岗位较少；推荐排序会优先本地偏好。
- 公开 ATS 来源的实时可用性受上游变更影响，失败会报告为 unavailable，不会被误认为「无岗位」。