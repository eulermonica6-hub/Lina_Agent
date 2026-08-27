# 016：VS Code 工程框架与完整技术书

## 用户问题

当前仓库已经能够运行 Web 硬条件工作台和文件职业匹配 Agent，但后续在 VS Code 内继续开发时缺少统一的工作区、调试入口和完整代码阅读地图。已有文档分别说明产品、数据流和开发命令，却没有一本从模块契约讲到扩展方法与未来行动的工程技术书。

## 本次范围

本次不改变 0.2.0 业务行为，不搬动经过测试的生产模块，也不把本地求职网站实验脚本转为正式 Tool。交付内容是：

- 可提交且跨开发者复用的 `.vscode` 配置；
- 根目录 `Lina_Agent.code-workspace`；
- 完整的工程代码技术书；
- README、开发指南、文档治理、知识库、路线图和 Release Notes 同步；
- 文档契约增加技术书入口。

## 为什么不立即重排源码目录

当前 `api/application/domain/infrastructure/cli/web` 分层已经清晰，100 项测试固定了行为。此时大规模移动文件主要产生导入路径和历史噪声，并不能解决双业务链未统一、语义匹配未评测这些核心问题。

因此本次先固定“怎样打开、怎样读、怎样调试、怎样扩展”，并把 Application 默认构造文件适配器等依赖折中记录为架构债务。等出现数据库、第二种 Loader 或状态图实现时，再以真实变化驱动 Port 与 Composition Root 重构。

## 工作区设计

### Settings

- UTF-8 与 LF；
- Python strict 分析和 `src` 路径；
- Python 保存时由 Ruff 格式化并显式提供 fix/import actions；
- 测试侧栏默认跳过 `tests/web`，用于快速开发循环；
- 隐藏/排除缓存、虚拟环境、私有数据和浏览器 Profile。

没有提交固定的 Python 解释器绝对路径。Windows、WSL 和 CI 的虚拟环境不同，开发者应各自使用 `Python: Select Interpreter`；工作区和任务则分别设置 `.venv-windows` 与 `.venv-wsl`，防止 `uv` 误操作另一平台的环境。

验证时发现 `pyproject.toml` 的 Pyright 配置仍固定读取 `.venv`，导致 Windows 工具把 WSL 环境中的 `fastapi`、`pytest` 等依赖报告为不存在。显式传入 Windows Python 后恢复为 0 错误，证明是解释器解析问题；随后移除单一 venv 硬编码，让 CLI 使用当前 `uv run` 环境、Pylance 使用当前选中解释器。

### Launch

- FastAPI 8000 调试；
- 使用公开匿名 Fixture 调试文件 Agent；
- 调试当前 pytest 文件。

FastAPI 调试配置不启用 reload，避免重载子进程干扰断点；需要热更新时使用独立任务。

### Tasks

- 锁定依赖同步与 Chromium 安装；
- 匿名离线 Agent 冒烟；
- 锁文件、Ruff、Pyright、快速测试；
- 带 Playwright、Trace 和 100% 覆盖率门槛的完整测试；
- 按顺序执行全部检查的默认 Build Task。

## 技术书的核心判断

1. 当前是有界多节点工作流 Agent，不是自主多 Agent 群聊。
2. 当前 LLM 只生成行动计划，不参与 Top-K 语义匹配。
3. 无 LLM 路径不是简单整段字符串比较，而是固定 Taxonomy、别名边界、证据分类和加权覆盖基线。
4. 最终语义匹配应由 LLM 输出证据关系，由 Verifier 检查引用，再由确定性 Scorer 评分。
5. 下一步必须先制作匿名 Gold Set；否则无法证明模型、Prompt 或权重调整是否改善结果。
6. Web 硬条件链和文件证据链应在语义垂直切片后统一，不再新增平行业务内核。

## 未来顺序

```text
匿名 Gold Set 与 lexical baseline
  -> 语义关系 Schema + Context Builder + LLM Mapper
  -> 证据 Verifier + 确定性 Scorer + 降级状态
  -> 统一硬条件链与文件证据链
  -> 文档/证据/确认状态/Agent Run 持久化与恢复
  -> PDF、Agent 工作台、岗位采集和简历优化
```

PDF 和爬虫仍后置。PDF 首版应只支持可搜索文本并显式拒绝扫描件；爬虫必须先具备合法来源策略、快照、幂等、去重和失败可观测性。

## 验证计划

本次不提高产品版本，因为没有新增最终用户能力或修改外部 API。完成标准：

1. 所有 VS Code JSON 文件可解析；
2. 文档契约能确认 README 直接链接技术书；
3. `uv lock --check`、Ruff、Pyright、pytest 和 Playwright 全部通过；
4. `git status` 不包含私有资料、Key、浏览器 Profile 或用户实验脚本的误提交。

## 学习总结

代码框架的价值不等于目录层数。真正可持续的框架需要同时固定：类型化契约、依赖方向、Composition Root、失败语义、测试镜像、调试入口和演进门槛。只有这些边界清楚，后续引入 LLM、数据库或状态图才是替换适配器和增加节点，而不是重写整个项目。
