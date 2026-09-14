# 迭代 024：候选人投入确认领域契约

> 日期：2026-09-14
> 阶段：Phase 2B.4 人工确认输入
> 状态：完成

## 1. 目标

为每周可到岗天数和可连续实习月数建立类型化人工确认输入，使缺少简历证据的投入条件可以从 `unknown` 变为可比较事实，同时不伪造文档引用。

## 2. 实现

- `CandidateAvailabilityConfirmation` 分别约束每周 `1-7` 天和至少 `1` 个月。
- `ConfirmedCandidateFact` 保存值、单位和 `user_confirmation` 来源。
- `DecisionEvidenceItem` 分离 `candidate_evidence` 与 `candidate_confirmation`。
- `extract_decision_signals()` 可选消费确认输入，并复用文档抽取的同一最低值比较语义。
- 未提供确认值时行为完全不变，仍返回 `unknown` 和人工确认警告。

## 3. 验证

合成岗位要求每周 4 天、连续 3 个月：

- 无确认输入：两项均为 `unknown`；
- 确认每周 5 天、连续 2 个月：分别为 `met` 和 `unmet`；
- hard compatibility 为 `0.5`；
- `candidate_evidence` 保持为空，确认来源单独记录。

领域契约以及 Agent、API、CLI 入口测试通过。API 在未开启自动决策信号时返回 422，CLI 在同类误用时拒绝执行。

## 4. 边界

Agent 的路径和文档入口、API 的 `candidate_availability` 对象，以及 CLI 的 `--candidate-weekly-days` / `--candidate-duration-months` 已贯通。三个入口都只在显式开启自动决策信号时接受确认输入。私有 Gold 仍不应在用户确认前把现有 `unknown` 改为 `met`。

## 5. 下一步

1. 向用户收集真实每周到岗天数和连续实习月数。
2. 使用确认值复跑逐项 Gold，比较 hard item known rate 与排序指标。
3. 指标不足时先分析缺失事实或抽取误差，不直接调整权重。