# Batch_001 Step 1 修复与复核记录

> **版本状态更新（2026-10-08）：**本文记录的是2026-10-05的Step 1复核快照。之后的软连字符修复及239条最终候选分块，请以同目录 `../02_Chunks/step1_hyphen_fix_verification_v2.md`、`../02_Chunks/chunk_qa.md` 和项目根目录 `审计记录/02_阶段核验报告.md` 为准。本文中“尚未运行RAG/evidence-block切分”等描述是当时状态，不是当前项目状态。

- **复核日期：**2026-10-05（Asia/Shanghai）
- **批次：**B001；输入严格为 `01_文献库/` 中本轮指定的5篇原始 PDF。
- **执行范围：**PDF 文本解析、首页元数据提取、章节树构建、Zone A–D 粗粒度定向切片；未运行 RAG 索引、正式 evidence-block 切分、LLM API 调用或人工标注实验。
- **解析脚本：**`02_PDF清洗与分块/step1_pdf_targeted_slicer.py`

## 问题原因与修复

| 原问题 | 原因 | 本轮修复 |
|---|---|---|
| Zone C 为空或内容被分错 | 旧规则对结果标题的词面覆盖不足；不认识 IOR、指标/计算/性能等常见表述，未知章节易掉进 Zone B；嵌套子标题也没有继承父章节上下文。 | 扩充结果/指标/性能/IOR/计算/影响分析术语；按结果→方法→案例/讨论的优先顺序分类；对仍不明确的子章节继承已识别父章节 Zone，并标注 `inherited from parent; verify`。 |
| 章节树误收首页标签、列表项和普通正文行 | 单字母编号规则把 `A R T I C L E I N F O`、`A B S T R A C T` 等间隔大写误当标题；未排除 `1)` 列表；无上限数字行（如 `336.`）可能误入章节树。 | 单字母标题须有明确点号及标题字体特征；排除 `n)` 列表样式；过滤大于20的阿拉伯章节号；修复 Roman `I` 主标题与字母子标题 `I.` 的歧义；分类标题时对连字做 NFKC 规范化。 |
| 作者缺失或误取标题尾行 | 旧回退按标题词重叠推断标题底部，可能把作者行/标题续行算入标题范围；候选又未限制为作者列表样式。 | 只在首页标题与 Abstract 之间搜索带逗号的作者候选，并排除院系/单位行；IEEE `Student Member/Member/Fellow, IEEE` 职级从展示用作者名中剔除，同时在 `author_byline_raw` 保留原始行。 |
| 期刊/年份/DOI/摘要/关键词来源不透明 | PDF 内嵌字段不完整，旧输出没有逐字段标出回退来源；643 文献缺少内嵌 title。 | JSON 新增 `abstract`、`author_byline_raw`、`metadata_sources`、`metadata_warnings`；优先 PDF 内嵌字段，其次首页可见文本，再到文件名。643 的标题从首页可见标题提取，不再依赖去标点的文件名。 |
| 文本中的 PDF 符号变成 `�` 或被猜补 | 部分 PDF 字体的 ToUnicode/CMap 映射不完整；提取结果含控制码点，通常涉及公式/特殊字形。无法从码点本身推回原始视觉符号。 | 不再静默输出替代字符或猜补：清洗文本中用 `⟦PDF_GLYPH_U+XXXX⟧` 显示所提取码点；JSON 同时记录页码、字体和次数。此标记只表示“映射失败”，不代表已恢复原符号。 |

## 本轮结果

| Doc ID / PDF | 页数 | 章节条目 | Zone A | Zone B | Zone C | Zone D | 未分类回退 | 未映射字符警告* |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| B001-PDF-01 `120.pdf` | 12 | 17 | 670 | 2,459 | 1,324 | 459 | 0 | 0 |
| B001-PDF-02 `105_Optimal_Coordination_...pdf` | 10 | 16 | 991 | 3,403 | 1,787 | 307 | 0 | 89 |
| B001-PDF-03 `643_Resilience Assessment...pdf` | 31 | 32 | 521 | 6,381 | 3,385 | 1,770 | 0 | 29 |
| B001-PDF-04 `46_Resilience_of_Cyber-Enabled...pdf` | 17 | 54 | 428 | 1,444 | 6,180 | 962 | 0 | 174 |
| B001-PDF-05 `37_Quantifying the dependent failure...pdf` | 15 | 22 | 492 | 979 | 4,546 | 1,117 | 0 | 0 |

\* 未映射字符警告为文档级页码/字体扫描计数；部分可能来自被剥离的出版商图标/版面字形，不等于保留切片中占位符数量。Zone 词数是预处理统计，含少量标题/元数据标签，且不把 `PDF_GLYPH` 标记计作英文单词。

## 元数据抽取复核

- 五篇均有非空标题、作者、期刊、年份、DOI、关键词和摘要；摘要来自首页带标签的文本块。JSON 逐字段标记来源。
- B001-PDF-02 与 B001-PDF-04 的展示作者名已去除 IEEE 会员级别标签；原始 byline 仍保存在 JSON。
- B001-PDF-03 的题名从首页可见标题提取为 **“Resilience Assessment of Interdependent Infrastructure Systems: A Case Study Based on Different Response Strategies”**；作者行中的 `1`/`2` 机构脚注标记保留，避免未经核验地重写署名。
- B001-PDF-05 的首页期刊卷期标注为 **2027**，DOI 字符串含 **2026** 年份标记，且首页列有 2026-08-24 online 日期。保留卷期年 2027，并在 `metadata_warnings` 标注差异；不把 DOI 年份标记当作出版年。B001-PDF-01、02、04 也记录 DOI 年份标记与卷期年的差异，不据此改年。

## 验证

- `python -m py_compile step1_pdf_targeted_slicer.py`：通过。
- 指定5个原始 PDF 的 Batch_001 重跑：成功；JSON、Markdown 预览、XLSX、DOCX 已覆盖生成。
- 自动 QA 断言：5篇均存在 A–D 四区且 Zone C 非空；元数据核心字段与摘要均非空；未分类回退数均为0；章节树中未发现本轮已排除的首页标签、`1)` 列表标题和 `336.` 类示例假标题；JSON/Markdown 未发现 U+FFFD（`�`）字符。
- 0个回退不等于分类已人工证实。分区仍为标题关键词+父级继承的粗分类；特别是继承项以及方法/结果交界标题仍应人工抽样对照原 PDF。

## 尚未解决 / 不得过度声称

1. `⟦PDF_GLYPH_U+XXXX⟧` 保留了提取失败的码点线索，但**没有恢复公式、希腊字母、上下标或其他特殊符号**。需要按 JSON 中页码/字体回看 PDF，必要时做页面图像/OCR或字体映射专门处理；当前不应把占位符解释为数学符号。
2. 章节和 Zone 映射是预处理启发式结果，不是人工金标准，也不能作为正式 RAG evidence blocks。需后续按原文核验标题层级、页码、段落边界和 Zone 归属。
3. 本轮没有生成带 `evidence_id`、字符偏移的细粒度 evidence blocks，也没有运行 RAG/LLM 实验。

## 文件

同目录中的 `step1_sliced_pdf_corpus.json` 是结构化源数据；`step1_sliced_zones_preview.md` 是可读切片预览；`Step1_PDF章节树解析与四区靶向切片实验报告.xlsx` 与 `.docx` 是核验报告；`run_manifest.json` 记录输入/输出哈希、脚本哈希和依赖版本。
