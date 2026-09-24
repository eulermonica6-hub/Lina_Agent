# 迭代 030：第二个冻结 Gold 与官方 JD 回归

> 日期：2026-09-24
> 阶段：Phase 2B.9 第二独立 Gold
> 状态：1 条新官方 JD 已冻结；其余 4 条候选待完整官方页

## 1. 目标

从扩展 backlog 中获取完整官方 JD，建立第二个独立 Gold，并用真实措辞验证方向 taxonomy 与多数据集稳定性。职位摘要、聚合站转载和搜索片段均不作为 Gold 证据。

## 2. 官方来源核验

本轮在官方招聘页确认一条上海/深圳学生岗位，职位号和完整来源仅保存在 Git 忽略的私有原始快照。页面提供摘要、职责、最低要求和优先条件，足以支持技能、学历、地点和实习时长标注。

另外四条候选目前只能定位到招聘聚合页、项目宣传页或搜索摘要，未满足“官方域名 + 完整正文”条件，因此继续留在 backlog。

## 3. 第二个 Gold

新增单岗位独立 Gold：

- 学历：本科或硕士在读，候选人硕士在读，`met`；
- 地点：上海或深圳，候选人期望上海，`met`；
- 时长：至少 4 个月全职，候选人已确认 12 个月，`met`；
- 方向：全栈 AI 工具与测试自动化，用户确认偏好为 `0.0`；
- 技能缺口：TypeScript 是最低要求但不在当前技能 taxonomy，且简历没有直接证据。

单岗位 `gold_ranking=[1]` 只表示集合内唯一元素，不表达它与原 5 岗的相对偏好，因此无需伪造跨岗位排序。

## 4. 失败与修复

首次自动评测结果：

- hard coverage / MAE：`1.0 / 0.0`；
- hard item accuracy、证据 Precision/Recall：均为 `1.0`；
- direction coverage：`0.0`；
- direction MAE：`null`。

根因是官方 JD 使用“测试自动化 / test automation”，而 `fullstack_ai_testing` taxonomy 只包含 Full Stack、CUDA 和 AI 测试等别名。新增这两个直接证据别名后，新集 direction coverage 提升为 `1.0`，MAE 为 `0.0`。

同时为 suite 增加 macro/minimum direction coverage。否则 unknown 会被 MAE 排除，报告可能继续显示 MAE `0.0`，掩盖整套数据的召回失败。

## 5. Suite 结果

| 指标 | 修复前 | 修复后 |
| --- | ---: | ---: |
| 数据集数 | `2` | `2` |
| 岗位数 | `6` | `6` |
| 方向族覆盖率 | `1.0` | `1.0` |
| macro direction coverage | `0.5` | `1.0` |
| minimum direction coverage | `0.0` | `1.0` |
| macro / maximum direction MAE | `0.0 / 0.0` | `0.0 / 0.0` |
| macro / minimum Pairwise | `1.0 / 1.0` | `1.0 / 1.0` |

Pairwise 在单岗位集上没有比较对，只用于保持报告结构一致，不能作为第二集排序质量证据。

## 6. 知识与行为准则

- MAE 只统计已知预测，必须与 coverage 联合报告；`MAE=0` 且 `coverage=0` 不是成功。
- 官方 JD 的真实措辞可以驱动 taxonomy 扩展，但新增 alias 必须有具体失败样本和回归测试。
- 单岗位 Gold 可验证抽取和证据契约，不能证明相对排序能力。
- 跨数据集稳定性必须同时看 macro 与 minimum，避免平均值隐藏整集失败。
- 搜索引擎片段只用于发现来源，不能替代官方正文或进入引用 Gold。

## 7. 下一步

继续为剩余四个 backlog 候选定位完整官方招聘页；至少再取得两条不同方向岗位后，请用户确认新集合内部排序或 ties，再评估真正的跨岗位 Pairwise 稳定性。

## 8. 面试表达

第二个 Gold 首轮出现了 `direction MAE=null`、覆盖率为零的真实失败。若只看 suite MAE，旧数据集会让宏观结果仍显示零误差。我因此补充宏平均和最差方向覆盖率，并用官方 JD 中的“测试自动化”措辞扩展 taxonomy。修复后两集六岗方向覆盖恢复为 100%，同时明确单岗位 Pairwise 不构成排序证据。
