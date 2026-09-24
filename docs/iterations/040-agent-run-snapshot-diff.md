# 迭代 040：Agent Run Snapshot Diff

> 日期：2026-09-24
> 阶段：Phase 3A.4 历史比较
> 状态：两个 Run 可在不加载正文时生成结构化差异

## 1. 目标

基于 Snapshot、DocumentReference 和 CandidateConfirmationVersion 比较两个 Agent Run，回答“输入、确认、排序、分数、gap 和计划发生了什么变化”，同时不读取原始文档或返回敏感文本。

## 2. Diff 契约

新增 `AgentRunDiff`：

- base / target run ID；
- candidate document、job catalog、confirmation 是否变化；
- run state 与 plan 是否变化；
- base / target 排名；
- 新增、移除和同编号替换岗位；
- 共同岗位的排名位置变化；
- score / skill score delta；
- hard / direction 分量是否变化；
- 新增与已解决 gap。

`position_delta = target_position - base_position`：负数表示排名上升，正数表示下降。

## 3. 输入身份比较

- v2 Snapshot 优先加载 DocumentReference content hash 与 ConfirmationVersion facts hash；
- v1 Snapshot 或缺失引用时回退稳定 document UUID 与 request 内嵌确认事实；
- 不读取 DocumentBlock、evidence text 或文件正文；
- plan 只比较规范化内容，忽略 provider、model 和 token usage 元数据。

## 4. 岗位身份规则

Catalog number 只在同一目录内稳定。两个 Run 中编号相同但 title/company 不同时，标记为 `replaced_catalog_numbers`，不计算 score delta 或位置变化，避免把不同岗位伪装成同一实体。

## 5. API

```text
GET /agent/runs/{base_run_id}/diff/{target_run_id}
```

任一 Run 不存在时返回 404。响应只包含结构化差异，不包含原文、offset、文件名、DocumentReference metadata 或确认事实正文。

## 6. 验证

- 相同简历/JD、不同确认版本：只报告 confirmation changed；
- 不同 JD content hash：报告 job catalog changed；
- 排名互换：报告 base/target position 和 delta；
- 分数变化：报告 score/skill delta 与 hard/direction change flags；
- gap 新增/解决正确；
- v1 Snapshot 可 fallback 比较；
- 同编号 title/company 变化标记 replacement，不计算伪 score delta；
- plan 从无到有标记 changed；
- API 响应不含 sentinel 原文；
- 未知 Run 返回 404。

## 7. 知识与行为准则

- 历史 diff 必须以版本 hash 和脱敏 Snapshot 为输入，不为比较加载敏感正文。
- 排名位置 delta 必须公开方向定义，避免“+1”含义歧义。
- 业务局部编号不能跨版本直接视为实体 ID，必须校验 title/company 或稳定岗位 ID。
- 分数变化和岗位替换是不同事件，不能混在一个 delta 中。
- 计划比较应忽略 provider/token 等执行元数据，关注行动内容变化。
- 旧 Snapshot 可读是 schema 演进底线；fallback 精度不足时应明确，而不是迁移时丢弃历史。

## 8. 当前边界

Diff 能解释结构化历史变化，但不展示原文证据 diff，也不恢复节点执行。岗位 title/company 仍是派生数据，会出现在 Snapshot 和 Diff 的岗位身份判断中。

## 9. 下一步

在工作台增加只读 Run 历史与 Diff 视图：运行列表、输入/确认变化、排名位移、分数分量、gap 和计划状态；不展示未授权原文。

## 10. 面试表达

我在持久化历史后没有直接对完整 JSON 做通用 diff，而是定义业务差异契约。文档用 content hash、确认用 facts hash，岗位先验证编号对应的 title/company，再计算排名与分数 delta。整个 API 不加载正文，并兼容旧 Snapshot，从而在隐私和 schema 演进约束下提供可解释历史比较。
