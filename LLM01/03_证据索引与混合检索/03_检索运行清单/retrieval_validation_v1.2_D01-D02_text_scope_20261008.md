# Step 3 v1.2 RQ1 文本范围检索检查（D01/D02）

- **状态：**同会话 Agent 工程性 smoke check；非独立人工金标准检索评估，也不是 RQ/领域假设的确认性检验。
- **范围：**仅 v1.2 D01/D02 文本查询；D03 方程类型检索不执行；D04-D10定义未变，本次不重跑。
- **索引：**沿用已构建239块混合索引；不改 embedding、BM25、RRF参数，不覆盖旧报告。
- **公式范围：**报告不复制任何检索块原文；仅保留ID、页码、`formula_layout_risk` 和字形风险元数据，避免公式转录；不分析公式。
- **参考 ID：**由当前同会话候选记录抽取，仅作证据发现 smoke check；不是 independent gold set，不把命中率解释为正式 recall/accuracy。
- **研究目标：**研究主线和三项候选方向保持不变。查询是否命中只反映当前 top-k 的证据可发现性；未命中不等同于论文未讨论该维度，Step 4仍需 coverage pass。

- evidence blocks SHA-256: `34bcca1e82bbb9435e060df839cd7bf48ff636e0c7a8b2d37caccd8225c93f57`
- schema v1.2 SHA-256: `5351c9b391c74ccd927e7b323556cb9ddf8972852990723aa8179e26b97daed1`
- prompt SHA-256: `845355613ca3a62d4c0c5675461fb0107e865ad1dbf894ab206fe14a9c6b0164`
- legacy report SHA-256 (unchanged): `76c75c5f5ecc77ddcb961e65762971177a1ee01e3c40e8df80342607f71c1e97`

## Q1-D01-text-direction — D01

- **查询：** How does each paper's own method describe water-to-power effects and power-to-water effects, including water availability or water-system operation affecting power generation or grid operation, and electricity, prices, pumps, desalination or power-system operation affecting water supply? Distinguish one-way from bidirectional textual coupling.
- 当前候选引用 ID 数：5（非金标准）
- 候选 ID 出现在 fused Top-10：['B001-PDF-02-ZA-ABSTRACT-C001']
- 候选 ID 出现在任一路 Top-20：['B001-PDF-02-ZA-ABSTRACT-C001', 'B001-PDF-04-ZA-S01-I-C001', 'B001-PDF-05-ZC-S10-2-4-C001']
- 候选 ID 未进入任一路 Top-20：['B001-PDF-01-ZB-S06-2-2-C001', 'B001-PDF-03-ZB-S03-2-1-C006']
- **Fused Top-10 排名/元数据（不复制原文）：**
  1. `B001-PDF-02-ZA-S03-B-C001` — B001-PDF-02, pages [2]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  2. `B001-PDF-02-ZC-S12-V-C001` — B001-PDF-02, pages [6, 7]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  3. `B001-PDF-01-ZA-ABSTRACT-C001` — B001-PDF-01, pages [1]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  4. `B001-PDF-01-ZB-S05-2-1-C004` — B001-PDF-01, pages [4]; formula_layout_risk=True; contains_unmapped_glyph_marker=False
  5. `B001-PDF-03-ZB-S21-5-2-C001` — B001-PDF-03, pages [19]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  6. `B001-PDF-02-ZA-ABSTRACT-C001` — B001-PDF-02, pages [1]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  7. `B001-PDF-03-ZA-S01-1-C001` — B001-PDF-03, pages [1, 2]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  8. `B001-PDF-02-ZB-S05-A-C001` — B001-PDF-02, pages [3]; formula_layout_risk=True; contains_unmapped_glyph_marker=True
  9. `B001-PDF-04-ZA-S01-I-C002` — B001-PDF-04, pages [3]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  10. `B001-PDF-05-ZC-S15-3-4-C003` — B001-PDF-05, pages [13]; formula_layout_risk=False; contains_unmapped_glyph_marker=False

## Q1-D02-cooling-model-vs-generic-network — D02

- **查询：** Does the paper's own model text explicitly describe in-plant cooling-water demand or process for a power plant, such as cooling-water requirements represented as water-network demands, cooling-water supply or pumping, or plant-specific flow, temperature, constraint, control or performance? Distinguish this from background mentions of power-plant cooling and generic water distribution system pumps, tanks, pipes and water demands.
- 当前候选引用 ID 数：8（非金标准）
- 候选 ID 出现在 fused Top-10：['B001-PDF-01-ZB-S05-2-1-C001', 'B001-PDF-04-ZB-S04-II-C001', 'B001-PDF-04-ZD-S48-B-C001']
- 候选 ID 出现在任一路 Top-20：['B001-PDF-01-ZB-S05-2-1-C001', 'B001-PDF-02-ZA-ABSTRACT-C001', 'B001-PDF-04-ZB-S04-II-C001', 'B001-PDF-04-ZD-S48-B-C001']
- 候选 ID 未进入任一路 Top-20：['B001-PDF-02-ZA-S01-I-C001', 'B001-PDF-03-ZB-S03-2-1-C006', 'B001-PDF-03-ZB-S21-5-2-C001', 'B001-PDF-05-ZD-S17-4-C003']
- **Fused Top-10 排名/元数据（不复制原文）：**
  1. `B001-PDF-04-ZD-S48-B-C001` — B001-PDF-04, pages [13, 14]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  2. `B001-PDF-02-ZB-S04-II-C001` — B001-PDF-02, pages [2, 3]; formula_layout_risk=True; contains_unmapped_glyph_marker=False
  3. `B001-PDF-01-ZB-S05-2-1-C001` — B001-PDF-01, pages [3]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  4. `B001-PDF-04-ZA-S01-I-C001` — B001-PDF-04, pages [3]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  5. `B001-PDF-02-ZB-S05-A-C002` — B001-PDF-02, pages [3]; formula_layout_risk=True; contains_unmapped_glyph_marker=True
  6. `B001-PDF-04-ZB-S04-II-C001` — B001-PDF-04, pages [4]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  7. `B001-PDF-02-ZB-S05-A-C003` — B001-PDF-02, pages [3]; formula_layout_risk=True; contains_unmapped_glyph_marker=True
  8. `B001-PDF-04-ZD-S47-A-C002` — B001-PDF-04, pages [13]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  9. `B001-PDF-04-ZB-S04-II-C003` — B001-PDF-04, pages [4, 5]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  10. `B001-PDF-01-ZB-S05-2-1-C003` — B001-PDF-01, pages [3, 4]; formula_layout_risk=True; contains_unmapped_glyph_marker=False

## Q1-D02-generic-dependency-boundary — D02

- **查询：** In a multilayer infrastructure model, does the text only state that power plants receive water from water-supply facilities and give cooling as an example of the water-to-power dependency, or does it describe a cooling-specific demand, physical process, state, constraint, control target or performance measure? Preserve the distinction between a modeled generic dependency link and an explicitly modeled in-plant cooling process.
- 当前候选引用 ID 数：2（非金标准）
- 候选 ID 出现在 fused Top-10：['B001-PDF-03-ZB-S03-2-1-C006', 'B001-PDF-03-ZB-S21-5-2-C001']
- 候选 ID 出现在任一路 Top-20：['B001-PDF-03-ZB-S03-2-1-C006', 'B001-PDF-03-ZB-S21-5-2-C001']
- 候选 ID 未进入任一路 Top-20：[]
- **Fused Top-10 排名/元数据（不复制原文）：**
  1. `B001-PDF-03-ZB-S21-5-2-C001` — B001-PDF-03, pages [19]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  2. `B001-PDF-03-ZB-S03-2-1-C006` — B001-PDF-03, pages [4]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  3. `B001-PDF-05-ZD-S17-4-C003` — B001-PDF-05, pages [14]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  4. `B001-PDF-04-ZD-S48-B-C001` — B001-PDF-04, pages [13, 14]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  5. `B001-PDF-05-ZD-S17-4-C001` — B001-PDF-05, pages [14]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  6. `B001-PDF-03-ZB-S20-5-1-C001` — B001-PDF-03, pages [18]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  7. `B001-PDF-03-ZA-S01-1-C001` — B001-PDF-03, pages [1, 2]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  8. `B001-PDF-02-ZB-S05-A-C002` — B001-PDF-02, pages [3]; formula_layout_risk=True; contains_unmapped_glyph_marker=True
  9. `B001-PDF-04-ZA-S01-I-C001` — B001-PDF-04, pages [3]; formula_layout_risk=False; contains_unmapped_glyph_marker=False
  10. `B001-PDF-03-ZB-S03-2-1-C002` — B001-PDF-03, pages [3]; formula_layout_risk=False; contains_unmapped_glyph_marker=False

## 解释与限制

1. 结果只回答：当前锁定索引能否把一些与这些自然语言查询相符的块排到 top-k。
2. 当前 candidate reference IDs 来自本会话候选输出，存在循环性；不报告平均 recall，不据此比较模型，不称为检索准确率。
3. 负面标签需回看论文全文文本和方法/案例上下文；top-k 未命中不能作为“未提及/未建模”的证据。
4. 原 `retrieval_validation_report.md` 与 `retrieval_validation_results.json` 保留原样；此报告仅作 v1.2 增补。
