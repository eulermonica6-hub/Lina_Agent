# 迭代 012：首个证据驱动职业匹配 Agent

> 日期：2026-08-26
> 类型：文档摄取、证据匹配、Agent 编排、经济型模型 Provider
> 状态：已完成

## 1. 用户目标与开发顺序

用户提供 1 份包含 29 个真实岗位的 Markdown JD 文件和 7 份不同阶段的真实 DOCX 简历，希望先建立 Agent 核心，再补爬虫、PDF 和包装功能。

本轮按工程依赖实施：

```text
文件字节 -> 规范化证据块 -> 候选人/JD 技能事实 -> 确定性覆盖排序
        -> Supervisor Trace -> 显式 opt-in 的模型行动计划 -> API/CLI
```

先做内核的原因是：爬虫只增加输入数量，PDF 只增加输入格式，前端只增加交互。如果证据、排序和停止条件尚未稳定，继续增加入口只会放大不可验证行为。

## 2. 真实数据先导出的设计结论

审计发现 7 份 DOCX 都包含文本框，其中 1 份通过普通 Word 段落接口得到 0 段、0 表格，但 OOXML 中实际存在 386 个文本节点。只使用 `python-docx.document.paragraphs` 会静默生成空画像。

因此首版读取器直接处理 DOCX ZIP 包中的 `word/document.xml`，遍历叶子段落并读取 `w:t`。父文本框段落不会重复计入，正文、表格单元格和文本框使用同一证据块契约；真正无文本时抛出明确错误。

当前不处理页眉页脚、批注、图片、扫描件 OCR 和版面恢复。这个边界把“文本层解析”与以后需要视觉模型的“版面理解”分开。

## 3. 核心领域契约

每个输入转换为 `IngestedDocument`：

- 内容 SHA-256 与基于指纹的稳定 UUID；
- 原始来源名和格式；
- 规范化全文；
- 带类型、序号、起止字符偏移的证据块。

JD 目录进一步转换为独立岗位，并保留标题、公司、职责、要求、来源、状态及每条原文证据。技能抽取区分：

1. 明确要求；
2. “优先、加分”等偏好项；
3. 职责中的上下文技能。

覆盖分对三类分别计算并加权，只表示当前词表能够找到的证据覆盖，不表示录取概率。报告单独展示明确要求覆盖率与缺口，避免总分掩盖硬技能事实。

## 4. 为什么先用一个 Supervisor

当前步骤共享同一份文档证据，依赖是线性的，摄取、解析和计分都有确定性实现。拆成多个会对话的智能体会增加上下文复制、结果漂移、成本和调试面，却没有独立决策收益。

本轮使用一个 Supervisor 编排多个类型化工具，并记录五个基础步骤；启用模型计划时追加第六步。未来只有当公司研究、材料改写和学习计划能够并行、使用不同工具并分别验收时，才升级为专门子智能体。

## 5. 经济型 Provider 与隐私边界

Groq、NVIDIA 和 DeepSeek 共用 OpenAI-compatible 适配器。默认 `auto` 顺序为 Groq、NVIDIA；DeepSeek 是付费档，不会自动进入路由，除非显式选择或设置 `allow_paid_fallback`。

Groq 官方限额按 organization 计算，项目不通过多 key 轮换叠加免费额度。网络错误、429、无效成功响应和选定 5xx 可以切换下一 Provider；400 等非瞬时错误立即失败，避免掩盖错误配置。

`--use-llm` 只发送规范化技能标签、Top 岗位标题/公司、覆盖项和缺口，不发送文件名、联系方式、文档证据原句。真实私有简历的模型验收因缺少敏感派生数据外传授权而未执行；无隐私连通性探针已验证 Groq。

官方依据：

- [Groq OpenAI compatibility](https://console.groq.com/docs/openai)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [NVIDIA NIM LLM API](https://docs.api.nvidia.com/nim/reference/llm-apis)
- [NVIDIA NIM development access](https://docs.api.nvidia.com/nim/docs/run-anywhere)
- [DeepSeek models and pricing](https://api-docs.deepseek.com/quick_start/pricing)

## 6. 实施中出现的真实失败

1. 第一次真实汇总误用 `python -m lina_agent.cli.career_match`，模块没有启动钩子，随后补充 `python -m lina_agent.cli` 并加回归测试。
2. JD 空列表项分支使覆盖率停在 99.74%，补充脏输入用例后恢复到 100%。
3. 首次免费 Provider 探针只给 8 个输出 Token，模型返回空 `content`；适配器现将空内容视为无效响应并允许安全降级，默认 Groq 模型也改为更适合中文的 Qwen。
4. 本机仓库 `.venv` 是 Linux 格式，Windows Pyright 无法使用；使用临时本机配置指向锁定的 Windows 环境完成 strict 检查，随后删除临时文件。

## 7. 私有样本验收

私有数据只在本地内存中处理，没有写入报告文件或版本控制：

- 7/7 DOCX 解析成功；
- 每份简历得到 42–104 个证据块；
- 早期样本识别 2 项技能，后期样本识别 10–16 项；
- JD 稳定解析 29 个岗位，其中 28 个默认参与排序；
- 早期样本 Top-1 覆盖分为 50，后期样本为 100。

这些数字只证明管线能够运行并区分阶段，不证明排序正确。下一步必须制作匿名人工 Top-K 和字段标注，测量排序一致性、技能 Precision/Recall 和引用支持率。

## 8. 当前 Agent 定位与下一步

当前可以称为“有界工作流 Agent”：它有明确目标、工具、状态、证据、顺序、停止条件、可选模型节点和结果 Schema。它还不是通用自主 Agent，因为没有会话记忆、持久化、失败恢复、动态任务规划、开放式工具选择或多智能体协作。

最优先的下一步不是爬虫或 PDF，而是人工标注首批真实匿名样本，校准技能词表与 Top-K；随后持久化文档、确认状态和 Agent Run。PDF 文本层读取本身不难，困难在扫描件 OCR、双栏顺序、表格和引用偏移，应在统一证据契约稳定后单独加入。

## 9. 30 秒表达

> 我先用 7 份真实 DOCX 发现普通 Word 段落接口会把文本框简历读成空文档，因此直接在 OOXML 层建立统一证据块和字符偏移。之后把 29 个真实 JD 拆成独立岗位，用确定性词表区分硬要求、优先项和职责上下文，再由单 Supervisor 生成可解释 Top-K 与完整 Trace。模型只用于显式启用的匿名化行动计划，Provider 默认从 Groq 降级到 NVIDIA，DeepSeek 不自动付费。这样项目已经是一个有界、可测试的 Agent，而不是把 Prompt 包在框架里。
