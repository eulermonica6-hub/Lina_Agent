# 迭代 005：JD 解析离线评测基线

> 日期：2026-08-23
> 阶段：Phase 2 评测
> 状态：已完成

## 1. 用户问题

此前只有少量单元测试证明解析器在特定输入上正确，但无法回答三个关键问题：

- 当前解析器整体表现如何？
- 它更容易误提取还是漏提取？
- 下一次应该优先增加规则，还是引入 LLM？

本次目标是建立可重复运行的离线评测集和指标，为后续优化提供数字基线。

## 2. 初始假设与判定

**假设**：当前规则对标准表达精度高，但会漏掉 `Base 地`、`本科起`、`2026 年毕业生` 等替代表达。

**判定方式**：构造 6 个匿名代表性案例，其中 3 个使用已支持表达，3 个使用常见变体；运行生产解析器，计算字段 Precision、Recall、整例 Exact Match 和证据指标。

**结果**：Precision 100%、Recall 62.5%、Exact Match 50%，支持初始假设。

## 3. 实现内容

### 类型化标注

`JobParserEvaluationCase` 保存：

- 稳定案例 ID；
- 匿名 JD 描述；
- 四类期望约束；
- 期望证据原文集合。

Pydantic 在加载 JSON 时校验学历枚举、非负经验和必填文本，避免错误标注静默进入评测。

### 指标报告

`JobParserEvaluationReport` 返回：

- 案例数；
- TP、FP、FN；
- Precision、Recall；
- Exact Match；
- 证据 Precision、Recall；
- 失败案例 ID。

失败 ID 使报告不仅有总分，还能直接进入错误分析。

### 可重复 CLI

评测可脱离 pytest 运行：

```bash
PYTHONPATH=src .venv/bin/python -m lina_agent.evaluation.job_parser \
  tests/fixtures/job_parser_evaluation.json
```

JSON 输出可以后续接入 CI，比较规则版本、Prompt 或模型 Provider。

## 4. 测试驱动过程

### 失败一：评测模块不存在

先写指标语义测试，收集阶段得到：

```text
ModuleNotFoundError: No module named 'lina_agent.evaluation'
```

实现最小评测模型与计算后，测试转绿。

### 失败二：CLI 找不到 `lina_agent`

首次运行：

```bash
.venv/bin/python -m lina_agent.evaluation.job_parser ...
```

得到 `ModuleNotFoundError`。原因是当前虚拟环境尚未 editable install，pytest 能导入是因为 `pyproject.toml` 单独配置了 `pythonpath = ["src"]`。

修正为显式 `PYTHONPATH=src` 后 CLI 输出报告。这一过程说明“测试里能 import”不代表用户命令也能 import。

### 失败三：Pydantic 转换通过但 Pyright 报错

测试构造 `ExpectedJobConstraints` 时传入字符串 `"bachelor"`。Pydantic 运行时会转换为枚举，pytest 通过；Pyright strict 则正确指出构造器声明需要 `EducationLevel`。

测试改为显式传 `EducationLevel.BACHELOR`。JSON Fixture 仍由 Pydantic 在 I/O 边界负责转换，Python 代码内部保持静态类型一致。

## 5. 核心知识点

### 5.1 单元测试与离线评测回答不同问题

- 单元测试回答“某个规则是否按定义工作”；
- 离线评测回答“当前系统在一组代表性任务上的总体表现和失败分布”。

单元测试适合阻止已知行为回归，评测集适合比较版本和决定优化方向，两者不能互相替代。

### 5.2 Precision 与 Recall 体现产品取舍

当前产品将解析结果用于预填并要求人工确认。高 Precision 能减少错误填充，高 Recall 能降低手工输入成本。在数据集尚小时，应先保持 Precision，再逐步提升 Recall，避免为了多提取而引入错误约束。

### 5.3 空值不能当作正确提取抬高指标

很多 JD 不会声明全部四类约束。如果“预测空、标注空”也计为 TP，系统只要什么都不提取就能获得高准确率。因此空对空只参与整例一致性，不进入 Precision/Recall。

### 5.4 错误值同时是 FP 和 FN

例如标注地点是上海，预测为北京：系统既产生了一个错误结论，也漏掉了正确结论，所以同时计一个 FP 和一个 FN。这比只计“错误一次”更清楚地反映 Precision 和 Recall 损失。

### 5.5 指标必须能回到失败案例

只有 62.5% 无法指导开发。报告同时返回三个失败案例 ID，错误分析进一步定位为毕业年份、学历和地点表达缺口，下一轮可以逐类补规则和反例。

### 5.6 小数据指标不能外推

6 个案例适合建立工程回归基线，不足以估计真实岗位分布。数据是匿名人工编写的代表性表达，不应描述为生产准确率或真实市场效果。

## 6. 开发心得

1. 在引入 LLM 前先量化规则基线，才能判断模型是否真的带来提升。
2. 评测数据必须同时包含支持场景、失败场景和无约束场景。
3. 指标定义应先由小型手算案例固定，再对完整 Fixture 回归。
4. CLI 是评测的产品入口，不能只依赖 pytest 内部环境。
5. 运行时类型转换和静态类型检查解决不同问题，两者都要通过。
6. 失败案例 ID 比单一总分更接近可执行的开发任务。

## 7. 验证证据

- 6 例 JSON 标注集通过 Pydantic 加载；
- 指标语义测试用 2 例手算结果验证；
- Fixture 回归固定 Precision 1.0、Recall 0.625、Exact Match 0.5；
- CLI 输出包含 10 TP、0 FP、6 FN 和三个失败案例 ID；
- Pyright strict 与编辑器诊断通过；
- pytest：`29 passed`；
- 覆盖率：320 条语句、22 个分支均覆盖，合计 `100%`；
- Ruff format、Ruff check、Pyright strict、Markdown 链接与 `git diff --check` 全部通过。

## 8. 遗留风险

- 当前只有 6 个代表性案例，尚未覆盖真实匿名 JD 分布；
- 集合字段按整体计分，无法展示多地点中只漏一个的部分得分；
- 证据指标只比较文本，尚未独立聚合字符跨度准确率；
- 未记录每个字段的独立 Precision/Recall；
- CLI 依赖 `PYTHONPATH=src`，正式安装后应提供 console script；
- 评测尚未在 CI 中设置指标下降门禁。

## 9. 下一步

1. 为三个失败案例补充高精度规则和误提取反例；
2. 要求 Precision 保持 100%，Recall 和 Exact Match 提升；
3. 将标注集扩充到至少 10 个匿名真实 JD；
4. 增加字段级分项报告和 CI 回归门禁；
5. 再决定是否需要结构化 LLM 抽取。

## 10. 面试素材

### 30 秒表达

> 我没有因为规则解析器单元测试通过就宣称效果好，而是建立了 6 例匿名 JD 离线评测。先用两例手算固定 TP、FP、FN 和证据指标语义，再对完整数据集跑生产解析器。基线 Precision 是 100%，Recall 是 62.5%，Exact Match 是 50%，说明它适合作为保守预填，但会漏掉 Base 地、本科起等表达。这个结果让我先补高频规则和反例，而不是直接接 LLM，并为后续模型比较留下同一套评测标准。

### 高频追问

**为什么不用 Accuracy？**
四类字段中存在大量空值，空对空会让“什么都不抽取”的系统看起来准确。Precision 和 Recall 更能揭示误提取与漏提取。

**为什么集合字段整体计分？**
岗位匹配消费的是完整约束集合，漏掉一个允许年份可能改变业务结果。第一版采用严格整体匹配；后续可增加元素级指标作为诊断，但不替代严格指标。

**下一步如何提升？**
针对三个失败案例逐项增加窄规则，同时为每条规则添加容易误判的反例。只有在 Precision 不下降的前提下，Recall 提升才算有效。