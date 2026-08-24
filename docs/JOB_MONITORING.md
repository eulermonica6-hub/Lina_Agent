# Lina 每周岗位监控设计

> 状态：规划中，当前版本尚未实现来源适配器、持久化快照、调度或周报。
> 前置条件：跨周去重、变化检测和幂等运行依赖持久化；语义排序依赖可解释匹配工作流。Fixture 来源、规范化和内容指纹可先独立开发。

## 1. 目标

Lina 每周检查一组目标公司的官方招聘来源，找出与候选人方向相关的岗位变化，并生成一份可解释、可追溯的个性化周报。

它不是自动海投工具。Lina 负责发现、整理、匹配和提醒，是否投递、使用哪个简历版本以及是否创建外部任务始终由用户确认。

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

关键词不是简单的大小写字符串列表。后续将维护中英文别名和概念组，例如 `RAG`、`retrieval augmented generation`、`检索增强生成` 属于同一概念。地点、毕业年份、职位类型和经验要求作为独立过滤条件，不混入关键词得分。

## 3. 周报内容

每周报告应包含：

1. **本周摘要**：成功来源数、失败来源数、新增、更新、关闭和高匹配岗位数。
2. **优先查看**：通过硬条件且匹配度高的岗位，附推荐理由、能力证据和主要缺口。
3. **新增岗位**：首次出现且仍开放的岗位。
4. **重要更新**：职责、资格、地点或截止时间发生实质变化的岗位。
5. **需要复核**：来源证据不足、字段冲突或匹配置信度低的岗位。
6. **来源健康**：抓取失败、页面结构变化、疑似限流和最后成功时间。
7. **建议行动**：建议投递、补充资料、定制简历或加入学习计划；默认只生成草稿。

每条岗位必须展示官方 URL、公司、标题、地点、更新时间、变化类型、匹配理由和证据。无法确认仍开放的岗位不得标记为“可投递”。

## 4. 数据流

```mermaid
flowchart LR
    CRON[Weekly Trigger] --> RUN[Monitoring Run]
    RUN --> ADAPTERS[Source Adapters]
    ADAPTERS --> RAW[Raw Snapshots]
    RAW --> NORMALIZE[Normalize and Validate]
    NORMALIZE --> DEDUPE[Fingerprint and Dedupe]
    DEDUPE --> DIFF[Cross-week Change Detection]
    DIFF --> RULES[Hard Constraints]
    RULES --> SEMANTIC[Semantic Match]
    SEMANTIC --> VERIFY[Evidence Verifier]
    VERIFY --> DIGEST[Weekly Digest Draft]
    DIGEST --> HUMAN[Human Review]
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

适配器必须支持超时、有限重试、指数退避和速率限制。某一来源失败时，整个周报继续生成，但必须显示该来源数据不完整。

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

周报排序建议综合岗位匹配分、发布时间、新增/更新状态和用户关注公司，但权重必须可配置，并通过真实点击、收藏和投递反馈逐步校准。

## 8. 调度与运行方式

首版建议采用 GitHub Actions 的 `schedule` 加 `workflow_dispatch`：

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
- 不使用求职者账号自动投递，不自动发送邮件或消息。
- 页面不可访问时保留失败记录，并提供粘贴 JD 或手动导入作为降级路径。
- 快照只保存完成去重和审计所需的内容，并按保留策略清理。

## 10. 测试与评测

首版必须包含：

- 每个适配器的本地 HTML/JSON Fixture 契约测试；
- 分页、空结果、超时、限流和页面结构变化测试；
- 同批数据重复运行的幂等测试；
- 跨周新增、更新、关闭、重新开放和不确定状态测试；
- 多来源重复岗位测试；
- 周报中的 URL、证据和推荐理由完整性测试。

核心指标：

| 指标 | 含义 |
| --- | --- |
| 来源成功率 | 本周成功或部分成功来源占比 |
| 变化检测准确率 | 与人工标注相比，岗位状态变化判断的准确程度 |
| 去重准确率 | 重复岗位被正确合并且不同岗位未误合并的比例 |
| 有效链接率 | 周报岗位 URL 仍可访问的比例 |
| 推荐采纳率 | 用户收藏或进入投递准备的推荐岗位比例 |
| 周报新鲜度 | 从来源变化到周报生成的时间 |

## 11. 实施顺序

1. 用本地 Fixture 实现 `JobSourceAdapter` 契约和变化检测，不访问真实网站。
2. 选择一个公开、稳定且条款允许的来源完成首个真实适配器。
3. 接入硬条件匹配，先生成 JSON/Markdown 周报。
4. 增加来源健康状态、失败告警和手动补跑。
5. 扩展到其余来源；每次只增加一个适配器并补齐 Fixture。
6. 匹配工作流稳定后再加入语义评分和通知渠道。

这个顺序的核心是先证明数据可信，再让 LLM 参与推荐。否则语义分析可能建立在缺失、重复或过期岗位之上。

## 12. 面试表达

可以将这一能力概括为：

> 我把每周岗位监控设计成一个有状态、可恢复的数据工作流，而不是定时爬虫。不同招聘网站通过统一适配器隔离，原始快照和内容指纹支持跨周变更检测，幂等键防止重复事件。单一来源失败不会阻断周报，也不会被误报为零岗位；确定性硬条件先过滤，Agent 只处理需要语义理解的匹配，并为每个推荐保留官方来源和证据。