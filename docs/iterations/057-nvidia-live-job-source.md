# 迭代 057：NVIDIA 实时官方岗位解析器

> 日期：2026-09-30
> 版本：0.2.39
> 状态：首个真实官方岗位列表解析器已接入手动搜索与每周监控

## 1. 来源选择

Apple 的结构化搜索 API 需要认证；字节招聘页面的直接 HTTP 响应主要是 SPA 外壳。NVIDIA Workday CXS 提供无需登录的官方 JSON POST 接口，稳定返回职位总数、分页列表、标题、地点文本、职位编号、发布时间和详情路径，因此选为首个真实来源。

接口：

```text
POST https://nvidia.wd5.myworkdayjobs.com/wday/cxs/nvidia/NVIDIAExternalCareerSite/jobs
```

## 2. 实现

`NvidiaWorkdayJobSource`：

- 默认检索上海岗位，并按 Workday `offset` / `limit` 分页；
- 规范化职位编号、标题、上海地点、官方详情 URL 和抓取时间；
- 从标题确定实习、校招或全职类型；
- 从标题提取 AI、Deep Learning、Machine Learning、GPU、CUDA、SoC、软件工程和测试标签；
- 当前官方列表中的职位标记为 `live`；
- 支持关键词、公司、地点、岗位类型和结果上限过滤；
- 分类 401/403、429、5xx、结构变化和网络错误。

## 3. 装配边界

- `POST /opportunities/search` 在 development/production 聚合核验快照与 NVIDIA 实时源；
- test 环境只使用核验快照，测试不会访问公网；
- 首页 `GET /opportunities` 与 `POST /opportunities/recommended` 继续只使用核验快照，公网失败不会影响首页；
- 每周监控对 `nvidia-careers` 使用真实解析器，其余来源继续使用 HTTP 健康探针。

## 4. Fixture 与验收

离线 Fixture 冻结 Workday 的真实响应字段，覆盖：

- 多页抓取；
- 上海、北京和多地点文本；
- 实习、New College Graduate 和全职标题；
- AI、GPU/CUDA、软件工程和默认方向；
- 本地二次过滤和去重；
- 空页、无效 JSON、字段缺失、403、429、500 和网络失败。

真实 API 验收使用 `AI + NVIDIA + 上海 + internship`，成功返回 AI Infra、Compute System Arch AI Infra 和 TensorRT-LLM 等官方职位。

## 5. 下一步

当前只解析列表级字段，没有抓取详情正文或保存跨批次状态。下一迭代应持久化岗位详情指纹和抓取批次，生成新增、更新、关闭与重新开放事件。
