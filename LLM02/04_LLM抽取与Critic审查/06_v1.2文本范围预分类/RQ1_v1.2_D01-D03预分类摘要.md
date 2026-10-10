# RQ1 v1.2 文本范围预分类摘要（5篇）

- **状态：**Agent辅助预分类，非正式 Step 4 最终通过记录；不覆盖任何 v1.0/v1.1 产物。
- **范围：**研究总目标、RQ层级和三项候选 gap/frontier 方向保持不变；本版本只对齐证据操作化。D01/D02只据清晰自然语言；D03一律登记为公式子维度范围外，不作论文发现或方程存在/类型结论。5篇先导样本中某个 D01–D10 标签未出现属于正常样本结果，不能据此删RQ或推断领域中没有该现象。
- **来源：**当前239版 `evidence_blocks.jsonl`（SHA-256 `34bcca1e82bbb9435e060df839cd7bf48ff636e0c7a8b2d37caccd8225c93f57`）。结构化记录及逐条引文见同目录 `B001_RQ1_D01-D03_v1.2_text_only_preclassification.json`。
- **执行披露：**同会话 Arena.ai Agent 辅助判读、原 PDF 定向复核与自我核对；不是独立人类领域专家终审，也不是隔离的 Agent A/B 复核。PDF-01/02/03的 D02 原文复核与边界说明见 `D02_v1.2_original_pdf_targeted_review_same_session_2026-10-08.md`。

| 文献 | D01 耦合方向（文本版） | D02 厂内冷却水（文本版） | D03 方程类型 | 与正式 v1.0 的主要变化 |
|---|---|---|---|---|
| PDF-01 | `Bidirectional_Coupled` | `Generic_Water_Network_Only` | `Not_Analyzed_Out_Of_Scope` | D01/D02主标签未变；D03不再作方程类型分析。 |
| PDF-02 | `Bidirectional_Coupled` | `Mentioned_Only_Not_Modeled` | `Not_Analyzed_Out_Of_Scope` | D01/D02主标签未变；D03不再作方程类型分析。 |
| PDF-03 | `Bidirectional_Coupled` | `Mentioned_Only_Not_Modeled` | `Not_Analyzed_Out_Of_Scope` | **D02从 `Generic_Water_Network_Only` 改为 `Mentioned_Only_Not_Modeled`**：v1.2区分“完全没有冷却文字”与“仅作为示例提到冷却、但无冷却专属模型叙述”。不否认其文本所述的通用水—电依赖关系。 |
| PDF-04 | `Bidirectional_Coupled` | `Both_Present` | `Not_Analyzed_Out_Of_Scope` | D01/D02主标签未变；文本pilot显示风险块中的清晰叙述可用，但本批引用本身未使用风险标记块。 |
| PDF-05 | `Power_to_Water` | `Mentioned_Only_Not_Modeled` | `Not_Analyzed_Out_Of_Scope` | D01/D02主标签未变；D03不再作方程类型分析。 |

## 机械核验结果

- 结构化记录共15条：D01 5条、D02 5条、D03范围状态5条。
- 13条支持引文均逐字匹配当前 evidence block；证据 ID、章节与 PDF 物理页码均一致。
- 所引用块中 `formula_layout_risk=true` 的块为0；未产生任何 `equation_detail`。
- D03的5条均无 evidence ID/quote/equation detail，明确标为 `Not_Analyzed_Out_Of_Scope`；不作为论文标签、发现或评估分母。
- 上述为来源/结构/范围核验，不等同于领域专家人工内容效度审核；需要在冻结前继续做独立人工抽查及下游复算。

## 重要边界

此摘要只记录基于现有可读文本的 v1.2 候选标签。PDF-03的 D02 是边界案例：文本把“供水到电力设施（例如冷却热电厂）”作为依赖关系示例，但未描述冷却专属的水量需求、热力过程、控制对象或性能指标。因此按 v1.2暂归“仅提及、未描述冷却专属建模”，并在正式终审时优先复核。不得把此标签扩展为“论文完全没有冷却相关内容”。
