# 迭代 024：候选人投入确认领域契约

> 日期：2026-09-14
> 阶段：Phase 2B.4 人工确认输入
> 状态：第 1 步完成；入口接线待完成

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

领域测试 11 项通过，Ruff 与 Pyright strict 通过。

## 4. 边界

本轮只完成领域契约。Agent、API 和 CLI 尚未传入 `CandidateAvailabilityConfirmation`，因此不能宣称用户入口已经支持该能力。私有 Gold 也不应在用户确认前把现有 `unknown` 改为 `met`。

## 5. 下一步

1. Agent 的 paths/documents 两个入口透传确认模型。
2. API 增加 `candidate_availability` 对象。
3. CLI 增加 `--candidate-weekly-days` 和 `--candidate-duration-months`。
4. 补入口契约测试后，用真实确认值复跑逐项 Gold，不调整权重。