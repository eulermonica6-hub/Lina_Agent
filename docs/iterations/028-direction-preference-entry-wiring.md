# 迭代 028：方向偏好入口接线

> 日期：2026-09-24
> 阶段：Phase 2B.7 方向偏好入口契约
> 状态：Agent、API 和 CLI 接线完成

## 1. 目标

将迭代 027 已验证的 `CandidateDirectionPreferenceConfirmation` 从领域与私有评测层贯通到实际 Agent 入口，让用户能显式提供五类 `0-1` 方向偏好，同时保持自动综合排序 opt-in。

## 2. 实现

- `CareerMatchAgent.execute_paths()`、`execute_documents()` 和内部执行器新增 `candidate_direction_preferences`，并透传到 `extract_decision_signals()`。
- `CareerAgentRequest` 新增同名类型化字段；未启用 `auto_decision_signals` 时返回 422。
- CLI 新增五个 `--direction-*` 参数，支持 Agent/LLM 应用、AI 平台/Infra、通用机器学习、全栈 AI 测试和风险建模。
- API 通过 Pydantic、CLI 通过参数类型函数限制分数为 `0..1`。
- 确认值继续以 `user_confirmation` 返回，且不生成候选人文档 offset。

## 3. 失败与修复

首轮入口测试暴露了三种预期失败：

1. Application 对新关键字参数抛出 `TypeError`，说明入口签名未接线。
2. API 返回 200 但 `candidate_confirmation` 为 `null`。根因是请求模型没有声明该字段，Pydantic 默认忽略未知输入，造成静默丢失。
3. CLI 报未识别参数，说明本地入口尚无表达偏好的方式。

修复后，三层使用同一领域模型和同一 `auto_decision_signals` 开关约束；API/CLI 额外覆盖越界输入。

## 4. 知识与行为准则

- 新领域事实贯通入口时，必须同时验证“接受并生效”和“禁用时拒绝”，不能只验证请求成功。
- API 测试必须断言响应中的业务效果；仅断言 2xx 会漏掉未知字段被静默忽略的问题。
- CLI 参数应映射到领域字段名，范围校验在入口完成，领域模型仍作为最后防线。
- 多入口必须消费同一个类型化模型，避免 API、CLI 和评测产生不同语义。
- 用户确认是补充事实，不改变证据来源规则，也不自动解除实验性功能开关。

## 5. 风险与边界

- 工作台尚未提供方向偏好控件；当前入口是 API 和本地 CLI。
- 五类 taxonomy 仍来自当前小型 Gold，尚未证明跨岗位族泛化。
- 岗位多方向仍使用等权平均，未建模主方向与辅助方向。
- 自动综合排序保持显式 opt-in，不因当前 5 JD 指标达到 1.0 而默认启用。

## 6. 下一步

扩充冻结 Gold，覆盖更多公司、岗位族、单方向与多方向 JD；报告方向 MAE、Pairwise、Top-1 和逆序对稳定性，再决定是否调整 taxonomy、聚合规则或默认开关。

## 7. 面试表达

我没有把已验证的领域模型直接视为产品能力，而是沿 Application、API 和 CLI 逐层建立入口契约。测试发现 API 会把未声明字段静默丢弃并返回 200，因此我把验收标准从“请求成功”提高为“确认来源和最终方向分确实进入响应”，同时固化 opt-in 与范围校验。这样领域事实、外部输入和评测使用同一模型，又不会把 5 条 Gold 上的完美指标误当作泛化结论。
