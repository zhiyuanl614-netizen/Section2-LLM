# schema v1.1 修订提案与变更记录（2026-10-06）

**提案状态：已实施**（按 `P1_frozen_pipeline_config_v1_LOCKED.md` 第3节变更控制流程完成：缺陷记录→新版本号→变更日志→不回溯覆盖旧记录）
**触发来源：** Step 5 错误分析（`05_人工金标准与方法评估/03_错误分析/error_analysis_v1.md`）与 Step 6 跨文献综合（`06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.md`）中记录的2类真实缺陷。

---

## 1. 变更范围（仅2处，无其他改动）

| 缺陷 | 影响维度 | 修复方式 | 是否新增/修改受控标签 |
|---|---|---|---|
| ① B001-PDF-03 的图论拓扑依赖方程无法被现有6类D03标签描述 | D03 | 新增第7个标签 `Topological_Dependency_Equation` | 是，新增标签 |
| ② "proactive"/"steady-state" 等常见工程术语曾造成1次误判（PDF-05 D05）、1次正确规避（PDF-03 D06） | D05、D06 | 编码手册增加"关键词陷阱/反例"判例说明 | 否，仅补充判别指引，标签集不变 |

**明确不在本次修订范围内的事项（避免范围蔓延）：**
- `own_method_vs_cited` 字段在全部50条记录中均为 `Paper_Own_Method`（Step5审核标注的"审核盲点"，非已证实的错误）——本次不做修改，留待未来有真实触发 `Cited_Other_Work`/`Mixed` 分支的样本出现时再评估是否需要调整。
- D04、D07、D08、D09、D10 及 D01、D02 的受控标签集——本次复核未发现这些维度有类似的缺口或陷阱案例，保持v1.0原状。
- FRDI 计算方法（`06_跨文献综合与FRDI/02_FRDI计算/`）——与本次schema修订无关，不受影响。

---

## 2. 具体变更内容

### 2.1 D03 新增标签 `Topological_Dependency_Equation`

**定义：** 基于图论/网络拓扑的二元依赖状态方程（node-node、node-edge、node-path、geographical dependence 等二元乘积/布尔形式），描述基础设施层间依赖关系的功能状态，不涉及连续物理量。

**判别边界：**
- 与 `No_Explicit_Equation_Qualitative_Only` 的区别：本标签要求论文确有可引用编号的显式方程；若方程的数学性质是拓扑依赖类型，不应退回"无显式方程"这一标签。
- 与 `Hydraulic_Pressure_Flow_Equation`/`Energy_Power_Balance_Equation` 的区别：本标签方程中的变量是二元功能状态（0/1），不是连续的压力、流量或功率值。

**完整定义、正例和证据要求见：** `schema_v2_D01-D10_codebook.md` D03章节（已更新）。

### 2.2 D05、D06 关键词陷阱反例

**D05新增反例：** "steady-state"（稳态）一词若指"扰动前后快照比较"而非"水-热-水力相对电力的慢动态时间尺度"，应判 `Not_Addressed`，不可机械触发 `Single_Timescale_Only`。

**D06新增反例：** "proactive"（主动）一词若修饰"规划设计阶段的结构韧性属性"（MCEER框架意义）而非"运行阶段基于时间尺度差的前瞻控制"，应判 `Not_Addressed`。

**完整判例见：** `schema_v2_D01-D10_codebook.md` D05、D06章节（已更新）。

---

## 3. 变更验证（程序化确认，非口头声明）

1. **向后兼容性验证：** 对全部50条v1.0已核验记录重新用v1.1 schema的受控标签集做校验，**0条记录失效**（新标签是纯增量，不影响旧记录合法性）——详见本次会话验证脚本输出。
2. **新标签实际可解决原缺陷：** 制作了演示性重分类文件 `B001-PDF-03_D03_v1.1_reclassification_demo.json`，将B001-PDF-03的D03记录按v1.1重新表达为 `Topological_Dependency_Equation`，`evidence_id`、`verbatim_quote`均复用原v1.0记录并重新验证通过（evidence_id存在性、quote逐字匹配）。**该演示文件不替代正式核验结果**，`05_核验通过结果/B001-PDF-03_verified_10d.json` 中的v1.0原始记录（`No_Explicit_Equation_Qualitative_Only`，schema_version=v1.0）保持不动。
3. **版本溯源完整性：** 已确认全部50条正式核验记录和全部18条manifest调用记录均带有 `schema_version: "v1.0"` 字段，可明确区分于v1.1，不存在版本混淆风险。

---

## 4. 文件变更清单

| 文件 | 变更 |
|---|---|
| `schema_v2_D01-D10_codebook.md` | 标题更新为"当前版本v1.1"；新增"变更日志"章节；D03章节新增标签定义+正例；D05、D06章节新增关键词陷阱反例 |
| `schema_v2.json` | `schema_version`: `"v1.0"` → `"v1.1"`；新增 `version_history` 字段；D03的`labels`数组新增`Topological_Dependency_Equation` |
| `schema_v1.0_frozen_snapshot.json`（新建） | v1.0版本的完整不可变快照，修订前的原始副本，供未来审计对比 |
| `B001-PDF-03_D03_v1.1_reclassification_demo.json`（新建） | 演示性重分类文件，验证新标签有效性，明确标注非正式核验结果 |
| `05_核验通过结果/*.json` | **未改动**——所有v1.0正式核验记录原样保留 |

---

## 5. 遗留事项（本次修订未解决，仍待后续处理）

1. 若未来扩大语料规模并重新执行Step 4，应优先使用v1.1 schema，并在新产出记录的 `schema_version` 字段如实标注 `v1.1`，不得与现有v1.0记录混淆统计。
2. 是否要把B001-PDF-03的D03记录**正式**重新跑一遍Agent A/B协议、用v1.1标签替换v1.0结果并写入05_核验通过结果——本次未做此事（演示文件只是方法验证），如需正式执行需用户确认后作为一次新的、独立留痕的批次动作，而不是静默替换。
3. D05/D06的关键词陷阱反例目前只基于本语料2个样本点总结，样本量极小，不排除未来语料中出现其他未被本次反例覆盖的新陷阱模式；这是v1.1本身的局限，不是未修复的缺陷。
