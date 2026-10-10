# RQ1 v1.2 文本范围 Pilot：B001-PDF-04

- **执行日期：**2026-10-08
- **状态：**范围规则试跑，不替换 `05_核验通过结果/B001-PDF-04_verified_10d.json` 中的 v1.0记录。
- **试跑维度：**D01、D02；D03只登记范围外状态。
- **边界：**只读当前239版 evidence blocks；不读取、转录、解释或核验任何公式的数学结构。特别用一个 `formula_layout_risk=true` 块检验“可读叙述可用、公式仍排除”的新规则。
- **执行者披露：**本文件为 Arena.ai Agent 同会话的辅助方法试跑与自我核对，不是独立人类领域专家签审，也不是隔离的双模型审核。

## D01 — 水—电耦合方向（文本证据版）

**Pilot标签：** `Bidirectional_Coupled`  
**置信度：**0.95（Agent自评，不是统计置信区间）

**支持文字：**

> “The main dependence of the EPS on the WDS is the water required for the cooling cycle of thermoelectric power generation. The main dependence of the WDS on the EPS is the electric power needed for pumping water from a source to the treatment plant and end-user through the WDS.”

- `evidence_id`: `B001-PDF-04-ZA-S01-I-C001`
- Section: `I. INTRODUCTION`
- PDF物理页: 3
- 核对说明：句子本身分别写明 EPS 对 WDS 的水需求，以及 WDS 对 EPS 的电力需求，支持双向文字描述。结论没有使用公式或方程编号。

**范围审查：**通过。所引文字即使不看后续方程也可独立支持标签。

## D02 — 厂内冷却水建模（文本证据版）

**Pilot标签：** `Both_Present`  
**置信度：**0.93（Agent自评，不是统计置信区间）

**支持文字一（通用水网与冷却需求之间的接口）：**

> “The relevant simulation data exchanged between the power system and wa-ter network simulations included EPS network conﬁgurations, pump electric power consumption as an identiﬁable component of power system loads, and thermal generation cooling water requirements, which were used as node demands within the water system.”

- `evidence_id`: `B001-PDF-04-ZB-S04-II-C001`
- Section: `II. OPTIMIZATION–SIMULATION APPROACH`
- PDF物理页: 4

**支持文字二（冷却水作为水网中的显式服务需求）：**

> “Cooling water is supplied to the power plants in the WDS from both a freshwater source and a reclaimed water source (shown in Fig. 5). This cooling water is pumped to each power plant through a freshwater pumping station and a reclaimed water pumping station. The WDS control optimization–simulation model attempts to maximize the supply of reclaimed water for power plants.”

- `evidence_id`: `B001-PDF-04-ZD-S48-B-C001`
- Section: `B. Example WDS`
- PDF物理页: 13–14

**风险块检查（仅叙述，不审公式）：** `B001-PDF-04-ZC-S12-G-C001` 被标为 `formula_layout_risk=true`，但其公式前有可独立理解的自然语言说明：“The index function relating system performance to the amount of cooling water that is being supplied is related to a conservative estimate of the storage tank level …”。这类说明可支持“冷却水量被纳入性能指标”的文本观察；本 pilot **不**据该块解释方程、分段形式、变量、参数或公式编号，也不需要转录公式。该块不是上述 D02 标签成立的唯一依据。

**范围审查：**通过。非风险块的模型接口与案例叙述已足以支持 `Both_Present`；没有从风险块里的数学片段推断标签。

## D03 — 核心耦合方程类型

**状态：**`Not_Analyzed_Out_Of_Scope`。本 pilot 不判断 PDF-04 是否存在或使用任何特定方程；该状态不表示“无方程”或“定性模型”，不进入结果或指标。

## Pilot Gate 结果

| 检查 | 结果 | 说明 |
|---|---|---|
| 文本引用可逐字匹配当前 evidence block | 通过 | 三条引用均来自当前239版块；待正式批次用脚本再作逐字校验 |
| D01/D02可由自然语言独立支持 | 通过 | 双向依赖与冷却水需求均有直接文字陈述 |
| 对公式结构/参数的推断 | 未发现 | 风险块只取独立叙述句，公式内容未进入判断 |
| D03状态是否与“未涉及/证据不可得”混淆 | 未混淆 | 单独记为范围外，不作论文性质判断 |
| 是否满足领域专家独立终审 | 否 | 需在发表前由人类领域专家抽查；本 Agent 试跑不能替代 |

**Pilot结论：** v1.2 的“只编码清晰文本，不编码方程结构”规则对 PDF-04 可操作，且能够保留冷却水模型这一有用的文本层信息。建议进入其余4篇的 D01/D02 文本复核前，先完成程序化 quote/evidence/page 校验并保留逐条审计记录。
