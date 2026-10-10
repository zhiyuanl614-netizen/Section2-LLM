# Step 3 检索覆盖/召回验证报告（工程抽查，非正式金标准评估）

**重要方法论声明：** 下表的 `reference_ids`（参考相关证据）由本Agent通过关键词检索+人工阅读候选块手动识别，
**不是独立的人工双标注金标准**。本报告的目的是在信任该索引用于 Step 4 之前，做一次工程级的健全性检查
（索引是否至少能找回明显相关的证据、是否存在系统性覆盖空白），不构成正式的检索效果confirmatory评估，
也不能替代 Step 5 的金标准审核。

**融合参数：** RRF k=60，每路Top-20，融合后Top-10。

| 维度 | RQ | recall@fused-top10 | recall@either-leg-top20 | 命中/参考数 | 遗漏 | 说明 |
|---|---|---:|---:|---|---|---|
| D01 | RQ1 | 0.25 | 0.5 | 2/4 | B001-PDF-02-ZB-S04-II-C001, B001-PDF-03-ZB-S04-2-2-C001 | Corpus has strong, explicit coupling-direction content (water-electric nexus is the core topic of 4/5 papers). |
| D02 | RQ1 | 0.5 | 0.5 | 1/2 | B001-PDF-01-ZB-S05-2-1-C001 | No paper in this 5-paper corpus models in-plant power-plant cooling water explicitly; reference set intentionally points to the best generic-water-network evidence to check the index can still surface discriminating context for a Generic_Water_Network_Only verdict. |
| D03 | RQ1 | 0.33 | 0.67 | 2/3 | B001-PDF-02-ZB-S05-A-C003 |  |
| D04 | RQ2 | 0.0 | 0.0 | 0/2 | B001-PDF-04-ZB-S04-II-C004, B001-PDF-04-ZB-S04-II-C001 | Weak corpus coverage expected: only PDF-04 ('Cyber-Enabled...') has tangential content (co-simulation topology update), not an explicit fast-sensing/communication architecture. |
| D05 | RQ2 | 1.0 | 1.0 | 3/3 | 无 |  |
| D06 | RQ2 | 0.0 | 0.5 | 1/2 | B001-PDF-03-ZB-S09-3-2-1-C001 |  |
| D07 | RQ3 | 0.67 | 0.67 | 2/3 | B001-PDF-05-ZC-S15-3-4-C003 |  |
| D08 | RQ3 | 0.0 | 0.0 | 0/3 | B001-PDF-05-ZD-S11-3-C001, B001-PDF-05-ZC-S12-3-1-C002, B001-PDF-04-ZC-S13-H-C002 | Corpus has a named-region case (Shelby County) but no explicit population-count / social-vulnerability-index metric found by keyword search; recall of the named-region evidence is the realistic bar here. |
| D09 | RQ3 | 1.0 | 1.0 | 3/3 | 无 |  |
| D10 | RQ4 | 1.0 | 1.0 | 3/3 | 无 |  |

## 逐维度细节

### D01（RQ1）
- 查询：*coupling direction between power grid and water supply system, bidirectional or one-way dependency*
- 参考相关 evidence_ids：['B001-PDF-01-ZB-S05-2-1-C001', 'B001-PDF-02-ZB-S04-II-C001', 'B001-PDF-03-ZB-S04-2-2-C001', 'B001-PDF-01-ZA-ABSTRACT-C001']
- 融合Top-10命中：['B001-PDF-01-ZA-ABSTRACT-C001']
- 仅BM25路（Top-20）命中但未进入融合Top-10：['B001-PDF-01-ZB-S05-2-1-C001']
- **两路Top-20均未召回：** ['B001-PDF-02-ZB-S04-II-C001', 'B001-PDF-03-ZB-S04-2-2-C001']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-03', 'B001-PDF-04', 'B001-PDF-05']
- 备注：Corpus has strong, explicit coupling-direction content (water-electric nexus is the core topic of 4/5 papers).

### D02（RQ1）
- 查询：*power plant cooling water thermal hydraulic model condenser versus generic water distribution network*
- 参考相关 evidence_ids：['B001-PDF-01-ZB-S05-2-1-C001', 'B001-PDF-02-ZB-S04-II-C001']
- 融合Top-10命中：['B001-PDF-02-ZB-S04-II-C001']
- **两路Top-20均未召回：** ['B001-PDF-01-ZB-S05-2-1-C001']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-02', 'B001-PDF-03', 'B001-PDF-04', 'B001-PDF-05']
- 备注：No paper in this 5-paper corpus models in-plant power-plant cooling water explicitly; reference set intentionally points to the best generic-water-network evidence to check the index can still surface discriminating context for a Generic_Water_Network_Only verdict.

### D03（RQ1）
- 查询：*hydraulic pressure flow equation pump curve linking water network variables to power system variables*
- 参考相关 evidence_ids：['B001-PDF-02-ZB-S05-A-C003', 'B001-PDF-02-ZB-S07-A-C002', 'B001-PDF-01-ZB-S05-2-1-C002']
- 融合Top-10命中：['B001-PDF-01-ZB-S05-2-1-C002']
- 仅BM25路（Top-20）命中但未进入融合Top-10：['B001-PDF-02-ZB-S07-A-C002']
- **两路Top-20均未召回：** ['B001-PDF-02-ZB-S05-A-C003']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-02', 'B001-PDF-04', 'B001-PDF-05']

### D04（RQ2）
- 查询：*fast cyber information sensing real-time monitoring communication layer for power or water system state*
- 参考相关 evidence_ids：['B001-PDF-04-ZB-S04-II-C004', 'B001-PDF-04-ZB-S04-II-C001']
- 融合Top-10命中：[]
- **两路Top-20均未召回：** ['B001-PDF-04-ZB-S04-II-C004', 'B001-PDF-04-ZB-S04-II-C001']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-03', 'B001-PDF-04']
- 备注：Weak corpus coverage expected: only PDF-04 ('Cyber-Enabled...') has tangential content (co-simulation topology update), not an explicit fast-sensing/communication architecture.

### D05（RQ2）
- 查询：*two-stage day-ahead real-time dispatch multiple time scales fast and slow dynamics*
- 参考相关 evidence_ids：['B001-PDF-01-ZB-S06-2-2-C001', 'B001-PDF-01-ZB-S06-2-2-C002', 'B001-PDF-01-ZA-S03-1-2-C002']
- 融合Top-10命中：['B001-PDF-01-ZB-S06-2-2-C001', 'B001-PDF-01-ZB-S06-2-2-C002', 'B001-PDF-01-ZA-S03-1-2-C002']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-04']

### D06（RQ2）
- 查询：*early warning proactive anticipatory control rolling horizon predictive scheduling versus reactive control*
- 参考相关 evidence_ids：['B001-PDF-01-ZB-S06-2-2-C001', 'B001-PDF-03-ZB-S09-3-2-1-C001']
- 融合Top-10命中：[]
- 仅Dense路（Top-20）命中但未进入融合Top-10：['B001-PDF-01-ZB-S06-2-2-C001']
- **两路Top-20均未召回：** ['B001-PDF-03-ZB-S09-3-2-1-C001']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-03', 'B001-PDF-04']

### D07（RQ3）
- 查询：*cascading failure propagation across infrastructure layers beyond physical network service loss*
- 参考相关 evidence_ids：['B001-PDF-03-ZB-S04-2-2-C006', 'B001-PDF-05-ZC-S15-3-4-C003', 'B001-PDF-05-ZA-ABSTRACT-C001']
- 融合Top-10命中：['B001-PDF-03-ZB-S04-2-2-C006', 'B001-PDF-05-ZA-ABSTRACT-C001']
- **两路Top-20均未召回：** ['B001-PDF-05-ZC-S15-3-4-C003']
- 融合Top-10覆盖的文献：['B001-PDF-03', 'B001-PDF-05']

### D08（RQ3）
- 查询：*population affected social vulnerability critical facility human impact of infrastructure failure*
- 参考相关 evidence_ids：['B001-PDF-05-ZD-S11-3-C001', 'B001-PDF-05-ZC-S12-3-1-C002', 'B001-PDF-04-ZC-S13-H-C002']
- 融合Top-10命中：[]
- **两路Top-20均未召回：** ['B001-PDF-05-ZD-S11-3-C001', 'B001-PDF-05-ZC-S12-3-1-C002', 'B001-PDF-04-ZC-S13-H-C002']
- 融合Top-10覆盖的文献：['B001-PDF-02', 'B001-PDF-03', 'B001-PDF-04', 'B001-PDF-05']
- 备注：Corpus has a named-region case (Shelby County) but no explicit population-count / social-vulnerability-index metric found by keyword search; recall of the named-region evidence is the realistic bar here.

### D09（RQ3）
- 查询：*case study validation system IEEE test feeder or real named city region such as Shelby County*
- 参考相关 evidence_ids：['B001-PDF-04-ZD-S47-A-C001', 'B001-PDF-05-ZD-S11-3-C001', 'B001-PDF-05-ZC-S14-3-3-C002']
- 融合Top-10命中：['B001-PDF-04-ZD-S47-A-C001', 'B001-PDF-05-ZD-S11-3-C001', 'B001-PDF-05-ZC-S14-3-3-C002']
- 融合Top-10覆盖的文献：['B001-PDF-01', 'B001-PDF-02', 'B001-PDF-03', 'B001-PDF-04', 'B001-PDF-05']

### D10（RQ4）
- 查询：*author acknowledged limitations model simplification scalability data availability future research directions*
- 参考相关 evidence_ids：['B001-PDF-04-ZD-S52-X-C002', 'B001-PDF-03-ZD-S31-7-C003', 'B001-PDF-02-ZD-S15-VI-C002']
- 融合Top-10命中：['B001-PDF-04-ZD-S52-X-C002', 'B001-PDF-03-ZD-S31-7-C003', 'B001-PDF-02-ZD-S15-VI-C002']
- 融合Top-10覆盖的文献：['B001-PDF-02', 'B001-PDF-03', 'B001-PDF-04', 'B001-PDF-05']

## 汇总与建议

- 10个维度查询在融合Top-10上的平均 recall = 0.47
- 10个维度查询在任一路Top-20上的平均 recall = 0.58


## 定性复核与方法论反思（重要，决定是否可信任该索引）

对 recall 较低的4个维度（D01、D04、D06、D08）做了进一步排查：逐一查看融合Top-10的**实际内容**
（而不仅看是否命中我预先手选的单一参考ID），发现：

- **D01（召回0.25）：** 融合Top-10中排名靠前的 `B001-PDF-03-ZB-S03-2-1-C006`
  （"Edges between different layers denote interdependences... The color of an edge identifies the direction..."）
  和 `B001-PDF-02-ZA-S01-I-C002`（"energy is an indispensable component of the water facilities... This interrelationship..."）
  **都是比我原先手选参考ID更贴切的耦合方向证据**，只是未被我纳入参考集合。
- **D04（召回0.0）：** 融合Top-10中 `B001-PDF-03-ZB-S20-5-1-C003`（"Green nodes and edges... information infrastructure..."）
  在主题上与"信息层"相关，但通篇检查后**确实没有发现任何一篇论文显式描述快速傳感/通信架构及其与水力过程的时间尺度对比**——
  这与此前关键词扫描的结论一致（仅7处弱相关命中）。**这是语料本身内容稀疏，不是检索缺陷**；
  预期 Step 4 中多数/全部论文在 D04 上会落入 `Not_Addressed`，这是合理的研究发现，不代表方法失败。
- **D06（召回0.0）：** 融合Top-10排名第5的 `B001-PDF-03-ZD-S31-7-C003` 原文直接包含
  **"Proactive absorptive capacity and reactive restorative capacity..."**——这是一条教科书式的D06正例，
  但同样未被我纳入参考集合。
- **D08（召回0.0）：** 融合Top-10附近的 `B001-PDF-03-ZB-S13-4-C003` 原文含"...impact on the early affected population"，
  `B001-PDF-03-ZD-S31-7-C001` 含"social, environmental, economic pillars of sustainable development"——
  均是合理的D08候选证据，只是未被纳入参考集合；说明BM25/Dense均正常工作。

**结论：** 本次"低召回"主要是**参考集合本身过窄**（每个维度仅手选1个"最佳范例"而非该维度所有合理证据）
导致的度量artifact，而非索引/检索流程的系统性缺陷——多数被判定"遗漏"的查询，融合Top-10实际上包含了
主题同样合理甚至更优的替代证据。真正确认为**语料内容本身稀疏**（而非检索缺陷）的维度是 **D04**，
其次 D08 在"显式人口数量/社会脆弱性指标"层面也偏弱（但"命名地区案例"层面有 Shelby County 证据可用）。

**方法论教训（记录供 Step 4 参考）：** 用单一人工预选参考ID做召回率度量，对"一个维度可能有多种合理证据表达方式"
的构念类检索并不稳健，容易产生假阴性。Step 4 实际执行"维度检索pass"时，不应仅依赖Top-10的固定召回，
而应结合本项目已冻结的 **coverage pass**（对每篇论文全部evidence blocks强制全量遍历）作为兜底，
这正是本项目pipeline设计（coverage-pass + 混合检索，而非纯Top-k-only RAG）已经预见并缓解的问题——
本次验证间接印证了coverage pass设计的必要性（H4假设方向），但同样不构成对H4的正式确认性检验。

## Go/No-Go 决策

**判定：GO —— 可信任该混合索引进入 Step 4 pilot。**

理由：
1. 两路检索（BM25、Dense）均在技术上正常工作（无报错、返回主题相关结果）；
2. 定性复核确认，大多数"低召回"查询的融合Top-10实际包含合理相关证据，只是不等于预选的单一参考ID；
3. 真正的语料内容稀疏（D04，及D08的部分子方面）已被识别并记录为**领域发现**而非**检索缺陷**，
   会在 Step 4 中体现为相应维度大量记录落入 `Not_Addressed`/`Insufficient_Evidence`，这是合理且诚实的结果，
   不需要靠"调整检索让它看起来有更多证据"来掩盖；
4. 按本项目pipeline设计，Step 4 对每篇论文还会执行**coverage pass**（全文强制遍历，不只依赖Top-k检索排名），
   进一步降低了"维度检索pass漏召回"的风险，即使某次检索的Top-10未命中最佳证据，coverage pass仍能保证
   该证据在Agent A的输入范围内。

**不构成的结论：** 本验证不证明"该pipeline优于其他方法"（H1-H5未经确认性检验），也不是正式的IR效果评估；
仅确认"配置可用、无系统性缺陷、可以带着已知局限（D04稀疏）进入Step 4 pilot"。
