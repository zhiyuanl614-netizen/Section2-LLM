# Step 5（预备版）：RQ1 v1.2 文本范围描述性统计

- **日期：**2026-10-08
- **状态：**预备性描述统计；不是 Step 5 正式评估，不覆盖 `evaluation_metrics_v1.md/.json`。
- **输入：**`04_LLM抽取与Critic审查/06_v1.2文本范围预分类/B001_RQ1_D01-D03_v1.2_text_only_preclassification.json`（5篇×D01/D02，另有5条D03范围状态）。
- **方法边界：**本文件只汇总同会话 Agent 的文本预分类。没有独立人类金标准，未计算精确率、召回率、标注者一致率或模型效果；比例只描述当前5篇先导语料，不代表总体文献领域。D01–D10中某些标签/维度在本样本未出现是正常样本观察，不改变研究总目标或三项候选 gap/frontier hypotheses；不能据此删除RQ或声称领域中不存在相关方法。

## 1. 当前候选标签分布

### D01：水—电耦合方向（文本证据版）

| 标签 | 篇数 | 文献 |
|---|---:|---|
| `Bidirectional_Coupled` | 4/5（80%） | PDF-01、PDF-02、PDF-03、PDF-04 |
| `Power_to_Water` | 1/5（20%） | PDF-05 |
| `Water_to_Power` | 0/5 | — |
| `Parallel_No_Explicit_Textual_Coupling_Statement` | 0/5 | — |

### D02：厂内冷却水建模（文本证据版）

| 标签 | 篇数 | 文献 |
|---|---:|---|
| `Generic_Water_Network_Only` | 1/5（20%） | PDF-01 |
| `Mentioned_Only_Not_Modeled` | 3/5（60%） | PDF-02、PDF-03、PDF-05 |
| `Both_Present` | 1/5（20%） | PDF-04 |
| `Explicit_InPlant_Cooling_Model_Described`（不同时出现通用水网） | 0/5 | — |

### D03：方程类型

5篇均登记 `Not_Analyzed_Out_Of_Scope`。这是分析范围状态，不进入 D03 标签比例、准确率或任何结论分母；不能解读为论文没有方程。

## 2. PDF-03 D02 边界敏感性

PDF-03 的文字把冷却热电厂作为水—电依赖关系的例子，但未描述冷却专属过程/需求模型。本次按 v1.2 规则暂归 `Mentioned_Only_Not_Modeled`，并列为边界复核项。若独立审查者认为该例应算作 `Generic_Water_Network_Only`，则两类计数变为：

- `Generic_Water_Network_Only`：2/5（40%）
- `Mentioned_Only_Not_Modeled`：2/5（40%）
- `Both_Present`：1/5（20%）

所以 D02 的类别比例对一条边界判定较敏感；当前不要把 60%/20% 写成稳健总体发现。

## 3. 机械溯源检查（不是内容效度）

- 13条被引叙述逐字匹配当前 evidence block：13/13。
- Evidence ID、section 和 PDF物理页号：均与来源记录一致。
- 新候选批次的引文中 `formula_layout_risk=true` 块：0条；D03不含公式细节。
- 这只说明所选引文可回溯、文本逐字准确；不证明标签内容效度，不替代专家判断。

## 4. 原始 PDF 定向复核增补（2026-10-08）

同会话 Arena.ai Agent 直接核对了 PDF-01/02/03 的可检索原文、相关方法/案例段落及指定图页。PDF-01/02的候选标签没有改变；PDF-03的冷却示例及“电厂由供水设施供水”的通用节点—边依赖都得到更精确记录。按当前冷却专属过程阈值，PDF-03仍暂列 `Mentioned_Only_Not_Modeled`，但需领域专家裁定该模型抽象是否足以算作 D02 建模。详见 `04_LLM抽取与Critic审查/06_v1.2文本范围预分类/D02_v1.2_original_pdf_targeted_review_same_session_2026-10-08.md`。此来源复核不改变当前描述频数、不构成独立人类复核，也不允许将 D02 样本比例推广到领域总体。

同时新增 Step 3 的 v1.2 D01/D02文本范围检索 smoke check，引用的是同会话候选证据而非独立金标准；它属于检索工程检查，不是 Step 5 模型性能或准确度指标，报告位于 `03_证据索引与混合检索/03_检索运行清单/retrieval_validation_v1.2_D01-D02_text_scope_20261008.md`。

## 5. 正式 Step 5 前置条件

1. 已完成 PDF-01/02/03 的同会话原始 PDF 文字层及相关方法/案例页定向复核；PDF-01/02当前标签获来源核对支持。PDF-03 D02 的事实已核验，但“通用供水依赖是否达到厂内冷却模型阈值”仍须用户/领域专家独立裁定；同会话复核不等于独立终审。
2. 继续完成当前239版的文本与 Zone 人工抽样 QA；如发现相关段落缺失或错分，先修正证据集并按变更控制重新处理。
3. 用最终确定的 v1.2 记录生成正式、版本化的 Step 4 数据；对 D01/D02 报告审查者与执行渠道。没有独立 gold set 时，不报告准确率/一致率。
4. 在上述条件满足前，不据此重写 Step 6/Step 7 结果，不将此描述统计与旧 v1.0 指标直接拼接。
