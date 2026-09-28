# Lina 岗位发现、订阅与推送设计

> 状态：`JobLead`、快照搜索、21 家双池公司目录、每周调度、HTTP 健康探针和 artifact 已实现；实时岗位列表解析、跨周变化和推送尚未实现。
> 下一切片：为一个可稳定读取职位列表与地点字段的官方来源实现真实解析器和 Fixture。

## 1. 目标

Lina 根据用户的即时搜索和持久化订阅检查公司官方招聘来源，找出匹配岗位及其变化，并生成可解释、可追溯的推荐 Inbox、即时提醒和周期摘要。

它不是自动海投工具。Lina 负责发现、整理、匹配和提醒；是否投递、使用哪个简历版本以及提交哪些字段始终由用户逐次确认。

## 1.1 两种触发方式

- **即时搜索**：对话或搜索表单产生类型化条件，立即查询选定来源并返回结果；
- **持续订阅**：保存相同条件，由本地调度器周期运行，只推送新增、重要变化和临近截止事项。

两种方式复用同一适配器、规范化、去重、匹配和证据链，不能维护两套搜索逻辑。

## 2. 首批监控源

| 公司 | 官方来源 | 初始关注词 |
| --- | --- | --- |
| 腾讯 | [腾讯招聘](https://careers.tencent.com/) | Agent Memory、RAG、知识图谱、评测、向量检索 |
| 字节跳动 | [字节跳动招聘](https://joinbytedance.com/) | 大模型应用、搜索、数据算法、AI 产品 |
| 阿里巴巴 | [阿里招聘](https://talent.alibaba.com/) | 搜索推荐、智能客服、AI 应用 |
| 蚂蚁集团 | [蚂蚁招聘](https://talent.antgroup.com/) | 大模型评测、金融 AI、Agent、数据智能 |
| Microsoft | [Microsoft Careers](https://careers.microsoft.com/) | Applied Science、Data Science、AI Engineering |
| Amazon | [Amazon 上海实习搜索](https://www.amazon.jobs/en/search?base_query=intern&loc_query=Shanghai%2C%20China) | OpenSearch、SDE、AI/ML |
| Meltwater | [Meltwater Careers](https://www.meltwater.com/en/careers) | AI、Data、Product Analytics |

主池另包含小红书、Apple 和 NVIDIA。专注型 AI 探索池包含 MiniMax、Baseten、Cohere、Fireworks AI、Anyscale、LlamaIndex、Pinecone、Weaviate、ElevenLabs、LangChain 和 Together AI。完整地区、方向和关注理由由 `GET /companies` 与代码注册表统一提供。

“专注型 AI”是可观察的产品方向分类，不是对融资轮次、估值或经营状态的断言。

关键词不是简单的大小写字符串列表。后续将维护中英文别名和概念组，例如 `RAG`、`retrieval augmented generation`、`检索增强生成` 属于同一概念。地点、毕业年份、职位类型和经验要求作为独立过滤条件，不混入关键词得分。

## 3. Inbox 与推送内容

推荐 Inbox 和周期摘要应包含：

1. **本周摘要**：成功来源数、失败来源数、新增、更新、关闭和高匹配岗位数。
2. **优先查看**：通过硬条件且匹配度高的岗位，附推荐理由、能力证据和主要缺口。
3. **新增岗位**：首次出现且仍开放的岗位。
4. **重要更新**：职责、资格、地点或截止时间发生实质变化的岗位。
5. **需要复核**：来源证据不足、字段冲突或匹配置信度低的岗位。
6. **来源健康**：抓取失败、页面结构变化、疑似限流和最后成功时间。
7. **建议行动**：收藏、忽略、比较、准备投递、定制简历或加入学习计划；默认只生成草稿。

每条岗位必须展示官方 URL、公司、标题、地点、更新时间、变化类型、匹配理由和证据。无法确认仍开放的岗位不得标记为“可投递”。

## 4. 数据流

```mermaid
flowchart LR
    QUERY[Manual Search or Schedule] --> RUN[Discovery Run]
    RUN --> ADAPTERS[Source Adapters]
    ADAPTERS --> RAW[Raw Snapshots]
    RAW --> NORMALIZE[Normalize and Validate]
    NORMALIZE --> DEDUPE[Fingerprint and Dedupe]
    DEDUPE --> DIFF[Cross-week Change Detection]
    DIFF --> RULES[Hard Constraints]
    RULES --> SEMANTIC[Semantic Match]
    SEMANTIC --> VERIFY[Evidence Verifier]
    VERIFY --> INBOX[Recommendation Inbox]
    INBOX --> NOTIFY[Notification Policy]
    NOTIFY --> HUMAN[User Review]
```

调度器只负责触发，不承载业务逻辑。同一个工作流必须支持命令行手动运行、API 触发和定时触发，便于调试与补跑。

## 5. 来源适配器契约

每个招聘网站实现统一适配器，而不是把来源判断散落在 Agent Prompt 中：

```python
class JobSourceAdapter(Protocol):
    source_id: str

    async def fetch(self, request: FetchRequest) -> FetchResult: ...
```

`FetchResult` 至少包含：

- 抓取开始和结束时间；
- 来源状态：成功、部分成功、限流、结构变化、禁止访问或未知失败；
- 原始岗位记录及官方 URL；
- 页码、游标或下一页信息；
- 可用于审计的错误分类，但不记录 Cookie、Token 等敏感信息。

适配器必须支持超时、有限重试、指数退避和速率限制。某一来源失败时，其他来源继续处理，但 Inbox 和摘要必须显示该来源数据不完整。

## 6. 去重与变化检测

岗位身份按以下优先级确定：

1. 官方来源提供的稳定职位 ID；
2. 规范化后的官方 URL；
3. 公司、规范化标题、地点和职位类型组成的复合键。

岗位正文经过字段规范化后生成内容指纹。与上次成功快照比较，产生：

- `new`：首次发现；
- `updated`：关键字段或正文发生实质变化；
- `closed`：在连续成功采集中消失，或官方明确标记关闭；
- `reopened`：关闭后再次出现；
- `uncertain`：来源失败或证据不足，不能判断状态。

单次消失不能直接判定关闭，避免分页故障或临时限流造成误报。

## 7. 匹配与排序

监控工作流复用主项目的匹配逻辑：

1. 先检查地点、毕业年份、学历、经验和职位类型等硬条件。
2. 再比较技能、项目证据、方向偏好和成长价值。
3. 新鲜度与变化类型只影响展示优先级，不篡改能力匹配分。
4. 每个分数必须附命中项、缺口、证据和置信度。

Inbox 排序建议综合岗位匹配分、发布时间、新增/更新状态和用户关注公司，但权重必须可配置，并通过真实点击、收藏和投递反馈逐步校准。

## 8. 调度与运行方式

真实个人资料首版采用本地调度器；公开 CI 只运行匿名 Fixture。稳定后可为不含隐私的来源发现使用 GitHub Actions `schedule` 加 `workflow_dispatch`：

- 每周固定时间自动运行；
- 允许手动触发和指定单个来源调试；
- 使用 `year-week + profile_version` 作为幂等键；
- 机密配置存储在 GitHub Secrets，不写入日志和仓库；
- 原始简历默认不进入云端任务，公开 CI 使用匿名画像。

如果真实个人资料只允许本地保存，则改用本地 cron/LaunchAgent 运行采集和匹配，GitHub Actions 仅运行匿名 Fixture 测试。

## 9. 合规与安全边界

- 优先使用官方公开 API、结构化数据、RSS 或允许访问的公开页面。
- 遵守站点服务条款、robots、访问频率和地区要求。
- 不绕过登录、验证码、访问控制、反爬机制或付费限制。
- 未经渠道授权不发送邮件或消息；未经逐次审批不使用求职者账号提交申请。
- 页面不可访问时保留失败记录，并提供粘贴 JD 或手动导入作为降级路径。
- 快照只保存完成去重和审计所需的内容，并按保留策略清理。

## 10. 测试与评测

首版必须包含：

- 每个适配器的本地 HTML/JSON Fixture 契约测试；
- 分页、空结果、超时、限流和页面结构变化测试；
- 同批数据重复运行的幂等测试；
- 跨周新增、更新、关闭、重新开放和不确定状态测试；
- 多来源重复岗位测试；
- Inbox 与摘要中的 URL、证据和推荐理由完整性测试。

核心指标：

| 指标 | 含义 |
| --- | --- |
| 来源成功率 | 本周成功或部分成功来源占比 |
| 变化检测准确率 | 与人工标注相比，岗位状态变化判断的准确程度 |
| 去重准确率 | 重复岗位被正确合并且不同岗位未误合并的比例 |
| 有效链接率 | 推荐岗位 URL 仍可访问的比例 |
| 推荐采纳率 | 用户收藏或进入投递准备的推荐岗位比例 |
| 推送新鲜度 | 从来源变化到 Inbox/提醒生成的时间 |

## 11. 实施顺序

1. 定义 `JobLead`、`JobSearchRequest`、`JobSourceAdapter` 和来源失败类型。
2. 用本地 Fixture 覆盖分页、空结果、限流、超时和结构变化。
3. 选择一个公开、稳定且条款允许的来源完成真实适配器与手动搜索 API。
4. 接入内容指纹、去重和现有硬条件/技能匹配，返回官方 URL 与证据摘要。
5. 增加 Inbox、收藏、忽略、对比和来源健康状态。
6. 持久化搜索订阅，增加本地调度、变化事件和站内推送。
7. 扩展来源和外部通知渠道；每次只增加一个适配器并补齐 Fixture。

这个顺序的核心是先证明数据可信，再让 LLM 参与推荐。否则语义分析可能建立在缺失、重复或过期岗位之上。

## 12. 面试表达

可以将这一能力概括为：

> 我把岗位发现与订阅设计成一个有状态、可恢复的数据工作流，而不是定时爬虫。即时搜索和定时订阅复用统一适配器；快照和内容指纹支持跨周期变更检测，幂等键防止重复事件。单一来源失败不会阻断其他来源，也不会被误报为零岗位；确定性硬条件先过滤，并为每个推荐保留官方来源和证据。