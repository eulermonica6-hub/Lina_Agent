# 技能证据与 Top-K 排序基线

> 数据版本：`2026-09-15-v2`
> 数据范围：5 条上海 AI 实习匿名 JD + 1 份匿名简历
> 隐私边界：原始 JD、匿名目录、Gold Label 和完整 JSON 报告均位于 `data/private/`

## 指标口径

- **技能 Precision / Recall**：比较岗位内 `required`、`preferred`、`contextual` 三类规范技能标签。
- **匹配 Precision / Recall**：比较模型认定“简历有证据支持”的岗位技能与人工 Gold。
- **引用有效率**：引用的文档 ID 和字符偏移必须精确还原引用文本。
- **引用支持率**：引用文本必须是对应规范技能的已登记别名，不能只靠邻近文本推断。
- **Pairwise Accuracy**：Gold 排名中任意两个岗位的相对顺序是否预测正确。
- **Top-1 Accuracy**：预测首位是否等于人工首位。

## 首轮结果

| 指标 | 默认权重 `0.7 / 0.2 / 0.1` |
| --- | ---: |
| 岗位技能 Precision / Recall / Exact Match | `1.000 / 1.000 / 1.000` |
| 候选人匹配 Precision / Recall / Exact Match | `1.000 / 1.000 / 1.000` |
| 引用有效率 / 支持率 | `1.000 / 1.000`（64 条引用） |
| 预测排序 | `4 > 5 > 2 > 1 > 3` |
| Gold 排序 | `1 > 2 > 3 > 4 > 5` |
| Pairwise Accuracy | `0.300` |
| Top-1 Accuracy | `0.000` |

20 组可解释权重网格中，最佳结果为 `required=0.7`、`preferred=0.0`、`contextual=0.3`，预测排序 `4 > 2 > 5 > 1 > 3`，Pairwise Accuracy 提升到 `0.400`，Top-1 仍为 `0.000`。

## 校准结论

不修改默认权重。当前 Gold 排名综合了实习时长、方向贴合度和发展目标，而评分器只看已识别技能覆盖率。岗位 4 的技能要求较少且均有简历证据，因此即使一年承诺是明显风险，仍会获得高分。仅调三类技能权重无法表达该信息，继续拟合会在 5 条小样本上制造虚假改善。

下一轮应先加入两个确定性特征，再重新校准：

1. 硬条件兼容度：毕业年份、地点、每周天数、持续月份和学历。
2. 方向适配度：Agent 主线、通用 ML、基础设施、风控算法等目标岗位族偏好。

## 决策信号消融

在人工确认的硬条件兼容度和方向适配度上运行 oracle 消融：

| 组合 | Pairwise Accuracy | Top-1 Accuracy |
| --- | ---: | ---: |
| skill-only | `0.300` | `0.000` |
| hard + skill | `0.300` | `0.000` |
| hard + direction + skill | `1.000` | `1.000` |

这证明当前 5 条样本中方向偏好是主要缺失变量，但不代表自动抽取准确率。下一步需分别评测信号抽取和组合排序，不能把人工标签结果包装成线上能力。

## 候选人投入确认复跑

用户确认每周可到岗 5 天、可连续实习 12 个月后，18 项硬条件的逐项已知率从 `0.50` 提升到 `1.00`，未知项从 `9` 降至 `0`，hard signal MAE 从 `0.15` 降至 `0.00`。逐项状态准确率和证据 Precision/Recall/有效率均保持 `1.00`。

用户进一步确认岗位 3 与岗位 4 同优先级。评测使用并列 Gold 后，预测排序仍为 `1 > 4 > 2 > 5 > 3`，Pairwise Accuracy 按 9 个明确顺序对重算为 `0.778`；人工 hard + direction + skill oracle 恢复 `1.000`。

自动路径只剩 `2 > 4` 和 `3 > 5` 两个逆序对。两组岗位内部的自动方向值相同，排序被技能覆盖分主导，说明下一步需要类型化方向偏好强度，而不是继续调整 hard 或组合权重。

## 复现

```bash
uv run --locked python -m lina_agent.evaluation.career_matching \
  data/private/evaluation/career_matching_gold_v1.json --ablate \
  > data/private/evaluation/career_matching_ablation_v2.json
```

Gold 必须在查看模型输出前冻结；若因标注越界修订，应记录理由并完整重跑。当前数据只用于建立工程基线，不代表生产准确率。