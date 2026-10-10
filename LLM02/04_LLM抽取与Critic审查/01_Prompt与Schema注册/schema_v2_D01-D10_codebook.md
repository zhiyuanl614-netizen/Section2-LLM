# D01–D10 操作性定义与标注手册（schema_v2，当前版本 v1.1 — D03/D05/D06 已修订；v1.0 部分条款保持冻结）

**冻结日期（v1.0）：** 2026-10-06
**修订日期（v1.1）：** 2026-10-06（同日修订，Step 7后基于Step 5/6发现的缺陷立即修复，未跨批次延迟）
**适用范围：** 当前 5 篇探索性/先导语料（Route A，非30篇确认性比较）；若未来扩展到30篇，需重新审视本手册是否需要修订版本号。
**冻结后变更规则：** 本手册冻结后，若在 Step 4 执行中发现定义缺陷，必须新开版本号（v1.1、v2.0…），记录变更日志和变更理由，不得静默修改 v1.0 并重跑已完成记录；所有已产出记录须标注其所用 schema 版本号。

## 变更日志

### v1.1（2026-10-06）—— 修复2处Step 5/6发现的真实缺陷，不涉及其他维度

**触发来源：** `05_人工金标准与方法评估/03_错误分析/error_analysis_v1.md` §2.1、§2.2 和 `06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.md` 簇B讨论中记录的2类问题。

1. **D03 新增受控标签 `Topological_Dependency_Equation`。**
   **缺陷描述：** B001-PDF-03 的 Eqs.(1)-(5) 是真实存在的、显式编号的图论/网络拓扑二元依赖状态方程（node-node、node-edge、node-path、geographical dependence），但 v1.0 的6个D03标签均未覆盖"拓扑依赖方程"这一数学性质类别，导致该论文被迫退回 `No_Explicit_Equation_Qualitative_Only`（置信度被迫降至0.5并标记flagged），而该标签本意是描述"完全没有方程、仅定性描述"的情形，与PDF-03的实际情况（有方程，只是方程的数学性质不在原有6类之内）不符。
   **修复方案：** 新增第7个受控标签 `Topological_Dependency_Equation`，定义和判别规则见下文D03章节更新。
   **对已有记录的影响：** **不回溯修改**任何已核验记录。B001-PDF-03 的 D03 记录在 `05_核验通过结果/B001-PDF-03_verified_10d.json` 中保持 v1.0 下产出的 `No_Explicit_Equation_Qualitative_Only` 标签及其flagged状态不变（该记录对应的 `model_call_manifest` 条目的 `schema_version` 字段已如实记录为 `v1.0`，可追溯）。若需要按v1.1重新分类该记录，须作为一次新的、独立留痕的分类动作执行（见本文件同目录下 `B001-PDF-03_D03_v1.1_reclassification_demo.json` 的演示性重分类，仅作方法验证用途，不替换v1.0正式核验结果）。

2. **D05、D06 补充"关键词陷阱/反例"说明。**
   **缺陷描述：** 本语料中出现过2次常见工程术语被误认为匹配受控构念的情形：
   - B001-PDF-05 的 D05：论文的"steady-state"措辞被 Agent A 初次误判为 `Single_Timescale_Only`（即"论文考虑过多时间尺度但只用了单一尺度"），但该"稳态"实际指地震前/后两个静态快照的比较，与D05构念（水-热-水力相对电力的慢动态时间尺度表征）无关；此案例由 Agent B 在 pass2 纠正为 `Not_Addressed`。
   - B001-PDF-03 的 D06：论文的"proactive absorptive capacity"表面上与D06构念高度相似，但实际是 MCEER 韧性工程框架中"基础设施规划设计阶段的结构韧性属性"，与D06要求的"利用信息层快感知与物理慢动态时间尺度差进行实时主动控制"是两回事；此案例在 Agent A 的 pass1 阶段即被正确识别为 `Not_Addressed`，未经修订。
   **关键观察：** 同一类陷阱一次被规避、一次未被规避，说明仅靠 Agent 自身的语境判断并不稳定，需要在编码手册层面提供显式反例，降低对单次推理质量的依赖。
   **修复方案：** 在D05、D06章节各增加"关键词陷阱/反例"小节，不新增/修改受控标签本身，只增加判别指引。
   **对已有记录的影响：** 不回溯修改任何已核验记录；本语料5篇文献的D05/D06已在Step4-5的完整双智能体+审核流程中被逐一核查过，复核未发现除上述2例外的其他类似误判（见error_analysis_v1.md），v1.1新增的反例说明是面向未来批次的预防性修订。

### v1.0（2026-10-06，原始冻结版本）

初始冻结版本，用于产出 B001-PDF-01至05 全部50条（5篇×10维）已核验记录。完整处理版本记录见 `02_模型调用日志/model_call_manifest.jsonl`（18条调用记录的 `schema_version` 字段均为 `v1.0`，可逐条追溯）。D01、D02、D04、D07、D08、D09、D10 及 D03/D05/D06 中v1.1未触及的部分在v1.1中保持与v1.0完全相同的定义，不构成变更。

---

## 0. 总体设计说明

### 0.1 与研究问题的映射

| 研究问题 | 对应维度 |
|---|---|
| RQ1：现有研究如何表征水-电耦合方向、厂内冷却水和核心耦合方程 | D01、D02、D03 |
| RQ2：是否利用信息层快感知与水-热-水力慢演化的时间尺度差进行早期预警/主动控制 | D04、D05、D06 |
| RQ3：级联故障后果是否从物理网络服务损失延伸到人口、关键设施、社会脆弱性 | D07、D08、D09 |
| RQ4：作者明确承认的局限和未来方向，是否支持第3-5章研究空白识别 | D10 |

### 0.2 跨维度通用规则（适用于全部 D01–D10）

1. **论文自身方法 vs 被引方法**：每条记录必须显式标注 `own_method_vs_cited`：
   - `Paper_Own_Method`：该标签依据的是本文自己提出/实现/仿真的模型或方法；
   - `Cited_Other_Work`：文本只是在综述或引用他人方法，不能作为本文方法的证据；
   - `Mixed`：本文方法直接采用/修改了被引方法，且本文确实在自己的实验/模型中使用了它（不是单纯背景介绍）。
   - 仅 `Paper_Own_Method` 或 `Mixed` 可以作为该维度主标签的有效证据；纯 `Cited_Other_Work` 的文本只能记录在 `cited_context_note`（辅助字段），不能单独支撑主标签。

2. **四种回退状态**（当无法分配具体受控标签时，必须使用以下四者之一，不得混用或留空）：
   - `Not_Stated_In_Text`：已检索到的 Zone A–D 全文证据中完全没有涉及该构念（沉默，不代表论文否定它）。
   - `Explicitly_Not_Considered`：论文正文**明确声明**不考虑/未建模该构念（例如"we do not model..."），这是一个主动的否定性断言，必须单独区分，不能等同于 `Not_Stated_In_Text`。
   - `Insufficient_Evidence`：文本提到了该构念，但信息不足以确定具体子标签（例如只说"存在耦合关系"但未说明方向）。
   - `Evidence_Unavailable`：相关内容依赖于未保留的公式图像、表格图像或原始版面信息（Step 1 未能可靠抽取），而非论文本身未讨论。此状态下必须注明可能相关的页码，供人工回查原始 PDF。

3. **必需字段**（每条维度记录的通用 schema，具体见 `schema_v2.json`）：
   - `doc_id`、`dimension_id`（D01–D10）、`schema_version`
   - `primary_label`：受控标签或四种回退状态之一
   - `secondary_labels`：list，用于多选维度（D03、D08、D10），单选维度留空
   - `own_method_vs_cited`
   - `mechanism_judgment`：1–3句话的机制性判断，必须由证据支撑，不得脱离原文泛化
   - `uncertainty_note`：可选，说明标注者/Agent 的不确定来源
   - `evidence_ids`：list，至少1个（当 `primary_label` 不是 `Not_Stated_In_Text` 或 `Evidence_Unavailable` 时必填）
   - `verbatim_quote`：直接引用原文（逐字），`Not_Stated_In_Text` 时可留空
   - `section_id`、`page_numbers`
   - `equation_detail`（可选，仅当证据含公式时）：`{equation_number, variables, physical_meaning, page}`
   - `confidence`：0.0–1.0，Agent 自评
   - `agent_a_model_call_id`：指向 `model_call_manifest` 的外键

3. **禁止事项**（继承自 README 原规则，在本手册中具体化）：
   - 不得仅凭标题、摘要、关键词推断 D02–D09 的具体子标签（必须有 Zone B/C/D 正文证据）；
   - 不得把 HLA/软件数据交换等通用联合仿真技术细节自动解释为"真实 cyber 早期预警机制"（D04/D06）；除非原文明确将其与预警/主动控制功能关联；
   - 不得把一般水网压力方程自动解释为厂内冷却热-水力模型（D02）；
   - `accept`/`Paper_Own_Method` 判断只表示原文确有此表述，不表示该表述在工程/物理上正确。

---

## D01 — 水-电耦合方向（RQ1）

**构念定义：** 本文自身方法/模型中，电力系统与供水系统之间被显式建模的因果或约束方向。

**受控标签（单选主标签；如论文模型明确包含双向环节，选 `Bidirectional_Coupled`，不要分别勾选两个单向标签）：**

| 标签 | 定义 |
|---|---|
| `Water_to_Power` | 供水系统的状态/运行约束了电力系统（如水源可用性限制发电/抽水负荷） |
| `Power_to_Water` | 电力系统的状态/运行驱动供水系统调度（如电价/电网调度指令决定水泵/海水淡化运行） |
| `Bidirectional_Coupled` | 本文模型中两个方向都被显式表达（如联合优化、双向反馈） |
| `Parallel_No_Explicit_Coupling_Equation` | 两系统均被讨论，但本文方法中没有显式数学耦合方程将二者联系起来 |

**正例：** "本文提出一种优化策略……抽水/淡化负荷由电价和电网调度信号共同决定，受水力约束反作用于电网运行" → `Bidirectional_Coupled`。

**反例（应判为 `Parallel_No_Explicit_Coupling_Equation`）：** 论文分别讨论电网韧性和供水韧性，仅在引言中提及"二者相关"，但模型中无共享变量或联立约束。

**排除规则：** 若耦合关系仅出现在被引用文献的方法描述中（`Cited_Other_Work`），不可作为本文 D01 标签证据。

**边界案例：** 若论文方法仅用供水负荷作为电力系统的一个外生输入参数（不反馈），且未对供水系统本身建模，判 `Power_to_Water`（单向，供水在此仅为外生扰动/输入，不构成双向耦合）。

---

## D02 — 厂内冷却水建模（RQ1）

**构念定义：** 本文方法是否将发电厂冷却水过程作为独立的热-水力过程显式建模（区别于泛泛的城市/市政供水网络）。

**受控标签（单选）：**

| 标签 | 定义 |
|---|---|
| `Explicit_InPlant_Cooling_Model` | 存在针对电厂冷却水的热-水力方程/参数（如冷凝器冷却水温度-流量关系、取水限制导致机组降出力） |
| `Generic_Water_Network_Only` | 仅建模城市/市政供水网络（管网压力、海水淡化、水厂等），未涉及电厂冷却专属过程 |
| `Both_Present` | 同时包含电厂冷却热-水力模型与更广泛的城市供水网络模型 |
| `Mentioned_Only_Not_Modeled` | 背景/引言/讨论提及电厂冷却水问题，但本文正式模型未纳入 |

**正例：** 文中给出冷却水取水温度升高导致机组最大出力下降的函数关系式 → `Explicit_InPlant_Cooling_Model`。

**反例：** 论文建模"水-电耦合微网"中的水泵、海水淡化、水库，但未涉及任何发电厂冷却水过程 → `Generic_Water_Network_Only`。

**特别提醒：** 避免将"水-能源纽带 (water-energy nexus)"这一宽泛框架性措辞自动等同于冷却水建模；必须有具体方程/参数作为证据。

---

## D03 — 核心耦合方程类型（RQ1）

**构念定义：** 本文方法中实际使用的、连接水与电变量的方程的数学性质。**多选维度**（一篇论文可同时具备多种方程类型，记录为 `secondary_labels` 列表，`primary_label` 取其中论文强调的主要类型或 `Mixed`）。

**受控标签集合（v1.1，新增第7项，加粗标注）：**

- `Hydraulic_Pressure_Flow_Equation`：节点压力/流量平衡方程（如 Hazen-Williams、水泵曲线）
- `Energy_Power_Balance_Equation`：电力平衡/机组组合/OPF 类约束，将水泵/淡化负荷与电网变量联立
- `Thermal_Hydraulic_Equation`：冷却/温度-流量类方程（专属 D02 的 `Explicit_InPlant_Cooling_Model` 情形）
- `Economic_Cost_Coupling_Equation`：仅通过联合目标函数（成本）耦合，无显式物理方程联立
- `Statistical_Empirical_Correlation`：数据驱动/统计拟合关系，非第一性原理方程
- **`Topological_Dependency_Equation`（v1.1新增）：** 基于图论/网络拓扑的二元依赖状态方程，描述基础设施层间依赖关系的功能状态（如 node-node、node-edge、node-path、geographical dependence 等二元乘积/布尔形式），**不涉及连续物理量**（压力、流量、功率、温度等）。与 `No_Explicit_Equation_Qualitative_Only` 的关键区别是：本标签要求论文确实给出了可引用编号的显式方程，只是方程刻画的是拓扑/逻辑依赖状态而非连续物理过程；与 `Hydraulic_Pressure_Flow_Equation`/`Energy_Power_Balance_Equation` 的区别是：本标签方程中的变量是二元功能状态（0/1，正常/失效），不是连续的压力、流量或功率值。
- `No_Explicit_Equation_Qualitative_Only`：仅定性描述，无任何可引用编号的方程（注意：若存在编号方程但其数学性质是拓扑依赖类型，应判 `Topological_Dependency_Equation`，不應退回本标签）

**`Topological_Dependency_Equation` 正例（来自 B001-PDF-03）：** "Water supply facilities...are powered by the electric infrastructure located in the same geographic area, which means node-node dependence and use of Equation (1)." —— 显式编号方程(1)，但变量是二元依赖状态乘积，不是连续水力/电力物理量 → `Topological_Dependency_Equation`，而非 `No_Explicit_Equation_Qualitative_Only`，也不是 `Hydraulic_Pressure_Flow_Equation`。

**证据要求：** 必须引用具体方程编号及所在页码（`equation_detail` 字段必填，除非标签为 `No_Explicit_Equation_Qualitative_Only`；`Topological_Dependency_Equation` 同样必填 `equation_detail`，其 `physical_meaning` 字段应说明具体的依赖关系类型如node-node/node-edge等，而非物理量纲）。

---

## D04 — 信息层快感知机制（RQ2）

**构念定义：** 本文是否讨论/建模了针对电力或供水系统状态的快速（秒级至分钟级）网络/信息/传感/通信层感知机制。

**受控标签（单选）：**

| 标签 | 定义 |
|---|---|
| `Explicit_Fast_Sensing_Mechanism` | 明确描述 SCADA/PMU/实时监测/通信架构，并给出或暗示其时间尺度快于水力过程 |
| `Implicit_RealTime_Assumption` | 假设实时数据可用，但未描述具体感知/通信机制 |
| `Not_Addressed` | 未涉及 |

**排除规则：** HLA、协同仿真接口等软件数据交换机制若未被论文明确关联到"快速感知/预警"功能，不得自动判为 `Explicit_Fast_Sensing_Mechanism`；此时应判 `Not_Addressed` 或 `Insufficient_Evidence` 并在 `uncertainty_note` 说明。

---

## D05 — 水-热-水力慢演化表征（RQ2）

**构念定义：** 本文方法是否显式表达了供水/热力/水力过程相对电力过程更慢的动态时间尺度。

**受控标签（单选）：**

| 标签 | 定义 |
|---|---|
| `Explicit_MultiTimescale_Model` | 存在明确的多时间尺度结构（如日前+实时两阶段调度、不同步长的嵌套仿真） |
| `Single_Timescale_Only` | 水、电系统使用同一时间步长，无显式快慢区分 |
| `Qualitative_Mention_No_Formal_Model` | 文字提及时间尺度差异，但模型未正式区分 |
| `Not_Addressed` | 未涉及 |

**正例：** "日前阶段决策充分考虑实时功率波动，实时阶段修正可再生能源偏差" → `Explicit_MultiTimescale_Model`。

**⚠ 关键词陷阱/反例（v1.1新增，来自 B001-PDF-05 真实误判案例）：** "steady-state"（稳态）一词在不同论文语境中含义差异很大，**不能见到该词就默认论文在讨论时间尺度**。若论文的"稳态"实际指的是"扰动前状态 vs 扰动后状态"这类**前后快照比较**（例如地震损伤前后的系统性能对比），而不是"水-热-水力过程相对电力过程更慢"这一 D05 构念本身，应判 `Not_Addressed`，**不要**因为字面出现"稳态/steady-state"就机械地判为 `Single_Timescale_Only`——后者意味着"论文确实在模型层面统一处理了水电两侧的时间步长"，这是一个关于D05构念本身的判断，而非任意提及"稳态"二字即可触发。判别方法：先确认论文是否在讨论"水电两侧谁的动态更快/更慢"这一问题本身，再决定是否属于D05的任何子标签；若论文的分析框架根本不触及这一问题（如本案例中的概率地震损伤抽样模型），纵使出现"稳态"字样，也应判 `Not_Addressed`。

---

## D06 — 早期预警/主动控制机制（RQ2）

**构念定义：** 本文方法是否利用（或提出利用）快慢时间尺度差，实现早期预警或主动（前瞻性）控制，而非仅被动响应已发生的扰动。

**受控标签（单选）：**

| 标签 | 定义 |
|---|---|
| `Proactive_Anticipatory_Control` | 方法具备前瞻性，如滚动时域优化、基于预测的日前调度、预防性机组组合 |
| `Reactive_Control_Only` | 仅在扰动/偏差被观测到之后触发控制 |
| `Early_Warning_Alert_Mechanism` | 提出/评估了基于阈值或预测的预警/告警机制，不一定包含自动控制动作 |
| `Not_Addressed` | 未涉及 |

**辅助字段：** `justification_explicit`（布尔值）— 论文是否**明确**将该机制的设计动机归因于 D04/D05 所述的时间尺度差异（而非仅因为这是常见两阶段调度范式）。若仅为常规两阶段调度但未做此类时间尺度论证，仍记录主标签，但 `justification_explicit=false`，并在 `mechanism_judgment` 中说明。

**⚠ 关键词陷阱/反例（v1.1新增，来自 B001-PDF-03 正确规避案例，保留作为正面判例）：** "proactive"（主动）一词在韧性工程文献中经常指 **MCEER 韧性框架**意义上的"主动吸收能力"（proactive absorptive capacity）——这是一种**规划/设计阶段的结构韧性属性**（基础设施本身的鲁棒性，在灾害发生前的规划阶段就已确定），与D06构念要求的"**利用信息层实时快感知与物理慢动态之间的时间尺度差，在运行阶段进行前瞻性控制**"是完全不同的两个概念，即使两者都使用"proactive/主动"这个词。判别方法：确认论文中"主动"/"proactive"修饰的对象——如果修饰的是"结构/网络固有的鲁棒性属性"（规划设计阶段确定，运行阶段不再改变），应判 `Not_Addressed`；只有当"主动"修饰的是"运行阶段基于预测或实时感知而动态调整的控制/调度行为"时，才可能属于 `Proactive_Anticipatory_Control` 或 `Early_Warning_Alert_Mechanism`。**同时提醒：** 即使确认属于后者（运行阶段的前瞻性调度），仍需按 `own_method_vs_cited` 规则区分这是论文自己的方法还是论文引用的他人框架（参见 B001-PDF-04 案例：论文自身的IOR指标是反应式测量，另行引用的UC/GA调度框架才具有主动预见性，不可混淆归入本文方法的D06标签）。

---

## D07 — 级联故障后果扩展范围（RQ3）

**构念定义：** 本文自身分析/仿真实际追踪到的级联故障后果所达到的最远层级。

**受控标签（单选，取证据支持的最远层级；需在 `mechanism_judgment` 中说明是否也包含更近层级）：**

| 标签（由近及远） | 定义 |
|---|---|
| `Physical_Network_Service_Loss_Only` | 仅限物理网络自身的服务损失（如未供水量、停电负荷，以技术单位表达） |
| `Economic_Cost_Impact` | 延伸到经济成本/损失量化 |
| `Critical_Facility_Impact` | 延伸到具体关键设施（医院、水厂等命名实体）的服务中断 |
| `Population_Impact` | 延伸到受影响人口数量 |
| `Social_Vulnerability_Impact` | 延伸到社会脆弱性指标/人口统计脆弱性分析 |

**回退：** 若论文完全未讨论级联后果（例如仅做稳态优化，无故障/扰动场景），用 `Not_Stated_In_Text`。

---

## D08 — 人类/社会影响终点细节（RQ3）

**构念定义：** 在 D07 基础上，具体使用了哪些人类/社会影响度量方式。**多选维度**。

**受控标签集合：**

- `Population_Count_Affected`
- `Critical_Facility_Service_Disruption`（需命名具体设施类型，如医院、学校）
- `Social_Vulnerability_Index_Used`（如 SVI/CDC-ATSDR 指数或等效指标）
- `Named_Case_Region_Impact`（如 Shelby County 或其他命名地区的人类影响案例分析）
- `None_Reported`（与 D07 的 `Physical_Network_Service_Loss_Only`/`Economic_Cost_Impact` 通常配对）

---

## D09 — 案例/验证场景类型（RQ3）

**构念定义：** 本文用于验证的系统类型。

**受控标签（单选）：**

| 标签 | 定义 |
|---|---|
| `Synthetic_Test_System_Only` | 仅使用标准测试系统/合成网络（如 IEEE 测试系统、合成水网） |
| `Real_World_Named_Region` | 使用真实命名地区/系统（如 Shelby County、具体城市供水/电网公司数据） |
| `Hybrid_Synthetic_Calibrated_To_Real_Data` | 合成网络但以真实数据校准关键参数 |
| `Not_Applicable_Theoretical_Only` | 纯理论/方法论文，无案例验证 |

---

## D10 — 作者承认的局限与未来方向（RQ4）

**构念定义：** 作者在正文（通常在讨论/结论章节）明确承认的方法局限性，和/或明确提出的未来研究方向。**多选维度**，每个具体局限/方向各记一条证据。

**受控标签集合：**

- `Scalability_Limitation`（计算规模/可扩展性局限）
- `Data_Availability_Limitation`（数据可得性局限）
- `Model_Simplification_Limitation`（线性化、理想化假设等简化局限）
- `Validation_Generalizability_Limitation`（案例数量有限、仅合成系统、外推性局限）
- `Missing_Factor_Limitation`（明确声明未考虑某具体因素，须在 `verbatim_quote` 中包含该因素名称）
- `Future_Work_Direction`（前瞻性的未来研究建议，不一定是对本文的局限性批评）
- `Not_Stated_In_Text`（作者完全未讨论局限或未来方向——需谨慎使用，多数论文至少有简短局限段）

**与第3–5章映射字段（辅助，非受控标签）：** `maps_to_chapter`：{3, 4, 5, None}，由 Agent A 给出初步建议，Agent B 复核；该字段仅用于后续空白识别参考，不是 D10 的正式标签组成部分，不计入 Agent A/B 一致率统计。

---

## 附：状态字段与第2章设计文档已提出概念的对应关系

本手册的四种回退状态 (`Not_Stated_In_Text` / `Explicitly_Not_Considered` / `Insufficient_Evidence` / `Evidence_Unavailable`) 对应并具体化了 README 第2.5.3节与P0-2条目中提出但未操作化的"未陈述""未考虑""证据不足""证据无法获取"概念。`accept`/`revise`/`reject`/`insufficient_evidence` 是 **Agent B Critic 的决策状态**（见 `agent_prompts_and_manifest_v1.md`），与本手册四种回退状态是不同层面的字段，不要混淆：前者描述 Agent A 标签是否被原文支持，后者描述 Agent A 能否从文本中分配具体受控标签。
