# JD 硬条件解析基线评测

> 评测日期：2026-08-23
> 数据集：`tests/fixtures/job_parser_evaluation.json`
> 样例数：6
> 解析器：确定性规则第一版

## 1. 结论

| 指标 | 结果 |
| --- | ---: |
| 字段 Precision | 100% |
| 字段 Recall | 62.5% |
| 整条 JD Exact Match | 50% |
| 证据 Precision | 100% |
| 证据 Recall | 62.5% |
| 正确字段 | 10 |
| 错误提取字段 | 0 |
| 漏提取字段 | 6 |

当前解析器是高精度、有限召回的预填工具：识别出的字段可信度较高，但没有识别到不代表原文没有要求。因此工作台必须保留人工确认，不能自动将空值解释为“岗位不限”。

## 2. 数据集组成

数据集使用匿名、人工编写的代表性中文 JD 表达，不包含真实公司、个人信息或受版权保护的完整岗位正文。

| 案例 | 目的 | 当前结果 |
| --- | --- | --- |
| `standard-campus-role` | 标准单年份、学历、经验、地点 | 完全匹配 |
| `multiple-years-and-locations` | 多年份、多地点、零经验 | 完全匹配 |
| `no-explicit-constraints` | 不应推断未声明条件 | 完全匹配 |
| `base-and-graduation-variant` | `Base 地`、`2026 年毕业`、`本科起` | 3 项漏提取 |
| `labelled-requirements-variant` | `学历要求`、`至少 1 年`、`办公地点` | 学历、地点漏提取 |
| `education-choice-variant` | `本科或硕士均可` | 学历漏提取 |

前三条整例完全正确，后三条至少有一个字段不匹配，因此 Exact Match 为 $3 / 6 = 50\%$。

## 3. 指标口径

评测单位是四类结构化字段：

1. `graduation_years`
2. `minimum_education`
3. `minimum_years_of_experience`
4. `locations`

规则如下：

- 预测值与标注值完全一致且非空：1 个 True Positive；
- 标注非空但预测为空：1 个 False Negative；
- 标注为空但预测非空：1 个 False Positive；
- 两者非空但不一致：同时计 1 个 False Positive 和 1 个 False Negative；
- 两者都为空：不计入 Precision/Recall，但参与整例 Exact Match；
- 集合字段必须整体一致，不按集合中的单个元素拆分计分。

$$
Precision = \frac{TP}{TP + FP} = \frac{10}{10 + 0} = 100\%
$$

$$
Recall = \frac{TP}{TP + FN} = \frac{10}{10 + 6} = 62.5\%
$$

证据指标以证据原文字符串为单位，比较解析器返回文本和人工标注文本。字符偏移正确性另由领域测试保证：

```python
description[start_offset:end_offset] == evidence.text
```

## 4. 运行方式

```bash
PYTHONPATH=src .venv/bin/python -m lina_agent.evaluation.job_parser \
  tests/fixtures/job_parser_evaluation.json
```

输出是机器可读 JSON，可在后续 CI、模型对比或评测仪表板中直接消费。

## 5. 失败分类

### 毕业年份表达

当前支持 `2027 届`，漏掉 `2026 年毕业生`。下一版可以将两种形式规范化为同一年份集合，同时避免把普通年份误识别为毕业年份。

### 学历表达

当前支持 `本科及以上`、`硕士以上`，漏掉：

- `本科起`；
- `学历要求：硕士`；
- `本科或硕士学历均可`。

第三种表达需要理解最低门槛是本科，不能简单取文本中最高学历。

### 地点表达

当前只支持 `工作地点：上海`，漏掉：

- `Base 地在杭州`；
- `办公地点：广州`。

地点解析应扩展标签词典，但需防止把团队所在地、出差地或公司总部误当成岗位地点。

### 经验表达

`至少 1 年相关经验` 当前能通过内部子串 `1 年相关经验` 正确识别。证据没有包含“至少”，值正确但展示上下文偏短，后续可改善证据跨度。

## 6. 下一版准入标准

下一次修改解析规则后必须：

- 在同一数据集上 Precision 保持 100%；
- Recall 高于 62.5%；
- Exact Match 高于 50%；
- 原有领域与 API 测试全部通过；
- 新增规则必须配套至少一个反例，防止关键词误提取。

数据集只有 6 例，指标用于回归和方向判断，不代表生产总体效果。扩充到真实匿名 JD 前，不应把该百分比用于外部效果宣传。