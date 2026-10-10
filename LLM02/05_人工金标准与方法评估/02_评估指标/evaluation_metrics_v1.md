# Step 5 — 评估指标 v1.0

**计算日期：** 2026-10-06　**样本：** 5篇文献 × 10维 = 50条 `05_核验通过结果/*_verified_10d.json` 记录
**原始计算结果：** `evaluation_metrics_v1.json`（本文件同目录）
**前置声明：** 本页所有指标均为**流程内部一致性/可回溯性**的程序化与半程序化度量，不是与独立人工金标准比较得出的准确率。详见 `../01_人工金标准审核/agent_assisted_audit_v1.md` 第0节强制披露。

---

## 1. 指标定义（按 README P0-4 要求，计算前冻结口径）

| 指标 | 定义 | 分子 | 分母 |
|---|---|---|---|
| **证据豁免率** `exempt_rate` | 主标签落在"无需证据"受控词表（`Not_Addressed`、`None_Reported`，或 `fallback_states`：`Not_Stated_In_Text`/`Explicitly_Not_Considered`/`Insufficient_Evidence`/`Evidence_Unavailable`）的记录比例 | 豁免记录数 | 全部记录数（50） |
| **证据充分率** `evidence_sufficiency_rate` | 在"非豁免"记录中，同时具备非空 `evidence_ids` 列表与非空 `verbatim_quote` 字段的比例 | 同时具备两者的非豁免记录数 | 非豁免记录数 |
| **引用精确匹配率** `quote_exact_match_rate` | 非豁免记录的 `verbatim_quote`，经空白归一化（collapse whitespace、大小写不敏感）后，是否为其 `evidence_ids` 对应原文 `text` 字段的**精确子串** | 匹配通过记录数 | 非豁免记录数 |
| **章节/页码可回溯率** `section_page_traceability_rate` | 非豁免记录同时具备非空 `section_id` 与 `page_numbers` 字段的比例 | 具备两字段的记录数 | 非豁免记录数 |
| **Agent A/B 初次一致率** `pass1_pass2_initial_agreement_rate` | pass2 中 Agent B 决策为 `accept`（未要求任何修订）的记录比例 | accept 记录数 | 全部记录数（50） |
| **修订率** `pass2_revision_rate` | pass2 中 Agent B 决策为 `revise` 的记录比例 | revise 记录数 | 全部记录数（50） |
| **主标签级修正率** `primary_label_correction_rate` | 修订记录中，修订后 `primary_label` 与 pass1 原值不同的比例（相对全体50条） | 主标签变更的修订记录数 | 全部记录数（50） |
| **证据/次要标签级修正率** `evidence_only_correction_rate` | 修订记录中，`primary_label` 未变但证据引用或次要标签被修正的比例（相对全体50条） | 此类修订记录数 | 全部记录数（50） |
| **未决分歧率** `unresolved_adjudication_count/rate` | pass4 终审后仍标记为非 `accept`（即需要人工仲裁 `adjudication_required`）的记录数 | — | 全部记录数（50） |
| **无支撑断言率** `unsupported_claim_rate` | 非豁免记录中，`evidence_ids`/`verbatim_quote` 缺失，或引用精确匹配失败的记录比例 | 不满足证据充分率或引用精确匹配率的记录数 | 非豁免记录数 |

**说明：** 一篇文献的10个维度记录彼此不是独立观测（同篇论文内维度间可能相关）；以下指标按"记录"为单位汇总，同时在第3节按文献分层报告，避免总体均值掩盖文献间差异（README P0-4 要求）。

---

## 2. 总体结果

| 指标 | 结果 |
|---|---|
| 总记录数 | 50（5篇 × 10维） |
| 证据豁免记录数 / 豁免率 | 12 / **24.0%** |
| 非豁免记录数 | 38 |
| 证据充分率 | 38/38 = **100%** |
| 引用精确匹配率 | 38/38 = **100%** |
| 章节/页码可回溯率 | 38/38 = **100%** |
| Agent A/B 初次一致率（pass1→pass2 无条件 accept） | 46/50 = **92%** |
| 修订率（pass2 revise） | 4/50 = **8%** |
| 其中：主标签级修正 | 2/50 = **4%**（PDF-03 D02、PDF-05 D05） |
| 其中：证据/次要标签级修正（标签未变） | 2/50 = **4%**（PDF-01 D10、PDF-04 D07） |
| pass4 终审后未决分歧（`adjudication_required`） | 0/50 = **0%** |
| 无支撑断言率 | 0/38 = **0%** |
| `own_method_vs_cited` 分布 | `Paper_Own_Method`: 50/50；`Cited_Other_Work`: 0；`Mixed`: 0（见审核文档§3异常讨论） |

**解读边界：** 100%的证据充分率/引用匹配率/可回溯率是**程序化规则检查**的结果（代码可重复验证，见本文件末尾复现命令），度量的是"记录是否符合 schema 规定的可回溯性要求"，**不是**"标签本身是否正确"这一语义判断——后者仍只能由 Agent B critic 的 92%/8% 一致率间接体现，且该体现本身受限于双 Agent 共享执行渠道（见 `01_人工金标准审核/` 第0节）。

---

## 3. 按文献分层结果

| 文献 | 非豁免记录数 | 证据充分率 | 引用匹配率 | pass2 accept | pass2 revise |
|---|---|---|---|---|---|
| B001-PDF-01 | 8 | 100% | 100% | 9/10 | 1/10 |
| B001-PDF-02 | 8 | 100% | 100% | 10/10 | 0/10 |
| B001-PDF-03 | 7 | 100% | 100% | 9/10 | 1/10 |
| B001-PDF-04 | 8 | 100% | 100% | 9/10 | 1/10 |
| B001-PDF-05 | 7 | 100% | 100% | 9/10 | 1/10 |

---

## 4. 按维度分层结果（含 Pilot Gate 重点难点维度 D02/D04/D05/D06/D08）

| 维度 | 豁免记录数/5 | 标签分布（primary_label，跨5篇） |
|---|---|---|
| D01（耦合方向） | 0/5 | `Bidirectional_Coupled`×4，`Power_to_Water`×1 |
| D02（厂内冷却识别，难点） | 0/5 | `Generic_Water_Network_Only`×2，`Mentioned_Only_Not_Modeled`×2，`Both_Present`×1 |
| D03（核心方程类型） | 0/5 | 多样，含1例受控词表缺口（PDF-03，见错误分析） |
| D04（信息层快感知，难点） | 5/5 | 全部 `Not_Addressed`（与 Step 3 检索验证报告"语料本身稀疏"的预判一致） |
| D05（时间尺度建模，难点） | 1/5 | `Explicit_MultiTimescale_Model`×1，`Single_Timescale_Only`×2，`Qualitative_Mention_No_Formal_Model`×1，`Not_Addressed`×1 |
| D06（主动/被动控制，难点） | 1/5 | `Proactive_Anticipatory_Control`×3，`Not_Addressed`×1，`Reactive_Control_Only`×1 |
| D07（级联后果类型） | 2/5 | `Not_Stated_In_Text`×2，`Physical_Network_Service_Loss_Only`×1，`Critical_Facility_Impact`×2 |
| D08（人类/社会影响，难点） | 3/5 | `None_Reported`×3，`Critical_Facility_Service_Disruption`×1，`Named_Case_Region_Impact`×1 |
| D09（测试系统真实性） | 0/5 | 多样，覆盖 synthetic/hybrid/real-world 全谱 |
| D10（局限/未来方向） | 0/5 | 全部明确表述，含多标签组合 |

**观察：** D02/D05/D06/D08 四个 Pilot Gate 标记的难点维度**均出现了非平凡的标签分布**（不是全部坍缩到同一标签），且D02（PDF-03）、D05（PDF-05）恰好是本批次仅有的2例主标签级修正的发生维度——这与"这些维度判别边界模糊、更依赖 Critic 纠错"的预期相符，不是巧合。D04 是唯一5/5同质的维度，但这是语料内容本身的性质（见上），不是标注失败的信号。

---

## 5. 未覆盖/无法计算的指标（诚实披露）

- **检索召回/覆盖率指标**（`evidence recall@k`、`section coverage` 等）：Step 4 执行时对5篇文献采用的是"全文证据块逐一审阅"（coverage pass 的手工等价形式），而非真正按 `03_检索运行清单/` 中锁定的 dense+BM25 混合检索流程逐维度调用；因此本次无法计算"检索到的证据 vs 全文应有证据"的召回率差异，这是 Step 4 执行方式（Arena Agent 同会话直接推理）相对于原设计 M2→M3 流程的已知简化，已在 `agent_prompts_and_manifest_v1_LOCKED.md` 中披露。
- **成本/延迟指标**（token、调用延迟、重试率）：`model_call_manifest.jsonl` 中 `input_token_estimate`/`output_token_estimate` 为估算值，`temperature`/`model_version` 记录为 `not_exposed_by_execution_channel`；由于不是独立计费的外部 API 调用，传统意义上的"单篇成本"、"单篇延迟"指标不适用，不予虚构。
- **Agent A/B 一致率的 Cohen's κ / Krippendorff's α**：由于本流程只有一次 Agent A 初标 + 一次 Agent B 复核（非两名独立标注者各自标注全部50条后比较），当前"92%一致率"是协议内的 accept/revise 比例，不是机会校正的标注者间一致性系数。若未来引入真正独立的第二位标注者（人工或独立模型），应按 README P0-6 补充报告 κ/α。

---

## 6. 复现方法

所有数值均可通过重新运行本会话中对 `05_核验通过结果/*.json`、`04_AgentB_Critic审查/*_agentB_pass2.json`、`03_AgentA原始抽取/*_agentA_pass1.json` 的 Python 脚本重新计算；脚本逻辑已记录在本轮会话历史中，核心步骤为：(1) 从 `schema_v2.json` 读取 `fallback_states` 构建豁免标签集合；(2) 遍历50条 verified 记录计算证据/引用/回溯三项指标；(3) 遍历5个 `agentB_pass2.json` 按 `decision` 字段计数；(4) 对比 pass1 与 pass2 的 `corrected_label` 区分主标签修正与证据级修正。建议后续将该脚本固化为 `step5_compute_metrics.py` 并入版本库（本轮暂未单独建脚本文件，计算过程记录于会话日志）。
