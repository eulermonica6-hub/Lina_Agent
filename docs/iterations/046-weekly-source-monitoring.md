# 迭代 046：Lina 每周官方来源监控

> 日期：2026-09-28
> 阶段：岗位发现可靠性基础
> 状态：7 源周次调度、健康探针与 artifact 已完成

## 1. 目标

让 Lina 每周检查用户指定的 7 个官方招聘入口，并生成可审计报告。当前先解决“来源是否可访问、是否限流、是否被阻断、解析器是否就绪”，不把首页可访问误报成已获取岗位。

## 2. 监控来源

- 腾讯招聘：Agent Memory、RAG、知识图谱、评测、向量检索；
- 字节跳动招聘：大模型应用、搜索、数据算法、AI 产品；
- 阿里招聘：搜索推荐、智能客服、AI 应用；
- 蚂蚁招聘：大模型评测、金融 AI、Agent、数据智能；
- Microsoft Careers：Applied Science、Data Science、AI Engineering；
- Amazon 上海：OpenSearch、SDE、AI/ML；
- Meltwater Careers：AI、Data、Product Analytics。

公司、官方 URL 和关键词由类型化 `MonitoredJobSource` 注册表维护，并写入每次报告。

## 3. 运行模型

`WeeklyMonitoringRun` 包含：

- 固定 Agent 名 `Lina`；
- `lina-weekly:YYYY-MM-DD` 周一幂等 ID；
- 开始/结束时间；
- `complete`、`partial` 或 `failed`；
- 7 个来源配置；
- 每个来源的状态、错误码、抓取时间和 leads；
- 全局去重后的 leads。

单一来源失败不会终止其他来源。全部成功才是 `complete`；成功与待处理/失败混合为 `partial`；全部阻断、限流、结构变化或失败为 `failed`。

## 4. HTTP 健康探针

`OfficialCareersPageProbe` 使用 `httpx.AsyncClient`，支持重定向、20 秒超时和 Lina 用户代理。状态分类：

- HTTP 200 且有正文：`partial/listing_parser_pending`；
- 空正文：`structure_changed/empty_page`；
- 401/403：`blocked`；
- 429：`rate_limited`；
- 其他 4xx/5xx：`failed/http_NNN`；
- 网络异常：`failed/network_error`。

HTTP 200 只证明入口可访问，不证明已经解析岗位列表。

## 5. 调度与输出

新增命令：

```bash
uv run --locked lina-monitor --output artifacts/weekly-monitor.json
```

`.github/workflows/weekly-job-monitor.yml` 每周一 01:00 UTC 运行，也支持 `workflow_dispatch`。报告通过 GitHub Actions artifact 保存，不提交仓库，不读取简历、Cookie、Token 或招聘账号。

## 6. 首次真实运行

2026-09-28 手动运行结果：

- Agent：Lina；
- 周次：`lina-weekly:2026-09-28`；
- 7/7 入口返回可读取正文；
- 7/7 标记 `partial/listing_parser_pending`；
- 没有把入口成功伪装成岗位采集成功。

探测还发现 Amazon 给定上海查询 URL 返回的嵌入搜索请求中 `location=null`，页面结果包含全球岗位。因此 Amazon 解析器必须单独验证地点语义，当前不能产出上海岗位。

## 7. API

新增 `GET /monitoring/sources`，供页面或诊断工具读取 7 个来源的公司、官方 URL 和关键词。当前运行报告通过 CLI/workflow 生成，尚未持久化到 SQLite 或显示在网页 Inbox。

## 8. 验证

新增测试覆盖：

- 7 源注册表顺序、URL 和关键词；
- HTTP 200/403/429/500、空页和网络错误；
- Lina 身份、周一幂等键和三种运行状态；
- CLI 文件输出和 stdout；
- workflow 的 schedule、手动触发与 artifact；
- 监控来源 API。

全量 222 项测试通过，其中 21 项 Playwright；核心语句与分支覆盖率 100%。

## 9. 下一步

为一个来源实现真正的岗位列表解析器。优先选择能稳定提供公开职位列表和地点字段的来源；默认测试使用保存 Fixture，真实探针独立运行。解析器通过后再接第二来源和跨周变化检测。

## 10. 行为准则

- 首页健康不等于岗位列表健康；
- 查询 URL 存在不等于筛选参数生效；
- 来源失败不能变成空岗位结果；
- 周报必须携带监控关键词，不能只记录内部 ID；
- 定时任务不携带个人简历和招聘账号秘密；
- 解析器未完成时明确 `listing_parser_pending`。
