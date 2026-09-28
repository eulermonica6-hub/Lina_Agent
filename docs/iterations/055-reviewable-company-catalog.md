# 迭代 055：可审核公司清单

> 日期：2026-09-28
> 版本：0.2.37
> 状态：公司目录已迁移为单一结构化数据源

## 1. 问题

公司名称、分组、招聘入口、地区、关键词和纳入理由原先硬编码在 Python 注册表中。人工审核需要阅读构造函数调用，也容易在代码与文档之间产生重复清单。

## 2. 实现

- 新增 `src/lina_agent/infrastructure/job_sources/company_catalog.toml`，集中维护全部 32 家公司；
- 清单按国内大厂、国外大厂和探索型分组，保留官方招聘 URL、地区、关键词和关注理由；
- `registry.py` 只负责读取 TOML，并通过 `MonitoredJobSource` 执行 Pydantic 校验；
- 应用启动时拒绝不支持的 schema 版本、重复来源 ID 和重复公司名；
- TOML 作为 package data 随 wheel 一同发布。

## 3. 人工审核流程

1. 打开 `company_catalog.toml`；
2. 检查公司名称、`pool`、官方 URL、`regions`、`keywords` 和 `why_watch`；
3. 修改后运行 `pytest tests/test_company_catalog.py`；
4. 再运行完整质量门禁，确认推荐、监控和打包行为未回归。

公司池仍是内部召回策略，不通过公共 API 或首页展示。
