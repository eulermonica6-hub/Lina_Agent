# 迭代 021：决策信号桥接与排序消融

> 日期：2026-09-14
> 阶段：Phase 2B.1 排序特征验证
> 状态：人工确认信号桥接完成；自动抽取待实现

## 1. 问题与假设

技能抽取、匹配和引用指标已经达到 `1.0`，但技能排序 Pairwise Accuracy 只有 `0.3`。本轮验证一个可证伪假设：排序差异主要来自硬条件风险和职业方向偏好，而不是 required/preferred/contextual 三类技能权重。

## 2. 实现

- `DecisionSignals` 保存 `hard_compatibility`、`direction_alignment` 和人工解释。
- `DecisionWeights` 将技能、硬条件和方向分量分开，默认组合为 `0.3 / 0.2 / 0.5`。
- `RankedJobMatch` 同时暴露技能原始分、综合分和决策信号，避免综合分失去解释。
- `CareerMatchAgent` 可选接收按岗位编号索引的已确认信号；未提供时完全保持原 skill-only 行为。
- 评测 CLI 新增 `--ablate`，一次输出三组结果。

当前实现刻意不从自由文本自动生成决策信号。私有 Gold 中的信号是人工确认标签，用于验证评分结构的上限，不是生产预测。

## 3. 消融结果

| 组合 | 预测排序 | Pairwise | Top-1 |
| --- | --- | ---: | ---: |
| skill-only | `4 > 5 > 2 > 1 > 3` | `0.3` | `0.0` |
| hard + skill | `5 > 2 > 4 > 1 > 3` | `0.3` | `0.0` |
| hard + direction + skill | `1 > 2 > 3 > 4 > 5` | `1.0` | `1.0` |

硬条件本身没有改善相对排序，方向信号才是本数据集中的主要区分变量。由于方向标签与人工排序来自同一轮专家判断，最终 `1.0` 只能视为 oracle 上限，不能宣称为自动系统准确率。

## 4. 学习笔记

1. 消融实验应一次只增加一类信息，否则无法判断提升来自哪里。
2. 综合分必须保留每个分量；只返回一个数字会让人工确认信号看起来像模型能力。
3. `unknown` 不能编码为 `0`。缺失信号应从动态分母移除，`0` 只表示人工确认的不兼容或不匹配。
4. 人工标签可以验证评分接口和上限，但不能代替抽取器评测。
5. 方向偏好是用户上下文，不是 JD 的客观属性；后续必须保存来源、确认状态和版本。

## 5. 验证

```bash
uv run --locked python -m lina_agent.evaluation.career_matching \
  data/private/evaluation/career_matching_gold_v1.json --ablate \
  > data/private/evaluation/career_matching_ablation_v2.json
```

完整门禁结果：116 项测试通过，语句与分支覆盖率均为 100%，Ruff 与 Pyright strict 通过。

## 6. 下一步

1. 从匿名简历确定性提取毕业年份、学历、期望地点和目标方向，保留证据与未知状态。
2. 从 JD 基本信息提取毕业届次、学历、到岗天数和持续月份。
3. 将自动抽取结果送入本轮已验证的 `DecisionSignals` 接口，并和人工标签分别评测。
4. 自动信号未通过评测前，CLI/API 不默认启用综合排序。