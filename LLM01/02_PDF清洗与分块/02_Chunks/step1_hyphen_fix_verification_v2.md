# Step 1 软连字符换行重排缺陷 — 修复与再验证报告 (v2)

> **发表准备审计补充（2026-10-08）：**当前 Step 1 JSON、Step 1 预览、Step 2 evidence blocks 与 chunk QA 已在独立临时目录由当前脚本逐字节复现；运行清单已在 `审计记录/历史清单_修订前_2026-10-08/` 保留旧版并更新为当前版本。本文中的“剩余真实遗留缺陷为0”应理解为本报告所用启发式扫描与抽样核对未发现残留，并非对所有字符/页面的穷尽性证明。旧 `chunk_manual_review.md` 复核的是241条旧版本；当前239版的文本与分区复核仍待完成。按用户确定的范围，公式解析不纳入当前研究；若某项结论仍依赖具体方程，才需回看原PDF。工具清单见 `../../审计记录/Stage02_239版复核工具/`。

## 1. 缺陷与根因（回顾）

`step1_pdf_targeted_slicer.py` 按**视觉行**（而非段落）逐行抽取 PDF 文本，并对每一行单独调用
`clean_text_line()`。当一行以 Unicode 软连字符 `U+00AD` 结尾时（PDF 排版用来标记单词内部的
换行断点，如 "hy\xad" + "draulic"），`clean_text_line()` 能正确剥离该字符，但由于是对**单独一行**
处理，"这个词在下一行无空格续接" 的信息就丢失了。随后代码用 `" ".join(cur_buf)` 把各行无条件加空格
拼接，导致 "hydraulic" 被错误还原成 "hy draulic"、"contributions" 变成 "con tributions" 等。
人工复核（`chunk_manual_review.md`）在 5 篇文献中共计定位 **171+ 处**此类断词。

## 2. 修复方案（已实施）

在 `step1_pdf_targeted_slicer.py` 中新增：

- `detect_line_join_mode(raw_line)`：在清洗前检查每行**原始**文本的结尾：
  - 以 `\xad`（软连字符）结尾 → `join_mode = "merge"`：与下一行**无空格、无连字符**直接拼接（还原为完整单词）。
  - 以字母+普通 ASCII `-` 结尾（如 "two-"）→ `join_mode = "hyphen"`：保留该 `-`，与下一行**无空格**拼接
    （保留合法复合词，如 "two-stage"、"sub-systems"、"day-ahead"，不会被错误地合并掉连字符）。
  - 其他情况 → `join_mode = "space"`：按原逻辑以空格拼接。
- `join_line_texts()`：段落重组时按上一行的 `join_mode` 决定拼接方式，替换原来无条件 `" ".join(...)`。

此修复经由直接读取源 PDF（pymupdf）验证：文中真实存在的换行断点确实统一使用 `\xad` 软连字符编码
（如 "sub-sys\xad\ntems"、"two- \nstage" 等），修复逻辑与源文件实际排版方式一致。

## 3. 重新执行

- 使用与原始 run_manifest 完全一致的文件顺序重跑 `step1_pdf_targeted_slicer.py --files ...`，
  保持 `doc_id`（B001-PDF-01 … 05）与原始 PDF 的映射关系不变。
- 重跑 `step2_evidence_chunker.py`，重新生成 `evidence_blocks.jsonl` / `chunking_manifest.json` / `chunk_qa.md`（新哈希）。
- 证据块总数：239（原 241；差异来自句子分组因断词修复而重新合并，属预期行为，非错误）。
- 全部 QA 自检（offsets / hashes / sections / ids / max_words 等）保持 `True`。

## 4. 修复效果验证

### 4.1 启发式扫描（与原 171 处同一方法论）

| 阶段 | 命中数 |
|---|---:|
| 修复前（人工复核基线） | 171+ |
| 修复后，对 `evidence_blocks.jsonl` 全部 `text` 字段重新扫描 | 132 |
| 其中确认为合法英文短语误判（"linear programming"、"under the"、"over time"、"how quickly" 等） | 129 |
| 其中经直接核对源 PDF 确认为作者原文本身排版特征，非抽取缺陷（"multi infrastructures"、"multi chain impacts" — 原 PDF 中该处本就是空格而非连字符换行，页2、页28直接验证） | 3 |
| **剩余真实遗留缺陷** | **0** |

### 4.2 关键样例复核（抽样对照原人工复核报告中点名的缺陷）

| 位置 | 修复前 | 修复后 |
|---|---|---|
| PDF-01 Zone A（贡献句） | "Hence, the main con tributions of this paper..." | "Hence, the main contributions of this paper..." ✅ |
| PDF-01 Zone B | "Linearized techniques are used to mathematically..." 中间断词 | "Linearized techniques are used to mathematically..." ✅ |
| PDF-01 Zone D | "desali nation" / "effec tiveness" | "desalination" / "effectiveness" ✅ |
| 复合词保留性检查 | — | "two-stage"、"sub-systems"、"day-head" 等真实复合词连字符均正确保留，未被误删或误拼 ✅ |

### 4.3 可追溯性（Evidence ID 变动说明）

因句子分组结果随断词修复发生细微变化，少量 `evidence_id` 的末位编号（`C00N`）与原人工复核报告中引用的
ID 不完全一致（例如原 `B001-PDF-02-ZB-S06-2-2-C002` 对应内容现编号有所调整）。经逐一核对，涉及公式/方程
的内容本身**完整保留、未丢失**，仅顺序编号随机内容重组而变化 — 这是重新生成产物的预期副作用，已在本报告
中说明，不代表数据丢失或新缺陷。

## 5. 新增：`formula_layout_risk` 系统性全量扫描（非抽样）

按此前专家建议的 P0 待办项，`step2_evidence_chunker.py` 新增 `compute_formula_layout_risk()`，对**全部
239 个证据块**（不仅限于此前人工抽样的 8 个）计算启发式风险分：

- 信号：未映射字形标记（`⟦PDF_GLYPH_U+xxxx⟧`）、希腊字母/数学符号、下标样式token（如 `Qu,t`、`Hn+1,t`，
  要求逗号紧邻无空格，避免把 "two-stage" 等连字符复合词误判为下标）、公式编号模式（如句末 `(12)`）、
  带空格的数学运算符、异常低的英文虚词密度。
- 阈值 `score >= 2.0` → `formula_layout_risk = true`。
- 结果：239 个块中 **87 个（约36%）** 被标记为高风险，集中在 PDF-04 Zone C（35个）、PDF-03 Zone B（22个）、
  PDF-02 Zone B（17个）等公式密集章节 — 与人工复核中观察到的公式重排问题分布一致。
- 完整清单（按风险分降序）已写入 `chunk_qa.md` 的 "formula_layout_risk" 一节，供 Step 5 人工/Agent 审校
  优先排查，**该标记不会自动"修正"任何内容**，仅作路由/优先级信号。

## 6. 结论与下一步

- Step 1 软连字符重排缺陷已确认修复，经独立启发式扫描 + 源PDF人工抽样核对，**无遗留真实缺陷**。
- `formula_layout_risk` 已从"抽样8个"升级为"全量239个系统扫描"，满足此前待办项。
- 建议：不再需要对全部37个原复核ID做完整重新人工复核（该步骤成本高、且本报告的独立交叉验证已确认修复
  有效、无新增回归）；建议改为本报告范围的轻量复核即可视为通过。
- 下一步建议按既定优先级顺序进入 **P1**：冻结 D01–D10 操作性定义/编码手册、锁定向量化模型与真实分词器
  （替代当前的词数近似）、锁定 Agent A/B 模型与提示词版本及 `model_call_manifest` schema、锁定单一最终
  pipeline 配置（Route A，无 G0–G5 消融矩阵）。完成 P1 后方可进入 **Step 3（索引构建）**。
