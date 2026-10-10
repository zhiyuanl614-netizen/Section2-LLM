# Section2-LLM 项目说明（按 RAG 工作流程）

> **当前研究目标与范围澄清（2026-10-08）：**总目标不变：通过领域文献学习提出三项候选研究差距/前沿方向，形成研究问题/假设，再由大语言模型用可回溯证据检验支持、反例或不确定性。当前5篇 PDF 是先导语料；D01–D10是操作化编码维度，某些标签/维度在5篇中未出现属于正常样本观察，不是删除RQ或推断领域不存在。公式转录、数学结构比较和推导按用户确认不纳入当前分析，但这只调整公式层证据处理，不改变研究总目标或三项候选方向。下文标注为历史状态或历史设计的段落需与本段及锁定配置共同阅读。2026-10-10 按用户要求移除了 `审计记录/` 归档目录；保留的冻结 QA/运行清单仍保有生成时的历史路径字段，未回写。

## 2026-10-10 当前状态（优先于下文历史 checkpoint）

- **方向来源澄清：**三项既有候选方向已在论文第一节 Introduction 中通过领域文献对比提出。当前 pipeline 不需要在线搜索，也不需要新增代码步骤来生成候选方向；Step 1–8 优化的重点是以既有方向为输入，完成可追溯证据检索、抽取、整合与检验。三项方向保持不变。
- **当前样本边界：**只分析现有5篇 PDF；D01–D10 中有些维度/标签未出现是先导样本观察，不代表领域不存在，也不作为删除研究问题的依据。公式转录、推导和方程类型分析不进入新版结论/质量指标；原 PDF、evidence blocks 和公式风险 metadata 保留。
- **已完成的隔离与下游修复：**v1.2 local Step 4 的模型 payload 已隔离 D02 未定稿 boundary rule，并保留 PDF-03/D02 人工裁定状态；Step 5 v1.2.1 将 D03 限定为范围状态 metadata；Step 6 新 runner 只接受完整5篇真实本地 Step 4 ledger、在提示词中过滤 D03，并要求精确引用。表格/图表使用新版本路径，不覆盖 legacy 文件。
- **本轮实际验证：**API 批处理目录内 12 项单元测试通过，覆盖 mock/dry-run/引用校验与完整五篇样本门槛；这不是实际本地 LLM、真实 Step 3/4 批次或 Step 6 运行验证。尚未执行 Step 3/4 真实本地模型跑批，也未运行 Step 6 模型调用；未做在线检索。
- **当前静态先导产物：**Step 5 描述频数、Step 7 workbook/figures 基于已有 provisional static ledger，不是新的模型输出。当前修订版图位于 `07_图表与章节输出/01_图表_2-1至2-4/v1.2_text_scope_static_pilot_20261010_r2/`；工作簿为 `07_图表与章节输出/02_表格/chapter2_tables_v1.2.1_text_scope_static-pilot-v2.xlsx`。初版派生图表/工作簿保留作历史版本，当前以 `_r2`/`-v2` 为准。
- **本地平台预览：**`平台/` 现包含5篇正式 PDF、239个 evidence blocks、45条 D03 排除后的活动编码记录及来源追溯图。正式 release 保持只读；本机 loopback 可把新 PDF 上传到隔离 run，不会扩充正式样本。网页可执行真实 Step 1/2 PDF 清洗与分块 wrapper，以及 Step 3 BM25-only 索引；Dense/新 run 图谱索引和网页 Step 04–07 尚未接入，界面如实标记未就绪。新增项目整体/方法流程架构图、带版本出处的图2-1至图2-4图库（其中 v1.2 static-pilot r2 目前只有图2-1/2-3；旧图标为历史档案）。单次 QA 另支持用户显式选择 CSTCloud Uni-API 或通用 OpenAI-compatible、按请求获取模型目录；外发仍仅限本次问题和最多5条非公式风险证据块，不发送 PDF；Key不落盘。批量云端 evidence 未获默认授权。共享 preview 禁用上传、密钥输入和外部 API。使用说明见 `平台/README_LOCAL.md`。28项离线平台/工作流/API 路由测试通过；未使用真实 API Key，亦未运行真实 Step 02（当前环境缺 PyMuPDF）或真实本地模型/服务商 API。

**研究目标：**基于大语言模型的全文证据挖掘，识别水—电耦合系统的前沿研究方向。  
**来源项目：**[zhiyuanl614-netizen/Section2-LLM](https://github.com/zhiyuanl614-netizen/Section2-LLM)

## 当前文件夹结构

| 阶段 | 路径 | 内容 / 状态 |
|---|---|---|
| 01 文献库 | `01_文献库/` | 当前原始语料：用户本轮指定的5篇 PDF，仅此5个文件。 |
| 02 PDF清洗与分块 | `02_PDF清洗与分块/` | 含 `01_Zones/`（Zone A–D 粗切片）与 `02_Chunks/`；软连字符换行修复后的当前冻结 `evidence_blocks.jsonl` 为239条（241为较早历史计数），详见 chunk QA/manifest。 |
| 03 证据索引与混合检索 | `03_证据索引与混合检索/` | 239块 dense+BM25 混合索引已构建；旧范围 Step 3 工程检查保留在检索运行清单；新增 v1.2 D01/D02 文本范围 smoke check（非独立 gold-set 评估），详见版本化报告。 |
| 04 LLM抽取与 Critic | `04_LLM抽取与Critic审查/` | 历史 v1.0/API 产物保留；v1.2 local Step 4 有隔离版脚本与 mock 测试，但尚无真实本地模型跑批。PDF-03/D02 仍未裁定。 |
| 05 人工金标准与评估 | `05_人工金标准与方法评估/` | 有历史 Agent 辅助评审产物（非独立专家金标准）；v1.2.1 新描述统计基于静态先导 ledger，不是新模型评估。 |
| 06 跨文献综合与 FRDI | `06_跨文献综合与FRDI/` | 有历史/静态先导综合与FRDI产物；v1.2 local Step 6 runner 已编写但尚未调用真实模型。 |
| 07 图表与章节输出 | `07_图表与章节输出/` | legacy 图表/工作簿保留；另有基于 static-pilot ledger 的版本化 v1.2.1 图表/表格，均非最终或新模型输出。 |
| 平台 | `平台/` | 正式 release 只读；loopback 可建立隔离 PDF run 并运行真实 Step 1/2 与 BM25-only Step 3。新增结果画布、项目/方法架构图、带 provenance 的图表库及单次 QA 的可选模型目录。Step 04–07 网页 runner 未就绪；共享预览禁用上传/API；非正式知识库或已审批领域事实图。 |

## 当前语料与执行状态（2026-10-05）

- `01_文献库/` 仅含本轮指定的5篇原始 PDF；此前文献库中的 manifest 和方法参考 PDF 已按要求移除。
- `/home/user/uploads/` 曾是同一5篇 PDF 的重复副本目录；比对 SHA-256 确认文件均与 `01_文献库/` 完全相同后，已移除该重复目录。按用户确认，保留 `01_文献库/` 中的5篇规范原始 PDF，以维持来源追溯和后续重跑能力。
- 已对这5篇 PDF 重新运行 Step 1，编号为 `B001-PDF-01` 至 `B001-PDF-05`。脚本、输出和 SHA-256 运行清单位于 `02_PDF清洗与分块/01_Zones/`；原始 PDF 仍保留在 `01_文献库/`。
- 此次重新运行只做本地 PDF 解析、清洗、章节树提取和 Zone A–D 粗粒度定向切片；没有运行 RAG 索引、真实 LLM API 调用或人工评估。
- 原先30篇文献的旧 Step 1 JSON、批次摘要与核验表已移除；当前 `02` 只保留这5篇的重跑结果。旧的30篇设计方案仍保存在下方整合的历史设计文档中，不代表当前语料数量。
- **Step 1 修复与 QA（2026-10-05）：**已针对标题误识别、Zone C 归类、作者回退、元数据来源和 PDF 字符映射问题修订解析器，并仅基于上述5篇原始 PDF 重跑。5篇均检测到章节树，Zone A–D 均非空，当前未分类回退章节为0；此结果仍是标题关键词与父级继承的启发式分类，`inherited from parent; verify` 项及全部切片仍需对照原文人工 QA，不能仅凭“0回退”认定分类无误。
- 当前章节树条目数与 Zone A/B/C/D 粗略词数（含少量标签/元数据）：`120.pdf`：17，670/2459/1324/459；`105...`：16，991/3403/1787/307；`643...`：32，521/6381/3385/1770；`46...`：54，428/1444/6180/962；`37...`：22，492/979/4546/1117。章节树和分区明细见 `02_PDF清洗与分块/01_Zones/step1_sliced_zones_preview.md`。
- 元数据现已在 JSON 中分字段保存，并记录 `metadata_sources`；摘要、作者、期刊、年份、DOI 和关键词均已抽取。`37...` 的 PDF 期刊卷期标注为2027，而 DOI 字符串含2026年份标记（首面另列2026在线日期）；保留 PDF 标注的卷期年，并将差异标为待核，没有据 DOI 擅自改年。`120`、`105`、`46` 也有 DOI 年份标记与卷期年不同的提示。
- 未映射 PDF 字符不再静默成为 `�` 或猜补：输出以 `⟦PDF_GLYPH_U+XXXX⟧` 保留提取到的码点提示，并按页码/字体记录警告。`105`、`643`、`46` 的文档级计数分别为89、29、174；这些码点不等于恢复出的数学符号，公式/特殊字符仍须对照 PDF 检查。当前 JSON/Markdown 中未发现 U+FFFD 替换字符。
- Zone A–D 是粗粒度预处理切片；在其基础上，Step 2 已生成241条正式细粒度 evidence blocks，均带稳定 `evidence_id`、章节/Zone 来源、页码、原始 Zone substring、Unicode 码点偏移及来源哈希。Step 1 的人工 QA 注意事项见 `02_PDF清洗与分块/01_Zones/QA_复核.md`；Step 2 自动 QA 与限制见 `02_PDF清洗与分块/02_Chunks/chunk_qa.md`。
- Step 2 默认目标180词、硬上限240词、无重叠；正文哈希与由章节标题+正文构成的 `retrieval_text` 哈希均已记录。offset 为 Step 1 Zone 字符串中的零起始、end-exclusive Unicode 码点位置，不是 PDF 原始偏移。共4条短块（少于40词），已在 QA 中逐条列明并保留原文。
- 对分块规则的初步检查：241块的词数中位数为181、均值为154.9；31块少于80词。作为可追溯的首版文本分块方案基本合理，但尚未完成人工边界抽查或真实检索评估。规则不专门识别公式/表格/列表，词数限制也不等于 embedding tokenizer 的 token 限制。重点复核公式风险块 `B001-PDF-03-ZC-S12-3-3-C003` 与 `...C004`。
- **截至本次更新，未执行** embedding/稠密向量索引、BM25 词法索引、检索、RAG/LLM 调用或人工评估；`03`–`07` 中的预留子目录不表示对应流程已经执行。
- Step 1 产物含 JSON、Markdown 预览、Excel/DOCX 核验报告和 `run_manifest.json`。清单记录了输入文件 SHA-256、脚本哈希和解析依赖版本；解析依赖当时固定于一个阶段专属的 `requirements.txt`，现已合并进根目录统一的 `requirements.txt`（避免多份依赖清单重复维护、互相漂移）。
- 原 `00_研究设计与配置/` 已移除；章节大纲、实验框架、设计验证报告及阶段说明均整合在本 README 后续部分。ZIP 文件已清理。

### 下次接续工作（当前 checkpoint，2026-10-06 更新）

**当前停止点（2026-10-06 更新）：P0（Step 1）、P1（冻结配置）、P2/Step 3（索引构建）、Step 4（双智能体LLM抽取，全部5篇/50条记录）、Step 5（Agent辅助金标准审核，非领域专家人工评审）均已完成。下一步进入 Step 6 跨文献综合。**

- Step 1 软连字符换行重排缺陷已修复并重跑（见 `02_PDF清洗与分块/02_Chunks/step1_hyphen_fix_verification_v2.md`）；`evidence_blocks.jsonl` 现为239条（新哈希），`chunk_qa.md` 已补充全量 `formula_layout_risk` 扫描（87/239块标记，非抽样）。
- 语料规模缺口已按用户决策解决：当前5篇语料按 **Route A（探索性/先导研究）** 处理，不执行 README 原设计的 G0–G5 消融矩阵，不做30篇确认性统计比较。
- P1 已冻结：D01–D10编码手册、embedding模型(`BAAI/bge-small-en-v1.5`)+真实tokenizer(`tiktoken cl100k_base`)+BM25分词器、Agent A/B prompt(v1.0)与`model_call_manifest` schema、单一最终pipeline配置。详见 **`P1_frozen_pipeline_config_v1_LOCKED.md`**（根目录），该文件汇总并索引全部P1子文件。
- Step 4 执行方式决策：由 Arena.ai Agent 在对话中直接执行真实推理完成 Agent A/B 抽取，不调用外部付费API（已在 `agent_prompts_and_manifest_v1_LOCKED.md` 中详细披露此方式与"真正独立双模型"的差异局限）。
- Step 5 人工金标准决策：由 Agent 辅助/模拟完成，但所有相关输出必须明确声明不满足"领域专家人工评审"要求。

**下一步（P2 / Step 3）：**

1. ✅ 已完成：基于 `P1_frozen_pipeline_config_v1_LOCKED.md` 锁定的配置，对已冻结的239个evidence blocks构建了dense（`BAAI/bge-small-en-v1.5`）+ BM25混合索引，使用RRF(k=60)融合。索引脚本、manifest见 `03_证据索引与混合检索/`（`step3_build_hybrid_index.py`、`03_检索运行清单/index_build_manifest.json`）。
2. ✅ 已完成：创建了覆盖 D01-D10 的10条检索测试查询，做了工程级召回/覆盖率验证（非正式金标准评估），详见 `03_证据索引与混合检索/03_检索运行清单/retrieval_validation_report.md`。结论：**GO**——索引技术上工作正常，低召回案例经定性复核主要是参考集合过窄的度量artifact而非检索缺陷；D04（信息层快感知）被确认为语料内容本身稀疏，预期多数论文落入`Not_Addressed`，这是合理研究发现。
3. ✅ 已完成：Step 4 LLM抽取（Agent A→Agent B→Agent A修订→Agent B终审完整协议）。先在 B001-PDF-01、B001-PDF-05 两篇上做pilot并验证JSON有效性/evidence可回溯性（0个校验问题），通过pilot gate后扩展到B001-PDF-02/03/04，现已覆盖全部5篇、50条（5篇×10维）记录。脚本见 `04_LLM抽取与Critic审查/step4_pilot_extraction.py`（pilot）与 `step4_batch2_extraction.py`（扩展批次）；输出见 `03_AgentA原始抽取/`、`04_AgentB_Critic审查/`、`05_核验通过结果/`；`02_模型调用日志/model_call_manifest.jsonl` 共18条调用记录。全量验证（必填字段、标签合法性、evidence_id存在性、verbatim_quote逐字匹配、section/page回溯、manifest schema/FK）50/50条记录0问题。
4. ✅ 已完成：Step 5 Agent辅助金标准审核（**非领域专家人工评审**，强制披露见下）。对全部50条记录做全量内部一致性复核，输出见 `05_人工金标准与方法评估/`：`01_人工金标准审核/agent_assisted_audit_v1.md`（逐文献审核+跨记录模式复核）、`02_评估指标/evaluation_metrics_v1.md`+`.json`+`step5_compute_metrics.py`（证据充分率/引用精确匹配率/章节页码可回溯率均100%；Agent A/B初次一致率92%，4条修订中2条为主标签级真实修正、2条为证据/次要标签级修正；pass4终审后0条未决分歧）、`03_错误分析/error_analysis_v1.md`（4个真实修正案例的根因分析+3类流程暴露出的schema缺口/关键词陷阱，含对PDF-03 D03受控词表缺口和D05/D06关键词陷阱不稳定性的讨论）。**强制声明：本审核与Agent A/B共享同一执行渠道，不满足"领域专家人工评审"要求；D02/D04/D05/D06/D08等关键难点维度的真正独立人工盲审仍是未落实的工作项。**
5. ✅ 已完成：Step 6 跨文献综合。只使用 `05_核验通过结果/` 中已核验的50条记录，产出于 `06_跨文献综合与FRDI/01_跨文献LLM综合/`：`synthesis_v1.md`（叙述版，含3个研究范式簇、按RQ1-RQ4/第3-5章映射的3条研究空白陈述及候选前沿方向3-1/4-1/5-1，逐条绑定evidence_id并标注反向证据/外推边界）+ `synthesis_v1.json`（机器可读版，供Step 7 FRDI计算读取，所有evidence_id已程序化验证存在且与来源记录一致）。**最高置信度发现：候选方向4-1（第4章cyber快感知空白）——D04在全部5篇文献均为`Not_Addressed`，是本语料中最一致、不依赖任何单篇边界判断的空白；最弱证据的是候选方向5-1（第5章人口/社会脆弱性空白）——核心证据仅来自1篇文献（PDF-05），不满足原30篇设计方案的≥3 evidence_id统计效力预期，已在文档中诚实标注。**
6. ✅ 已完成：Step 7 FRDI计算（探索性指数部分）。依据 `01_跨文献LLM综合/synthesis_v1.json` 的3个候选方向，按冻结的ESI/TGM/LCI量表与公式（见 `06_跨文献综合与FRDI/02_FRDI计算/frdi_v1.md` + `step7_compute_frdi.py` + `frdi_results_v1.json`）完成计算。**核心稳健性结论：候选方向3-1（第3章）在全部6个测试场景（3种权重方案×2种出版年基准）中排序均为最低，是唯一稳健的排序结论；候选方向4-1（第4章）与5-1（第5章）的相对排序对权重/年份假设高度敏感（6场景中4-1领先5场景，但在主权重方案+印刷年份基准下5-1反而微弱领先0.560 vs 0.544），报告明确不对二者做结论性优先级判断。** 强制重复声明：FRDI为本受限5篇语料内的探索性候选方向优先级指数，非已验证、可跨领域比较的前沿指数。
7. ✅ 已完成：Step 7 图表与章节输出部分（阶段07）。`07_图表与章节输出/01_图表_2-1至2-4/`（`step7_generate_figures.py` + 图2.1 D01-D10标签覆盖矩阵、图2.2 研究范式簇示意图、图2.3 FRDI跨6场景稳健性柱状图、图2.4 候选方向成就等级vs出版年份散点图，均已验证中文字体正常渲染）；`07_图表与章节输出/02_表格/`（`step7_generate_tables.py` + `chapter2_tables_v1.xlsx`，含表2.1 D01-D10标签矩阵、表2.2 Step5评估指标、表2.3 FRDI结果三个工作表，均附带强制披露文字）。至此 P0→P1→P2/Step3→Step4→Step5→Step6→Step7 全部阶段按 `P1_frozen_pipeline_config_v1_LOCKED.md` 锁定的单一pipeline执行完毕。
8. 后续可选工作（非本pipeline强制项）：①第3-5章正式章节稿撰写（`03_章节稿件/`尚为空，可基于 `06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.md` 直接改写）；②若计划扩大到30篇确认性语料，需按 `P1_frozen_pipeline_config_v1_LOCKED.md` 第3节变更规则重新评估所有锁定参数，不得静默套用5篇语料的全量审核/无消融等假设；③安排真正的领域专家人工盲审（见 `05_人工金标准与方法评估/01_人工金标准审核/agent_assisted_audit_v1.md` 第4节）。
9. ✅ 已完成：**schema v1.1 修订**（按用户在Step7解读后选定的优先级执行）。按 `P1_frozen_pipeline_config_v1_LOCKED.md` 第3节变更控制流程（记录缺陷→新版本号→变更日志→不回溯覆盖旧记录）修复了Step5/6发现的2处真实缺陷：①D03新增标签 `Topological_Dependency_Equation`，解决B001-PDF-03图论拓扑依赖方程无法被原6类标签描述的问题；②D05/D06编码手册新增"关键词陷阱/反例"判例（"steady-state"误判案例、"proactive"正确规避案例），不改变标签集本身。完整记录见 `04_LLM抽取与Critic审查/01_Prompt与Schema注册/schema_v1.1_revision_proposal.md`；`schema_v2.json`已更新为v1.1并保留`version_history`，原v1.0完整快照保存于新建的`schema_v1.0_frozen_snapshot.json`；`schema_v2_D01-D10_codebook.md`已更新并含变更日志。**全部50条v1.0正式核验记录保持不变，未被回溯覆盖**（已程序化验证：v1.1标签集下50/50条记录仍合法）；新增演示性重分类文件 `B001-PDF-03_D03_v1.1_reclassification_demo.json` 验证新标签确实解决了原缺陷，但明确标注为方法验证用途、不替代正式核验结果。

10. ✅ 已完成，接口已就绪并**完成真实连通性验证**：**Step 4 批量外部API抽取接口**（按用户决策"当前智能体抽取并不能完成后续批量工作，后续批量工作需要使用API进行，接口应从03开始"新增，后续用户明确指定实际使用**中国科技云（CSTCloud）Uni-API**，文档 <https://uni-api.cstcloud.cn/doc/llm/>，并提供了真实token）。新目录 `04_LLM抽取与Critic审查/API批量管线/`：`llm_api_client.py` 提供 provider-agnostic 外部LLM客户端，内置专门的 `cstcloud` 适配器（base_url `https://uni-api.cstcloud.cn/v1`、`Authorization: Bearer {Token}`鉴权、剥离推理模型的非标准`reasoning_content`字段、支持`chat_template_kwargs`深度思考开关），以及通用的 `openai_compatible`/`anthropic`/`dry_run` 三种适配器；`step4_api_batch_extraction.py` 复用 Stage 03 已冻结的 `HybridIndex`（coverage pass全文覆盖 + hybrid_search维度检索，严格遵守已锁定的"coverage pass强制、Top-k不可替代"规则），驱动与会话内版本完全相同的冻结 Agent A/B prompt 与四轮协议，新增 `--list-models` 命令。**已用用户提供的真实CSTCloud token做了真实网络验证**（一次性、小规模，非完整批量跑）：①`GET /v1/models`成功取回实时模型目录，发现与文档文字示例不完全一致（`deepseek-v3:671b`/`qwen3:235b`等文档例子在该账号实际目录中不存在）；②对`deepseek-v4-flash`做了真实`chat/completions`往返，确认真实usage/延迟/model_version字段均被正确解析；③对`qwen3.5`/`gpt-oss-120b`/`minimax-m27`做了"仅输出JSON"真实指令遵从度测试，发现`minimax-m27`会把思维链以字面`<think>...</think>`文本内嵌在`content`里（不同于deepseek走独立`reasoning_content`字段的方式），已据此修复`extract_json()`解析逻辑并用该模型真实返回文本验证通过；`.env.example`默认配置已更新为实测验证过的`deepseek-v4-flash`(Agent A) + `qwen3.5`(Agent B)组合（不同模型家族，`cross_model_independence: true`），是本项目首次具备满足"Agent B不读取Agent A推理过程、双方互相独立"要求的技术路径。验证用token仅作为一次性环境变量使用，**未写入工作区任何文件**；所有输出写入独立的`API批量管线/产出/`子目录，已重新验证不触碰、不覆盖既有50条v1.0核验记录或原manifest。**尚未执行过完整的`--doc-ids`/`--all`批量正式运行**，真正批量使用前仍需用户自己的token跑一次pilot确认D01-D10完整抽取质量。**已提醒用户：按CSTCloud文档要求，使用该服务产出的研究成果在论文/专著/专利/奖励申请中需在致谢部分注明CSTCloud支持。**旧版 API 操作说明已按工作空间整理请求移除；当前 v1.2 本地文本范围分支说明见该目录下 `README_LOCAL_v1.2_text_scope.md`。

## 设计验证结论摘要

原实验设计的研究思路基本合理：全文证据、coverage pass、混合检索、独立 Critic、人工复核和模型调用审计均值得保留。但原方案以30篇为目标，目前实际原始语料是5篇；如后续开展确认性研究，需要先明确最终语料规模与筛选规则，并补齐 D01–D10 Schema、pilot/测试集隔离、RAG 参数与公平对照、样本量和统计计划，以及 FRDI 的可复算定义与效度验证。

**学术规范边界：**PRISMA 适用于系统综述报告；LLM/RAG 可复现性应记录模型、prompt、检索快照和中间轨迹；人工评估需报告标注准则与一致性；AI 使用披露应遵循目标期刊政策。相关依据和完整审查意见见下方整合的历史评估报告。

---

## 整合文档

以下内容整合自原 `00_研究设计与配置/` 中的三份 Markdown 和原 RAG 工作流阶段 README。为便于在单一文件中阅读，原文标题层级统一下移一级。原设计中的“30篇”样本、批次和旧目录编号均为历史方案记录；当前语料与目录以本 README 前文的最新状态为准。

> 注：下列实验设计/验证材料保留原文细节以供追溯，其中关于30篇全量语料、旧批次与旧运行路径的表述属于历史方案；当前工作区仅保留本轮指定的5篇原始 PDF，并已完成 Step 1 Zone A–D 切片和 Step 2 细粒度分块。索引、检索及 RAG/LLM 尚未运行。



### 章节大纲（原文件内容）

## 第2章 基于大语言模型全文证据挖掘的水-电耦合系统前沿研究方向识别

> v2 说明：本版本将 Step 2 和 Step 3 重新设计为真正调用大语言模型的可审计流程。旧版规则化结果已从当前工作目录清理；仅受保护的 benchmark 历史结果保存在 `/home/user/_protected_benchmark_archive/`。

### 2.1 研究问题与全文证据单元

#### 2.1.1 研究问题

- RQ1：现有水-电耦合研究如何表征水-电耦合方向、厂内冷却水和核心耦合方程？
- RQ2：现有研究是否利用信息层快感知与水-热-水力慢演化之间的时间尺度差进行早期预警和主动控制？
- RQ3：级联故障后果是否从物理网络服务损失延伸到人口、关键民生设施、社会脆弱性和 Shelby County 人类影响？
- RQ4：作者在全文结尾明确承认的模型局限和未来方向，是否能支持第 3–5 章的研究空白识别？

#### 2.1.2 分析单元

本章不以摘要或关键词作为主要分析单元，而以以下三类全文证据作为基本单元：

1. 文献级单元：一篇论文的完整四区切片；
2. 章节级单元：方法、模型、仿真、案例、讨论和局限性章节；
3. 证据级单元：一个可回溯到 section、page 和原文字符区间的句子、公式、表格说明或算法步骤。

### 2.2 PDF 全文解析与可复现证据语料库

#### 2.2.1 Step 1：PDF 版面解析

Step 1 继续使用 PyMuPDF 读取 PDF 文本块、坐标、字体和页码，构建章节树及 Zone A–D 四区切片。Step 1 输出必须为稳定的 evidence-ready 语料格式，而不仅是可读文本：

```json
{
  "evidence_id": "B002-PDF-02-S02-P02-E0007",
  "doc_id": "B002-PDF-02",
  "section_id": "2.2",
  "section_title": "Cascading model",
  "page": 2,
  "zone": "Zone_B",
  "text": "...",
  "char_start": 1820,
  "char_end": 2076
}
```

#### 2.2.2 全文证据边界

- Zone A：标题、摘要和 Introduction 末段，仅用于研究对象、贡献和范围识别；
- Zone B：系统架构、问题定义、耦合机制、核心方程和级联模型；
- Zone C：指标、仿真控制、预警、缓解、恢复和优化；
- Zone D：案例、社会/人类影响、讨论、局限和未来研究；
- References、Acknowledgments、作者简介和纯综述段落不作为本文方法证据；
- 如果全文切片缺少公式图像、表格图像或原始版面信息，必须标记 `evidence_unavailable`，不能由模型补写。

#### 2.2.3 Zone、证据块与完整 RAG 层

- Zone A–D 是语义/分析分区，不是 token 分片；
- evidence block 是可回溯的段落、公式、算法、表格或图注；
- context window 是模型调用的技术装载单位，不产生新的语义 Zone；
- 完整 RAG 必须包含 evidence indexing、embedding、BM25/向量混合检索、上下文组装、生成、引用核验和 retrieval manifest；
- Agent A 同时执行全文 coverage pass 和 D01–D10 维度 retrieval pass，避免 Top-k 检索造成全文漏召回。

### 2.3 Step 2：真正的双大语言模型智能体十维知识抽取

#### 2.3.1 Agent A：Full-Text Ontology Extractor

Agent A 接收单篇论文的 Zone A–D 全文切片和十维 Schema，逐维输出：

- 受控标签；
- 机制性判断；
- 不确定性说明；
- 至少一条正文证据；
- 章节号、页码、evidence_id 和原文字符区间；
- 涉及公式时记录公式编号、变量、物理含义和公式所在页码。

严格规则：

- 没有正文证据时只能输出 `Not_Stated_In_Text`；
- 不得仅凭标题、摘要、关键词推断 D02–D09；
- 不得把引用文献的方法误认作当前论文的方法；
- 不得把 HLA/软件数据交换自动解释为真实 cyber 早期预警；
- 不得把一般水网压力方程自动解释为厂内冷却热-水力模型。

#### 2.3.2 Agent B：Independent Critic and Evidence Auditor

Agent B 独立读取原始四区切片和 Agent A 输出，不能读取 Agent A 的推理过程。对每一条维度记录执行：

1. **Entailment check**：原文是否支持该标签和机理判断；
2. **Direction check**：水→电、电→水或双向关系是否被正确识别；
3. **Equation check**：是否真的存在所声称的方程、变量和动态过程；
4. **Temporal check**：时间步长、仿真推进和控制触发条件是否被准确表述；
5. **Endpoint check**：物理、经济、人类/社会后果是否被混淆；
6. **Evidence check**：section、page、evidence_id 和 verbatim quote 是否精确对应；
7. **Contradiction check**：文中是否存在反向或限制性证据。

Agent B 必须输出：

```json
{
  "decision": "accept | revise | reject | insufficient_evidence",
  "corrected_label": "...",
  "critic_comment": "...",
  "supporting_evidence_ids": ["..."],
  "contradicting_evidence_ids": ["..."],
  "confidence": 0.0
}
```

#### 2.3.3 双智能体迭代协议

采用以下可审计循环：

```text
Step 1 retained full-text slices
        ↓
Agent A 初次十维抽取
        ↓
Agent B 独立 Critic 审查
        ↓
Agent A 根据 Critic 修订
        ↓
Agent B 最终复核
        ↓
verified_10d_record
```

若 Agent A 与 Agent B 仍存在分歧，不强行投票，保留：

```text
adjudication_required = true
```

并进入人工复核清单。

#### 2.3.4 模型调用审计

每次大语言模型调用必须写入 `model_call_manifest.csv`：

- agent_name；
- provider；
- model_name；
- model_version；
- endpoint；
- prompt_version；
- input_hash；
- output_hash；
- temperature；
- seed（若可用）；
- input/output tokens；
- retry 次数；
- 调用时间；
- 失败原因。

本章节不预先虚构具体模型名称。实际运行前必须锁定 Agent A 和 Agent B 的可用长上下文模型，并在 manifest 中记录；在没有模型调用日志前，不得称为“LLM 已完成抽取”。

### 2.4 Step 3：基于已核验 LLM 记录的语义综合与前沿识别

#### 2.4.1 LLM 语义综合 Agent

Step 3 不再用人工 `PROFILES`、关键词命中或固定模板直接生成研究结论。将通过 Agent B 的 Corpus Synthesis 模式，对已通过 Step 2 的 300 条十维记录进行跨文献综合，输出：

- 研究范式簇；
- 每个簇的共同机制；
- 代表性证据和反例证据；
- 研究空白陈述；
- 空白对应的第 3、4、5 章；
- 候选前沿方向的边界条件和不可外推范围。

所有候选方向必须绑定至少 3 个 `evidence_id`，并同时列出反向证据或未充分证据。

#### 2.4.2 数值化 FRDI

FRDI 保留透明的数值计算，但数值输入必须来自已核验 LLM 记录，而不是人工硬编码标签：

\[
FRDI_k = \omega_1 ESI_k + \omega_2 TGM_k + \omega_3 LCI_k
\]

其中：

- `ESI`：基于已核验标签和证据覆盖率计算的领域稀缺度；
- `TGM`：按出版年份和证据支持的方向演化计算的时间动量；
- `LCI`：由 Agent B 对作者明确局限性与候选研究方向的证据关联进行 0–3 级评分，再由 Python 固定公式聚合；
- 权重、归一化方式和缺失值处理在执行前冻结，不允许根据结果反向调参。

Python 仅负责可重复的统计计算、置信区间、敏感性分析和制图；不负责替代大语言模型完成语义判断。

#### 2.4.3 可选语义聚类

UMAP/HDBSCAN 仅作为辅助稳健性分析，不作为主要知识抽取方法：

- 输入：Agent A/B 已核验的机制摘要和局限性摘要；
- 嵌入模型、版本和距离度量必须记录；
- 聚类标签必须由 Agent B 根据簇内 evidence_id 重新解释；
- 不能把无监督簇直接命名为研究方向而不提供正文证据。

### 2.5 方法有效性与人工复核

#### 2.5.1 Pilot gate

先用两个受控 benchmark PDF 执行真实 LLM 双智能体流程。只有满足以下条件，才能扩展到 30 篇：

- 20 个维度记录均有有效 evidence_id；
- 原文证据可由程序精确回溯；
- Agent A/B 对关键标签的最终一致率达到预设阈值；
- D02、D04、D05、D06、D08 等关键难点由领域专家人工抽查；
- 所有模型调用均有 manifest 和 prompt 版本记录。

#### 2.5.2 人工金标准抽查

从 30 篇中分层抽取至少 5 篇、50 条维度记录，由领域研究者盲审：

- 标签准确率；
- 证据充分率；
- 页码/章节回溯准确率；
- 误把引用方法归为本文方法的比例；
- D02 厂内冷却识别的精确率；
- D08 人类与社会影响识别的精确率。

#### 2.5.3 结果表述边界

`accept` 只表示证据支持该判断，不表示论文结论本身正确；`insufficient_evidence` 不得被改写为 `Not_Considered`；规则化 quote-match 只能验证溯源，不能替代语义 Critic。

### 2.6 30 篇语料执行顺序与输出

1. 保留 Step 1，不重复 PDF 版面切片；
2. 重新锁定 Agent A/B 模型、提示词、Schema 和 manifest；
3. 先对两个 benchmark PDF 进行真实 LLM pilot；
4. 通过 pilot gate 后处理 Batch 001–003 的 30 篇；
5. 以 verified records 执行 Step 3 LLM 语义综合和 FRDI；
6. 重新生成第 2.1–2.4 节图表。

推荐输出目录：

```text
02_llm_pdf_mining_pipeline/v2_llm_execution/
├── 01_Prompt与Schema注册/
├── 02_模型调用日志/ (model_call_manifest.csv)
├── 03_AgentA原始抽取/
├── 04_AgentB_Critic审查/
├── 05_核验通过结果/
├── 01_跨文献LLM综合/
├── human_audit/
└── 01_图表_2-1至2-4/
```

旧规则化结果已从第2章活动目录清理；两篇受控 benchmark 的历史结果仅保存在 `/home/user/_protected_benchmark_archive/`，不得与 v2 真实 LLM 结果混用。


### 实验设计与完整工作框架（原文件内容）

## 第2章实验设计与完整工作框架 v2

### 1. 实验启动原则

在任何新的大语言模型、Embedding 模型或向量索引调用之前，先完成：

1. 实验设计冻结；
2. 数据与证据索引审计；
3. Agent A/B Schema 和 prompt 冻结；
4. 模型 provider、model、version 锁定；
5. benchmark 金标准建立；
6. pilot gate 通过。

当前状态：Step 1 已完成；v2 实验框架已设计；真实 LLM/RAG/Embedding 调用尚未开始。

### 2. 实验总目标

验证以下方法是否能够比“PDF 四区切片后直接输入大语言模型”更准确、可回溯、可复现地完成全文知识抽取：

```text
全文覆盖约束下的混合 RAG
+ Agent A 全文十维抽取
+ Agent B 独立 Critic
```

最终服务于三个博士论文研究方向：

- 第 3 章：厂内冷却水—热—水力—电力显式建模；
- 第 4 章：快速 cyber 感知/决策与慢速热-水力演化之间的跨系统早期预警和主动控制；
- 第 5 章：Shelby County 水-电级联对人口、关键设施和社会脆弱性的影响量化。

### 3. 实验问题与假设

#### RQ-E1：RAG 是否提高全文证据召回率？

比较直接长上下文输入与全文覆盖约束下的混合 RAG，考察：

- 公式证据召回；
- 时间步长证据召回；
- 局限性证据召回；
- 人类/社会影响证据召回。

**H1：**全文覆盖约束下的混合 RAG 具有更高的 evidence recall@k 和 section coverage，尤其是在长 Zone B/D 文本中。

#### RQ-E2：独立 Critic 是否降低无证据判断？

比较 Agent A 单独输出与 Agent A + Agent B 独立复核。

**H2：**独立 Critic 能降低 unsupported-claim rate，提高标签准确率、引用精确率和反向证据发现率。

#### RQ-E3：混合检索是否优于单一检索？

比较：

- dense-only；
- BM25/关键词-only；
- dense + BM25 hybrid。

**H3：**混合检索在公式、变量、专业缩写和语义表达并存的论文中具有更稳定的召回率。

#### RQ-E4：完整全文覆盖是否优于 Top-k-only RAG？

比较只输入 Top-k 检索结果与“全文 coverage pass + 维度 retrieval pass”。

**H4：**coverage pass 能降低没有明显关键词的方程、反向证据和 Discussion/Conclusion 局限性遗漏。

#### RQ-E5：方法效果是否受上下文窗口大小影响？

比较 800、1,200、1,800 token 三种 context window 设置。

**H5：**过短窗口会造成证据上下文不完整，过长窗口会造成注意力稀释；中等窗口具有更好的证据准确率/成本平衡。

### 4. 实验对象与数据划分

#### 4.1 总体语料

- 30 篇论文；
- Batch 001、Batch 002、Batch 003 各 10 篇；
- 使用已保留的 Step 1 章节树和 Zone A–D 全文切片；
- 不使用摘要/关键词 Mode A；
- 不恢复原始 PDF，除非需要核验未保留的图像公式或原始版式。

#### 4.2 三层实验数据集

| 数据集 | 样本 | 用途 |
|---|---:|---|
| Pilot-Benchmark | 2 篇受控 benchmark | 验证 RAG、双智能体、证据链和 JSON Schema |
| Gold-Audit | 5 篇、至少 50 条维度记录 | 建立人工金标准，比较方法准确率 |
| Full-Corpus | 30 篇、300 条十维记录 | 最终 Step 2、Step 3 和 FRDI |

#### 4.3 Gold-Audit 选择原则

5 篇人工审查文献应覆盖：

- 有明确水→电冷却关系的文献；
- 只有水压/功能阈值黑箱的文献；
- HLA/联合仿真文献；
- 含真实城市或 Shelby County 算例的文献；
- 含人口、社区或社会影响内容的文献。

每条人工金标准记录由两名审查者独立标注，冲突由第三次仲裁或共同讨论解决。

### 5. 对照实验矩阵

#### 5.1 主实验组

| 组别 | 全文覆盖 | 检索 | Agent A | Agent B Critic | 目的 |
|---|---|---|---|---|---|
| G0 | 否 | 无 | 有 | 无 | 直接长上下文 baseline |
| G1 | 否 | dense-only Top-k | 有 | 无 | 单一向量检索 |
| G2 | 否 | BM25-only Top-k | 有 | 无 | 单一词法检索 |
| G3 | 否 | dense + BM25 | 有 | 无 | 混合检索但无覆盖保证 |
| G4 | 是 | dense + BM25 | 有 | 无 | 全文覆盖 RAG |
| G5 | 是 | dense + BM25 | 有 | 有 | **最终推荐方法** |

G5 是第 2 章的目标方法；G0–G4 是方法对照和消融实验，不是最终生产流程。

#### 5.2 上下文窗口消融

在 G5 上比较：

```text
W800   = 800 token 左右
W1200  = 1,200 token 左右
W1800  = 1,800 token 上限
```

保持以下变量不变：

- 模型；
- prompt；
- evidence index；
- retrieval query；
- top-k；
- 人工金标准。

#### 5.3 Critic 消融

```text
A-only       = Agent A直接输出
A+B          = Agent A + Agent B一次Critic
A+B+A+B      = Agent A初次抽取 → B Critic → A修订 → B最终复核
```

最终方法采用 `A+B+A+B`。

### 6. 完整工作框架

```text
┌───────────────────────────────────────────────┐
│ M0 配置与版本冻结                              │
│ Schema / prompts / models / parameters / seed  │
└───────────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────┐
│ M1 全文证据层                                  │
│ Step1 Zone A–D → evidence blocks               │
│ page / section / char range / evidence_id      │
└───────────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────┐
│ M2 RAG索引层                                   │
│ embedding index + BM25 index + metadata        │
│ context_window_manifest + retrieval_manifest   │
└───────────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────┐
│ M3 双LLM抽取层                                 │
│ Agent A → Agent B Critic → A revision → B final│
└───────────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────┐
│ M4 评估层                                      │
│ Gold labels / evidence metrics / cost / logs   │
└───────────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────┐
│ M5 语料综合层                                  │
│ Corpus RAG → research clusters → gaps          │
└───────────────────────────────────────────────┘
                      ↓
┌───────────────────────────────────────────────┐
│ M6 定量与输出层                                │
│ ESI / TGM / LCI / FRDI / 图2.1–2.4             │
└───────────────────────────────────────────────┘
```

### 7. 各模块输入、处理和输出

#### M0：配置与版本冻结

**输入：**研究问题、十维 Schema、模型候选、RAG 参数。

**输出：**

- `schema_v2.json`；
- `01_Prompt与Schema注册/`；
- `model_config.yaml`；
- `experiment_matrix.csv`；
- `run_id`。

#### M1：全文证据层

**输入：**30 篇已保留 Step 1 JSON。

**处理：**

- 证据块识别；
- 公式/算法/表格 block 标记；
- 字符区间定位；
- 版本化文本哈希。

**输出：**

- `evidence_index.jsonl`；
- `evidence_blocks.parquet` 或等价结构化文件；
- `evidence_quality_report.md`。

#### M2：RAG 索引层

**输入：**evidence blocks。

**处理：**

- embedding；
- BM25/词法索引；
- doc/zone/section metadata filter；
- dense + sparse hybrid retrieval；
- 邻接证据补充；
- 检索去重和排序。

**输出：**

- `01_稠密向量索引/`；
- `02_BM25词法索引/`；
- `03_检索运行清单/retrieval_manifest.jsonl`；
- `04_上下文窗口清单/context_window_manifest.jsonl`。

#### M3：双 LLM 抽取层

**Agent A 输出：**

- `03_AgentA原始抽取/*.json`。

**Agent B 输出：**

- `04_AgentB_Critic审查/*.json`。

**最终输出：**

- `05_核验通过结果/*.json`；
- `adjudication_queue.jsonl`。

#### M4：评估层

输出：

- `evaluation_metrics.csv`；
- `gold_audit.xlsx`；
- `error_analysis.md`；
- `cost_latency_report.csv`。

#### M5：语料综合层

只使用 `05_核验通过结果`，不使用未经核验的 Agent A 原始结果。

输出：

- 研究范式簇；
- 研究空白；
- 反例和边界条件；
- 第 3–5 章映射；
- `01_跨文献LLM综合/*.json`。

#### M6：定量与图表层

Python 只负责：

- 固定公式；
- ESI/TGM/LCI/FRDI；
- 置信区间和敏感性分析；
- 图 2.1–2.4；
- 第 2 章报告表格。

### 8. 评价指标

#### 8.1 检索指标

- `evidence recall@k`；
- `citation precision`；
- `section coverage`；
- `page coverage`；
- `contradiction recall`；
- 未检索目标 section 比例。

#### 8.2 知识抽取指标

- 标签 accuracy / macro-F1；
- 证据充分率；
- 公式变量准确率；
- 时间尺度识别准确率；
- D02 厂内冷却识别准确率；
- D05/D06 预警控制识别准确率；
- D08 社会影响识别准确率。

#### 8.3 生成与审查指标

- unsupported-claim rate；
- quote exact-match rate；
- page/section accuracy；
- Agent A/B agreement；
- Critic correction rate；
- unresolved adjudication rate。

#### 8.4 工程指标

- 输入/输出 token；
- 单篇成本；
- 单篇延迟；
- 重试次数；
- 检索和模型失败率；
- 可重复运行一致率。

### 9. Pilot Gate

正式处理 30 篇前必须满足：

1. 两篇 benchmark 完成 G0–G5 对照；
2. Gold-Audit 至少 50 条维度记录完成双人标注；
3. G5 相比 G0 在证据召回和引用精确率上达到预设改善；
4. Agent B 能识别至少一类 Agent A 的错误或遗漏；
5. 所有检索、模型和输出日志完整；
6. 未解决的公式图像或版面证据被明确标记为 `evidence_unavailable`；
7. 研究者确认后才进入 30 篇全量运行。

### 10. 最终科学产出

本章最终不只输出一个分数，而要输出：

- 30 篇论文的十维 verified evidence matrix；
- RAG 检索和双 LLM 核验性能比较；
- 现有研究方法范式簇；
- 三类证据化研究空白；
- FRDI 排名及敏感性分析；
- 图 2.1–2.4；
- 第 3、4、5 章的研究问题、模型边界和数据需求。


### 实验设计验证评估（原报告内容）

## 第2章实验设计验证评估

**审查日期：**2026-10-05  
**审查对象：**
1. `第2章_实验设计与完整工作框架_v2.md`
2. `第2章_大语言模型文本挖掘与前沿方向识别_章节大纲_v2_真实LLM双智能体.md`

### 一、结论摘要

**结论：研究方向合理，设计理念与当前学术界对全文证据可追溯、RAG 分模块评估、LLM 调用审计和人工复核的要求大体一致；但目前仍是“概念框架”，尚未达到可直接开展确认性比较、或据此宣称方法优越性的实验协议成熟度。**

建议**有条件通过方案设计，不通过全量实验启动**：可以在补齐下文 P0 项后做小规模工程试运行；在明确验证集、标注、指标和统计方案前，不应将两篇 pilot 的结果当成有统计效力的证据，也不宜直接启动 30 篇全量 LLM 调用并报告“RAG/双智能体有效”。

| 维度 | 判断 | 主要原因 |
|---|---|---|
| 研究问题与技术路线 | 基本合理 | 全文切片、coverage pass、混合检索、独立 Critic、可追溯证据链，针对了摘要漏掉公式、时间尺度和局限等问题。 |
| 语料与构念效度 | 未通过冻结 | 30 篇的检索/筛选依据未在设计中说明；D01–D10 的正式操作定义与标注手册未随 00 文件提供。 |
| RAG 对照与可比性 | 方向合理、细节不足 | 对照组较齐，但 chunking、top-k、融合、token 预算及主要对比尚未固定；G0 与 RAG 组可能不等量。 |
| 人工验证与统计推断 | 需重大补充 | 50 条人工标注和2篇 pilot 没有样本量/精度依据；缺少 IAA 指标、主要终点、最小效应和统计检验。 |
| 可复现性 | 原则良好、落地未完成 | 已计划模型调用 manifest、prompt 版本和检索 manifest；但还需索引快照、逐次中间轨迹、重复运行与统计配置。 |
| FRDI 前沿指数 | 可作为探索工具，暂不能视为已验证指标 | ESI/TGM/LCI 尚无可复算定义、效度依据、专家一致性或外部验证结果。 |

### 二、设计中值得保留的优点

1. **全文而非摘要作为证据基础，符合研究问题。** 研究问题涉及厂内冷却水、耦合方程、动态时间尺度、人类/社会后果和作者局限，仅靠摘要或关键词很难稳定识别。
2. **正确区分 Zone、evidence block 与模型上下文。** 方案明确 Zone A–D 是分析区域，不是 token chunk；并要求证据能够回溯到 section、page、evidence ID 和字符区间。这是很好的数据治理原则。
3. **Coverage pass 与 dimension retrieval pass 有合理动机。** 对长论文只做 Top-k 容易漏掉不含显著关键词的反例、方程和结论局限；“全文覆盖 + 维度定向检索”值得作为待检验的方法因素。
4. **对照因素基本可拆解。** G1/G2/G3 可比较 dense、BM25 与 hybrid；G3/G4 可比较 coverage；G4/G5 可比较 Critic 增益。前提是其他因素和上下文预算受到控制。
5. **模型输出不是金标准，且设置了人工复核。** 方案要求双人盲审、冲突处理，并明确 `accept` 只表示原文支持该标签，不等于原论文结论为真；也区分 `insufficient_evidence` 与 `Not_Stated_In_Text`。
6. **重视可审计性。** 计划记录模型、prompt、参数、输入/输出哈希、token、重试和失败原因，并禁止在没有调用日志时声称 LLM 已完成分析，这些应保留并落实。

### 三、启动前必须补齐的关键问题（P0）

#### P0-1：把“30 篇语料”变成可复现、边界清楚的数据集

现有设计给出了篇数和 batch，却没有交代这30篇如何从更大文献集合中取得：数据库/信息源、完整检索式、检索日期与时间范围、纳入/排除标准、筛选流程、重复记录处理、排除理由及语料截止日期。若章节要作系统性或范围性文献综述式的领域结论，应按 PRISMA 2020 报告研究识别、筛选和综合；搜索过程可参考 PRISMA-S 的检索来源、逐库检索式和可复现记录要求。若这不是系统综述而是目的性选取的计算语料，也应明确称为“目的性/受限语料”，说明选择理由和外推边界，不能写成覆盖整个领域的无偏代表样本。PRISMA 是报告规范，不意味着所有计算语料研究都必须被包装成系统综述。

**需新增：**语料构建协议、检索/筛选日志、纳入论文列表、语料截止日、研究年份定义（online-first 年份与期刊卷期年份的处理规则）。另外，截至本次更新，当前文献库已收录本轮指定的5篇原始 PDF；原计划30篇中的另外25篇 PDF 尚不在工作区。旧 manifest 已按用户要求移除。若后续仍按30篇方案开展，需先依法/实际取得其余 PDF，才能全面核对公式图像、页码和原始版面；不可核验项应记录为 `evidence_unavailable`。

#### P0-2：冻结 D01–D10 操作定义和标注手册

两份 00 文件多次引用 D01–D10、十维 Schema 和 `schema_v2.json`，但原 00 文件夹中未见该 Schema 文件（现已将设计说明合并到本 README）。没有代码本，标签准确率、macro-F1、Agent A/B agreement、D02 厂内冷却精确率等均无法重复计算。

每个维度至少需要：构念定义、互斥/可并存标签、正例/反例、纳入/排除规则、原文证据要求、可接受的证据类型、论文自身方法与被引方法的区分、缺失/不确定标签、边界案例及与博士论文 RQ1–RQ4 的映射。应重点操作化“未陈述”“未考虑”“证据不足”“证据无法获取”等不同状态，避免把没有检索到等同于不存在。

#### P0-3：分开工程 pilot、prompt 开发集与确认性测试集

实验框架将2篇 Pilot-Benchmark、5篇 Gold-Audit、30篇 Full-Corpus 并列，但未说明它们是否互斥。Batch 001 manifest 中有两篇标注为既有 pilot 的复用文献；需核实是否就是 Pilot-Benchmark。若同一篇论文既用于调 prompt/阈值，又用于证明 G5 优于 G0，就存在开发—测试污染。建议：

- 2篇 pilot 只用于排查解析、JSON、日志和工作流故障；
- pilot 文献可进入最终领域综合语料，但不得再作为独立确认性测试证据；
- 另行锁定、不参与 prompt 开发的测试样本；或明确全语料比较属于探索性结果。

5篇/50条可用于代码本试标和错误类型发现，但设计目前没有说明它足以检验多少效应。它不能仅凭“至少50”自动成为可靠的确认性样本。应按预期差异、标签阳性率、文献内相关性和所需置信区间/检验功效确定样本量；至少分层覆盖10个维度、批次和难例类别。

#### P0-4：明确主要终点、指标公式和统计方案

现有列表方向正确，但指标名不是可执行的计算规范。例如：`evidence recall@k` 的 gold evidence 如何建立、一个证据跨多个 chunk 如何计数、`section coverage` 的分母是什么、`citation precision` 按 claim 还是按引用计分、unsupported-claim rate 如何定义，都需要冻结。

建议在任何模型调用前预注册或版本冻结：

- 每个 RQ 的一个主要终点和有限的次要终点；
- G4 vs G3（coverage）、G3 vs G1/G2（hybrid）、G5 vs G4（Critic）等主要对比及实际有意义的最小改善阈值；
- 95% CI、效应量、显著性水平、多重比较校正和失败/缺失值处理；
- prompt 开发、验证和最终测试的分区；不得只报告多轮试验中的最佳 prompt/运行。

`30篇 × 10维 = 300条记录` 不等于300个独立样本：同一篇文献中的维度记录相关。比较时应对同一 `doc × dimension` 做配对，并在推断中按文献聚类（例如文献级 paired bootstrap/随机化检验或合适的混合效应模型）；不能把300条简单当作独立观测。建议同时报告每篇文献及每个维度的结果，避免总体均值掩盖稀有关键标签。

#### P0-5：把 RAG 与双智能体对照做成公平、可复算的条件

在 G0–G5 中固定或明确：同一基础模型及快照、prompt、语料版本、Schema、temperature/采样设置、证据切片、tokenizer、最大上下文预算和输出格式。对每种检索至少定义：证据块粒度/重叠、embedding 模型及版本、BM25 分词器与参数、top-k、融合方法（例如 RRF 或固定权重）、是否 rerank、metadata filter、邻块扩展、去重规则、各 D01–D10 的查询模板。

尤其需要处理两点：

- **G0 公平性：**完整长上下文可能比 RAG 组多输入数倍 token；若要比较准确率，应做等 token 预算对照，或另列“各方法实际可用的最佳配置”，并同时报告质量—token/成本/延迟曲线。
- **G5 定义：**主矩阵的“Agent B Critic”应明确是单次 A+B，还是最终协议 A→B→A→B。若最终方法是迭代版，就应将 G5 定义为迭代版，并单独列出 A+B 一轮消融；否则质量和调用成本都无法归因。

`W800/W1200/W1800` 更像“每个 doc-dimension query 的检索上下文 token budget”，不是基础模型的 context window。需明确 token 的 tokenizer、预算作用范围、超长证据的截断/邻接扩展规则和三个预算的先验依据。否则 H5 同时改变了窗口长度和被选到的证据，不能将差异解释为单纯的注意力稀释效应。

#### P0-6：把人类标注和两智能体核验分开评价

Agent B 是有价值的审查组件，但 Agent A/B 的一致率不等于准确率；二者可能共享模型偏差。应以独立人工证据标签作为性能参照，并由领域研究者核验原文跨度。对两名标注者，报告原始一致率及适合标签尺度的机会校正系数（如 nominal 标签的 Cohen’s κ；有缺失或不同标注数时可用 Krippendorff’s α），同时报告不确定性区间、按维度的混淆/分歧和仲裁规则。应提供标注者专业背景、试标/培训、完整指导语、盲法、抽样方式、仲裁流程；必要时说明伦理审查/豁免和利益冲突。

LLM-as-judge 可作为补充而非唯一评估。ARES 分别考察 context relevance、answer faithfulness、answer relevance，并用少量人工标注校准评估；RAGAs 也强调检索上下文质量、生成对上下文的忠实性和回答质量是不同维度。对本研究的结构化证据抽取，应借鉴其“分模块评估”思路，但不能直接用通用自动评分代替人工 gold evidence。

#### P0-7：FRDI 先按“探索性指数”处理

目前 FRDI 仅有 `FRDI = ω1·ESI + ω2·TGM + ω3·LCI` 的框架式表达。正式计算前应定义 ESI/TGM/LCI 的可复算公式、观测单位、分母、年份窗口、标准化方法、零值/缺失值、权重来源和 LCI 0–3 评分锚点；并在看到排名前冻结所有规则。LCI 若依赖 Agent B/专家判断，需先验证其重复性。应做权重、时间窗口、样本纳入规则的敏感性分析，并尽可能和独立专家判断或外部文献计量趋势进行效度核验。在完成这些工作前，建议称为“本受限语料内的候选方向优先级/探索性指数”，不要称为已验证、可跨领域比较的前沿指数。

### 四、与当前报告规范的对照

- **系统/范围综述报告：**若该章声明系统性检索或代表领域研究现状，PRISMA 2020/PRISMA-S 对纳入排除、信息源、检索日期/完整检索式、筛选流程和记录数量的透明报告尤其相关；如果采用其他语料构建设计，应说明为何不适用并采用相应透明报告。
- **多阶段 LLM/RAG 可复现性：**ACL 2026 的 ReproEvalCard 针对 RAG、agent 和 prompt-chain 评估，列出 base model/解码参数、生成与评估 prompt、judge 配置、retrieval corpus/index snapshot、工具/API、逐步执行轨迹、指标聚合和随机性控制。现有调用 manifest 是良好起点，但还应保留精确 retrieval/context 快照、每轮 A/B 中间输出、prompt 迭代记录、run ID、依赖版本和重复调用策略。
- **RAG 评估：**RAGAs 与 ARES 说明检索、上下文忠实性、回答相关性是不同评估面向；本方案已有 recall、引用和 unsupported claim 等指标，但应补齐定义并按阶段分别报告。自动 judge 的分数应经过人工子集校准。
- **人类评价：**NLG 人工评估的 best-practice 文献建议预定义评估标准、使用多个标注者、报告一致性及置信区间，并区分探索性分析与确认性检验；当前设计已有双人审查想法，但缺少实施细节和统计报告方式。
- **AI 使用与出版伦理：**出版社的具体规定会因期刊而异。Springer Nature 当前政策强调人类对学术判断承担不可转移的责任，并要求透明说明实质性 AI 使用。最终稿应按目标期刊政策披露模型、用途和人工核验；同时确认全文上传到第三方 API 的版权许可、数据保留和训练使用条款。

以上规范不是一套对所有学科普遍强制的“单一标准”。PRISMA 用于系统综述报告；ReproEvalCard 是 ACL 2026 面向 LLM pipeline 的新报告框架；具体投稿仍应遵循目标期刊/会议要求。

### 五、建议的 Go/No-Go 顺序

#### Go 前（首个真实模型调用之前）

1. 冻结语料来源、检索日期、筛选标准、语料截止日和 pilot/test 划分；核实 Batch 001 两篇复用 pilot 是否与 Pilot-Benchmark 重合。
2. 发布 `schema_v2.json` 和带例子的标注手册，并把 Chapter RQ1–RQ4 与 RQ-E1–E5 的关系画清楚。
3. 明确 evidence block/evidence ID 的稳定规则、PDF 回溯测试、公式/图表不可读时的标记，以及语料/派生文本的使用权限。
4. 冻结每组模型、prompt、retrieval 参数、token budget、指标公式、主要对比、阈值和统计计划。
5. 说明两人标注抽样、指导语、IAA、仲裁、置信区间和样本量依据。

#### 通过后：分阶段运行

- 先在不进入确认性测试的 dev pilot 上验证解析、证据回溯、schema 与日志；按错误分析修改一次并冻结版本。
- 再在未参与 prompt 调整的测试样本上做预先指定的检索/抽取比较；报告全部预定系统、配对效果量、95% CI、成本/延迟和错误类型。
- 通过该方法评估后，才把锁定的 pipeline 用于30篇领域语料的 Step 2/Step 3；领域综合与方法有效性评估分别表述，不混为一个结论。

### 六、参考规范与方法文献

1. Page MJ, et al. The PRISMA 2020 statement: an updated guideline for reporting systematic reviews. *BMJ*. 2021;372:n71. [doi:10.1136/bmj.n71](https://doi.org/10.1136/bmj.n71)
2. Rethlefsen ML, et al. PRISMA-S: an extension to the PRISMA Statement for Reporting Literature Searches in Systematic Reviews. *Systematic Reviews*. 2021;10:39. [doi:10.1186/s13643-020-01542-z](https://doi.org/10.1186/s13643-020-01542-z)
3. Pattnayak P, Bhatia A. ReproEvalCard: A Reporting Standard for Reproducible Evaluation of LLM Pipelines. *ACL 2026*. [ACL Anthology](https://aclanthology.org/2026.acl-short.22/), [doi:10.18653/v1/2026.acl-short.22](https://doi.org/10.18653/v1/2026.acl-short.22)
4. Saad-Falcon J, et al. ARES: An Automated Evaluation Framework for Retrieval-Augmented Generation Systems. *NAACL 2024*. [ACL Anthology](https://aclanthology.org/2024.naacl-long.20/)
5. Es S, et al. RAGAs: Automated Evaluation of Retrieval Augmented Generation. *EACL 2024*. [ACL Anthology](https://aclanthology.org/2024.eacl-demo.16/)
6. van der Lee C, et al. Best practices for the human evaluation of automatically generated text. *INLG 2019*. [ACL Anthology PDF](https://aclanthology.org/W19-8643.pdf)
7. ACL Rolling Review. [Reviewer Guidelines](https://aclrollingreview.org/reviewerguidelines) (current guidance; check version for the applicable review cycle).
8. Smucker MD, Allan J, Carterette B. A comparison of statistical significance tests for information retrieval evaluation. *CIKM 2007*. [doi:10.1145/1321440.1321528](https://doi.org/10.1145/1321440.1321528)
9. Springer Nature. [Journal policies: Artificial intelligence and data transparency](https://link.springer.com/brands/springer/journal-policies) (publisher-level policy; target-journal rules may differ).


### 证据索引与混合检索阶段说明

## 阶段 03：证据索引与混合检索

**状态：尚未执行。** Step 2 已生成241条细粒度 evidence blocks；当前没有 embedding、BM25 索引、检索运行或上下文窗口。进入索引前，先完成 Step 2.5 人工复核并冻结 evidence-block 版本；自动 QA 通过不等于语义边界已人工核验。

### 建议流程与接续顺序

1. 对照原始 PDF 优先核查公式风险块 `B001-PDF-03-ZC-S12-3-3-C003`、`...C004` 和全部4个短块，再按5篇文献与 Zone A–D 分层抽查约10%的一般块；结果记入 `02_PDF清洗与分块/02_Chunks/chunk_manual_review.md`。如发现系统性切分问题，修订 Step 2 并重跑；不得猜补无法确认的符号。
2. 人工复核通过后冻结 `evidence_blocks.jsonl`、Step 1 输入哈希、chunker 脚本哈希和 `chunking_manifest.json`，作为本阶段索引快照的输入版本。
3. 选择 embedding 模型及版本，使用对应 tokenizer 核对实际 token 长度；当前180/240是词数设置，不等于 token 限制。检索文本用 `retrieval_text`（章节标题 + 正文），引用核验使用原始 `text` 和来源字段。
4. 分别建立 dense embedding 向量索引与 BM25 词法索引。BM25 是词项/倒排检索，**不是密集 embedding 向量化**。索引须保留 `evidence_id`、`doc_id`、`section_id`、Zone、页码等可过滤和回溯元数据，并记录模型/分词/索引配置及哈希。
5. 建立覆盖 RQ1–RQ4 与 D01–D10 的检索测试查询，先标注相关 evidence IDs，再比较 dense、BM25、混合检索的覆盖/召回与排序；记录 top-k、过滤、融合及去重参数。
6. 保存检索运行清单与上下文快照。当前块无 overlap；需要时可按明确规则加入相邻证据以恢复边界上下文，同时保留原始 evidence IDs。
7. 检索基线和上下文快照验证前，不启动下游 LLM 抽取/Critic。

### 子目录

- `01_稠密向量索引/`：向量索引、embedding 模型与配置。
- `02_BM25词法索引/`：BM25 词法/倒排索引及分词配置。
- `03_检索运行清单/`：每次检索的查询、候选证据、排序/融合结果、指标和版本记录。
- `04_上下文窗口清单/`：组装后的模型上下文、token 设置、相邻块扩展规则及证据 ID。


### 双智能体抽取与Critic阶段说明

## 阶段 04：双智能体全文抽取与 Critic 审查

**状态：待执行。** 目录按研究框架预留；当前没有真实 LLM 调用、Agent 输出或已核验记录。

### 建议运行顺序

`prompt/schema 冻结 → Agent A 全文十维抽取 → Agent B 独立证据审查 → Agent A 修订 → Agent B 最终复核 → verified records`

Agent A/B 都应引用可回溯的 evidence ID；无正文证据时不得推断。Agent B 应独立检查蕴含关系、方向、方程、时间尺度、后果类型、引用精确度及反向证据。未解决分歧保留人工仲裁标记，不以简单投票消除。

每次模型调用应记录 provider、model/version、prompt 版本、输入/输出哈希、参数、token、重试、时间和失败原因。

### 子目录

- `01_Prompt与Schema注册/`：版本化 Schema 与提示词。
- `02_模型调用日志/`：调用清单及日志。
- `03_AgentA原始抽取/`：Agent A 原始抽取。
- `04_AgentB_Critic审查/`：Agent B Critic 审查。
- `05_核验通过结果/`：经过迭代核验的最终记录。


### 人工金标准与方法评估阶段说明

## 阶段 05：人工金标准与方法评估

**状态：待执行。** 当前目录仅预留存放位置，尚无金标准、双人审查结果或评估指标。

按实验框架，先对受控 benchmark 做 pilot；随后从全文语料分层抽取至少5篇、50条维度记录进行人工审查。建议两名审查者独立标注，记录冲突与仲裁，并评估证据充分率、标签准确率、页码/章节回溯准确率、unsupported-claim rate、Agent A/B 一致率、检索召回及成本/延迟等。

子目录：`01_人工金标准审核/`、`02_评估指标/`、`03_错误分析/`。


### 跨文献综合与FRDI阶段说明

## 阶段 06：跨文献综合与 FRDI

**状态：待执行。** 本阶段应只使用 `04_LLM抽取与Critic审查/05_核验通过结果/` 中通过核验的记录；目前没有综合结果或 FRDI 分数。

计划产物包括研究范式簇、共同机制、支持与反例证据、研究空白及其与第3–5章的映射。候选方向应绑定多条 evidence ID，并明确反向证据和外推边界。ESI、TGM、LCI 与 FRDI 的权重、归一化和缺失值规则应在计算前冻结；Python 用于固定统计计算和敏感性分析，不替代语义判断。

子目录：`01_跨文献LLM综合/`、`02_FRDI计算/`。


### 图表与章节输出阶段说明

## 阶段 07：图表与章节输出

**状态：待执行。** 当前没有由本项目工作流生成的最终图表、汇总表或章节稿。

建议只从经核验和评估的记录生成章节结论及图表；保留生成脚本、输入版本和计算参数，确保图表可复现。预留子目录：`01_图表_2-1至2-4/`、`02_表格/`、`03_章节稿件/`。

