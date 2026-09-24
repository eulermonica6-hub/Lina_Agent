# 迭代 032：确定性技能证据计划

> 日期：2026-09-24
> 阶段：Phase 2B.11 从排序逆序到能力证据
> 状态：NVIDIA 目标岗位计划已生成并通过 Reviewer

## 1. 问题

扩展 Gold 的唯一逆序是用户偏好 NVIDIA AI Computing 高于 MiniMax 模型评测，但自动排序相反。hard 与 direction 均已准确，差异来自 NVIDIA required 技能证据缺口：PyTorch、C++、CUDA。继续调权重会掩盖真实能力差异，不能帮助候选人提高可投递性。

## 2. 实现

- 将 CUDA 加入技能 taxonomy，使岗位缺口可被领域模型和 Gold 直接观察。
- 新增 `build_skill_evidence_plan()`，从目标 `RankedJobMatch.missing_required` 生成最多 3 个确定性行动。
- 复用现有 `CareerActionPlan` / `CareerPlanAction`：每项包含目标技能、行动、原因、产出物、验收标准和时间预算。
- 新增 `build_dataset_skill_evidence_plan()` 与评测 CLI `--evidence-plan-for <catalog_number>`，从冻结数据集重建目标岗位并输出计划 JSON。
- 计划 provider 为 `deterministic`、model 为 `skill-evidence-v1`、token 数为 `0`。
- 现有 Reviewer 验证目标技能均来自岗位 gap，拒绝无证据技能。

## 3. NVIDIA 计划

| 优先级 | 技能 | 产出物 | 验收 | 时间 |
| --- | --- | --- | --- | ---: |
| 1 | PyTorch | 可复现 LLM 推理仓库与性能报告 | 测试通过，记录吞吐、延迟、显存与优化前后对比 | 16h |
| 2 | C++ | 带 Python 绑定、测试和构建脚本的扩展 | 一条命令构建测试，与 PyTorch 参考实现误差在阈值内 | 20h |
| 3 | CUDA | Kernel、正确性测试和实验记录 | 与参考实现一致，并用基准解释性能与瓶颈 | 24h |

总预算为 `60h`。这三项能够形成仓库、测试、benchmark 和面试复盘材料，而不是只有课程完成记录。

## 4. 验证结果

- 确定性计划目标顺序：PyTorch > C++ > CUDA；
- Reviewer 状态：`verified`；
- CUDA 进入技能 taxonomy 后，NVIDIA skill score 从 `40.0` 调整为更真实的 `33.3`；
- 扩展集 Pairwise 保持 `0.933`，唯一逆序不变；
- suite 为 2 集 11 岗，macro/minimum Pairwise 为 `0.967/0.933`；
- 两个私有技能 Gold 的 Precision、Recall、Exact Match 和引用支持率均为 `1.0`。

## 5. 失败与修复

1. 首次将数据集计划函数插入 suite 函数中部，使 suite 隐式返回 `None`。修复为移动到完整函数 return 之后，并重跑整个评测文件。
2. 为 CUDA 更新私有 Gold 时，模糊补丁锚点误写了重复 JSON 结构。通过逐文件 JSON 解析与逐岗预测/Gold 差集定位，恢复岗位 1 并将 CUDA 放到正确岗位。
3. Apple 优先条件标题没有进入单条 evidence，导致 preferred 被预测为 required。匿名 JD 在每个子句保留“优先”语气，并将 Data Analysis 调整到 preferred，两个技能 Gold 恢复全 1.0。

## 6. 知识与行为准则

- 排序逆序若由真实 required 技能缺口解释，应生成证据计划，而不是调权重。
- 学习任务必须以可运行产出和测量结果验收，课程或阅读本身不算技能证据。
- 确定性计划只引用候选人已有技能或岗位 gap，并继续经过 Reviewer。
- 新技能进入 taxonomy 后必须复跑全部冻结技能 Gold，不能只看自动排序报告。
- 修改重复 JSON 结构时必须使用 catalog 上下文，并在编辑后立即独立解析每个文件。
- 长函数插入新函数必须以最终 return 为边界；同类失败出现第二次后升级为明确工程规则。

## 7. 使用方式

```bash
uv run --locked python -m lina_agent.evaluation.career_matching \
  data/private/evaluation/career_matching_gold_v3.json \
  --evidence-plan-for 6
```

## 8. 下一步

执行 PyTorch 推理基线：建立独立可复现项目，冻结模型与输入，采集吞吐、延迟和显存基线；完成后再进入 C++ 扩展与 CUDA Kernel，不并行摊薄证据质量。

## 9. 面试表达

当方向和硬条件都准确后，唯一排序逆序仍存在。我证明它来自 NVIDIA required 的 PyTorch、C++、CUDA 缺口，而不是评分权重，于是将逆序转化为 60 小时确定性证据计划。计划复用现有 Schema 和 Reviewer，每项都要求仓库、测试与 benchmark；同时把 CUDA 加入 taxonomy 并复跑所有技能 Gold，避免计划建立在不可观测的标签上。
