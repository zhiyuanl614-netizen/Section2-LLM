# Step 5 v1.2 先导语料描述性统计（预备版）

- **状态：**版本化预备计数；不是正式 Step 5 模型性能评估，不覆盖 v1.0/v1.1 文件。
- **总目标：**保持不变——文献学习提出三项候选研究差距/前沿方向，形成 RQ/假设，再由 LLM 基于证据检验支持、反例和不确定性。
- **样本：**5篇先导 PDF；D01–D10某些标签在此样本为零属于正常观察，不推断领域总体缺失，也不因此删除任何候选方向。
- **结果来源：**D01/D02/D03为v1.2同会话Agent文本候选；D04–D10沿用原v1.0记录（定义未变），没有在本版重审。PDF-03 D02仍待领域 adjudication。
- **不能声称：**无独立人类金标准，未计算准确率、精确率、召回率、F1、Cohen's κ、Krippendorff's α或模型效果。
- **公式范围：**不报告公式转录、推导或方程类型；D03只记范围状态，不进入发现/分布。

- 输入 ledger SHA-256: `788745f504b656ea7b48b1e34504885a1b0d669562e93756244d04e30e73ab14`

## 1. 主标签描述频数

| 维度 | 版本/状态 | 5篇先导语料中的 primary-label 频数 |
|---|---|---|
| D01 | v1.2文本候选 | `Bidirectional_Coupled` 4/5; `Power_to_Water` 1/5 |
| D02 | v1.2文本候选 | `Both_Present` 1/5; `Generic_Water_Network_Only` 1/5; `Mentioned_Only_Not_Modeled` 3/5 |
| D03 | v1.2范围状态，不作研究发现 | `Not_Analyzed_Out_Of_Scope` 5/5 |
| D04 | v1.0沿用，定义未变 | `Not_Addressed` 5/5 |
| D05 | v1.0沿用，定义未变 | `Explicit_MultiTimescale_Model` 1/5; `Not_Addressed` 1/5; `Qualitative_Mention_No_Formal_Model` 1/5; `Single_Timescale_Only` 2/5 |
| D06 | v1.0沿用，定义未变 | `Not_Addressed` 1/5; `Proactive_Anticipatory_Control` 3/5; `Reactive_Control_Only` 1/5 |
| D07 | v1.0沿用，定义未变 | `Critical_Facility_Impact` 2/5; `Not_Stated_In_Text` 2/5; `Physical_Network_Service_Loss_Only` 1/5 |
| D08 | v1.0沿用，定义未变 | `Critical_Facility_Service_Disruption` 1/5; `Named_Case_Region_Impact` 1/5; `None_Reported` 3/5 |
| D09 | v1.0沿用，定义未变 | `Hybrid_Synthetic_Calibrated_To_Real_Data` 1/5; `Real_World_Named_Region` 1/5; `Synthetic_Test_System_Only` 3/5 |
| D10 | v1.0沿用，定义未变 | `Future_Work_Direction` 1/5; `Missing_Factor_Limitation` 2/5; `Model_Simplification_Limitation` 1/5; `Validation_Generalizability_Limitation` 1/5 |

### D01/D02 当前候选标签分布

- D01：{'Bidirectional_Coupled': 4, 'Power_to_Water': 1}
- D02：{'Generic_Water_Network_Only': 1, 'Mentioned_Only_Not_Modeled': 3, 'Both_Present': 1}
- D03：5/5 `Not_Analyzed_Out_Of_Scope`；不计为“无方程”或缺失发现。

## 2. PDF-03 D02 敏感性

按当前冷却专属过程阈值，PDF-03暂列 `Mentioned_Only_Not_Modeled`，但原文中的通用“供水设施为电厂供水”依赖确实进入模型。若专家裁定该项应改列 `Generic_Water_Network_Only`，D02频数将变为：

| 假设 | `Generic_Water_Network_Only` | `Mentioned_Only_Not_Modeled` | `Both_Present` |
|---|---:|---:|---:|
| 当前暂行判定 | 1/5 | 3/5 | 1/5 |
| PDF-03改列通用水网（敏感性） | 2/5 | 2/5 | 1/5 |

敏感性只示范这一种备选标签，不代表专家已裁定；PDF-03的通用依赖模型与冷却专属过程模型必须分别表述。原文复核见 `04_LLM抽取与Critic审查/06_v1.2文本范围预分类/D02_v1.2_original_pdf_targeted_review_same_session_2026-10-08.md`。

## 3. 方法限制与后续门槛

1. 本表是5篇文献上的描述性频数；没有独立金标准，不能度量LLM性能或审核者一致性。
2. D04–D10只是因定义未变而沿用旧记录；D03方程类型信息完全不带入新指标。
3. PDF-03 D02须由用户/领域专家确认构念阈值后，才能生成定稿Step 4及正式Step 5–7。
4. Step 6/7应把三项 gap/frontier 作为可被样本证据支持、反驳或保留不确定性的假设；不能用零频标签把研究目标改写为领域总体结论。
