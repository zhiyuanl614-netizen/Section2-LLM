# Step 5 v1.2.1 先导语料描述性统计（预备版）

- **状态：**provisional_descriptive_counts_not_formal_model_evaluation；无模型性能或人工标注者一致性结论。
- **语料：**5 篇；当前数字只描述输入 ledger，不外推至领域总体。
- **ledger 状态：**`preliminary_compilation_not_final_step4_and_not_independent_human_expert_validation`；ledger SHA-256：`788745f504b656ea7b48b1e34504885a1b0d669562e93756244d04e30e73ab14`
- **公式范围：**D03 只作范围状态 metadata，不进入主标签频数；不报告方程类型、公式转录或推导。
- **D02 PDF-03：**边界仍未决；当前 ledger 标签不是用户批准的裁定。备选标签只作敏感性情景。

## 主标签描述频数（仅9个 active analytic dimensions）

| 维度 | 先导样本主标签频数 |
|---|---|
| D01 | `Bidirectional_Coupled` 4/5; `Power_to_Water` 1/5 |
| D02 | `Both_Present` 1/5; `Generic_Water_Network_Only` 1/5; `Mentioned_Only_Not_Modeled` 3/5 |
| D04 | `Not_Addressed` 5/5 |
| D05 | `Explicit_MultiTimescale_Model` 1/5; `Not_Addressed` 1/5; `Qualitative_Mention_No_Formal_Model` 1/5; `Single_Timescale_Only` 2/5 |
| D06 | `Not_Addressed` 1/5; `Proactive_Anticipatory_Control` 3/5; `Reactive_Control_Only` 1/5 |
| D07 | `Critical_Facility_Impact` 2/5; `Not_Stated_In_Text` 2/5; `Physical_Network_Service_Loss_Only` 1/5 |
| D08 | `Critical_Facility_Service_Disruption` 1/5; `Named_Case_Region_Impact` 1/5; `None_Reported` 3/5 |
| D09 | `Hybrid_Synthetic_Calibrated_To_Real_Data` 1/5; `Real_World_Named_Region` 1/5; `Synthetic_Test_System_Only` 3/5 |
| D10 | `Future_Work_Direction` 1/5; `Missing_Factor_Limitation` 2/5; `Model_Simplification_Limitation` 1/5; `Validation_Generalizability_Limitation` 1/5 |

## 单独的范围状态 metadata（不计入主标签频数）

- D03：{'Not_Analyzed_Out_Of_Scope': 5}。该记录只说明此版本未做方程类型分析，不表示论文没有方程。

## PDF-03/D02 敏感性（非裁定）

- 当前输入标签频数：{'Generic_Water_Network_Only': 1, 'Mentioned_Only_Not_Modeled': 3, 'Both_Present': 1}
- 假设 PDF-03 改列 `Generic_Water_Network_Only` 的情景：{'Generic_Water_Network_Only': 2, 'Mentioned_Only_Not_Modeled': 2, 'Both_Present': 1}
- 该情景不是用户或领域专家裁定；两种边界解释均保留为未决。

## 未计算的指标

未计算 accuracy、precision、recall、F1、Cohen's κ、Krippendorff's α 或 model effectiveness，因为没有独立人工金标准/独立审核输出。

## 版本化输出

- JSON：`evaluation_metrics_v1.2.1_scope_aligned_provisional_static-pilot-ledger-20261010.json`
- Markdown：`evaluation_metrics_v1.2.1_scope_aligned_provisional_static-pilot-ledger-20261010.md`
