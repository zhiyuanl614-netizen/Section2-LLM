# Step 3 检索配置锁定（v1.0 — 已冻结，2026-10-06）

**状态：** 本文档锁定 embedding 模型、真实 tokenizer、BM25 分词器、混合检索融合方法及相关参数。
所有内容已在当前沙箱环境中**实际运行验证**（非仅纸面设计），验证记录见第5节。
冻结后若发现需要调整，须新开版本号并记录变更日志，不得静默修改。

---

## 1. Embedding 模型（dense 检索）

| 项目 | 锁定值 |
|---|---|
| 模型名称 | `BAAI/bge-small-en-v1.5` |
| 解析来源 | HuggingFace 仓库 `Qdrant/bge-small-en-v1.5-onnx-Q`（ONNX int8 量化变体，通过 `fastembed` 库解析） |
| 调用库 | `fastembed==0.8.1`（底层 `onnxruntime`，不依赖 torch/GPU，避免了本沙箱对 `sentence-transformers`+torch 的磁盘/内存限制） |
| 向量维度 | 384 |
| 最大输入长度 | 512 token（模型自身截断限制，tokenizer 为其自带的 WordPiece/BPE，非本项目的 cl100k_base） |
| 许可证 | MIT（开源、免费、无需 API key、无调用费用） |
| 已验证模型文件哈希 | `model_optimized.onnx` sha256 = `51f1bd0addd6e859e42c2c8021a5e5461385bb676a649f4b269aa445449f2431`（本次下载实测值，供未来重新下载时核对一致性；若哈希不同需记录并核查模型是否被上游更新） |
| 运行时内存约束 | 沙箱总内存约1.9GB；一次性对239个块做批量 embedding 时，默认 batch_size 会导致 onnxruntime attention 层内存分配失败（实测 OOM）。**锁定 `batch_size=4`** 作为安全值（已实测239块全部成功，用时约50秒）；该参数只影响计算效率，不影响向量数值，可在后续更大内存环境下调高但不需要为此重新定义"锁定"状态。 |
| 查询/文档前缀 | 该模型版本（v1.5）官方说明"前缀非必需"（不同于v1的"必需"前缀要求）；本项目**不加前缀**，直接编码 `retrieval_text`（章节标题+正文）。 |

**截断风险披露：** 对当前239个证据块用 `cl100k_base` 实测 token 数，有 **3 个块**（`B001-PDF-02-ZB-S05-A-C004`、`B001-PDF-02-ZB-S08-B-C004`、`B001-PDF-03-ZC-S12-3-3-C003`）的 `retrieval_text` 超过512 token 上限，会被该 embedding 模型截断。三者均已被 Step 2 的 `formula_layout_risk` 标记为高风险公式块（分数 8.0/12.0/6.0）。**处理规则（锁定）：** 不因此重新切块或改写已冻结的 `evidence_blocks.jsonl`；dense 索引允许对这3块做截断编码（可能损失召回），但 BM25 侧会对**完整未截断文本**分词索引，由混合检索的词法腿兜底这3个块的可检索性；Step 5 审校应将这3个 ID 列入优先人工核查清单（与 `formula_layout_risk` 清单重合）。

**环境可复现性提示：** `fastembed` 模型缓存位于沙箱临时目录（非 `/home/user` 下），**不会跨会话持久化**；Step 3 实际建索引时需要重新触发一次自动下载（无需手动干预，`fastembed` 会自动从 HuggingFace Hub 拉取），下载后应重新核对上方模型文件哈希是否一致。

---

## 2. 真实 Tokenizer（替代原词数近似）

| 项目 | 锁定值 |
|---|---|
| 用途 | 上下文窗口/token 预算核算、`chunk_qa.md` 中词数统计的真实 token 口径补充 |
| 工具 | `tiktoken` 库，`cl100k_base` 编码 |
| 选择理由 | 作为通用、广泛使用、无需额外训练/下载语料的真实 BPE tokenizer 代理；不代表最终 Agent A/B 执行所用模型的真实 tokenizer（因为本项目 Step 4 由 Arena.ai Agent 直接在对话中执行推理，而非调用可获取 tokenizer 的外部付费 API），但相比"按空格词数近似"更贴近真实 token 消耗，适合做上下文预算的保守估计基准。 |
| 实测统计（对239个证据块的 `retrieval_text`） | 词数 median=181/mean=155.2；cl100k token 数 median=257/mean=243.6；token/词 比值 median=1.48、mean=1.65。 |
| 下游含义 | Step 2 的180词目标/240词上限仍保留作为"证据块切分"的版本化口径（已冻结，不因本次锁定重新切块）；但 Step 3/4 组装模型上下文窗口时，应按**token**而非词数预算，换算时按本表比值做保守估计（建议按 ×1.7 的安全系数折算词数到 token 数）。 |

---

## 3. BM25 分词器（词法检索）

**库：** `rank_bm25`（`BM25Okapi`），纯 Python 实现，无额外模型下载依赖。

**分词规则（已锁定，精确代码如下，供 Step 3 实现直接复用）：**

```python
import re

STOPWORDS = {
 "a","an","the","and","or","but","if","then","than","of","in","on","at","to","for","with",
 "by","from","as","is","are","was","were","be","been","being","this","that","these","those",
 "it","its","we","our","they","their","he","she","his","her","can","could","would","should",
 "will","shall","may","might","must","not","no","do","does","did","have","has","had","which",
 "who","whom","what","when","where","why","how","also","such","both","each","more","most",
 "other","some","any","all","into","through","during","before","after","above","below","between",
 "out","up","down","over","under","again","further","once"
}
TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:[-'][A-Za-z0-9]+)*|\d+(?:\.\d+)?")

def bm25_tokenize(text: str) -> list[str]:
    text = text.replace("\u00ad", "")  # 防止任何残留软连字符影响分词
    tokens = TOKEN_RE.findall(text.lower())
    return [t for t in tokens if t not in STOPWORDS and len(t) > 1]
```

**设计理由：**
- 连字符复合词（如 `two-stage`、`sub-systems`）作为**单个 token** 保留，不拆分，避免和 Step 1 修复的软连字符问题产生新的歧义；
- 固定英文停用词表（非 NLTK/第三方语料，避免引入未冻结的外部版本依赖），不做词干还原（stemming）——因语料含大量专业术语/变量名，词干化可能把有区分度的工程术语错误归并；
- 已知局限（接受）：对公式记号如 `Qu,t`、`Hn+1,t` 会被拆成 `qu`、`hn` 等，丢失下标信息，无法做精确公式符号匹配；这是词法检索对公式的固有局限，已通过 `formula_layout_risk` 标记路由到人工/Agent 复核，不在 Step 3 索引层试图"修复"。

**冒烟测试（已执行）：** 对239个证据块建立 BM25 索引，用示例查询"early warning proactive control fast sensing slow hydraulic timescale"（对应 D04–D06 风格查询）检索，返回的 top-5 结果语义相关、无报错。

---

## 4. 混合检索融合方法

| 项目 | 锁定值 |
|---|---|
| 融合算法 | **Reciprocal Rank Fusion (RRF)**，公式：`RRF_score(d) = Σ 1/(k + rank_i(d))`，对 dense 和 BM25 两路排名分别计算后求和 |
| 常数 k | 60（RRF 原始论文 Cormack et al., 2009 的常用默认值，不需要额外训练/调参，适合小语料探索性研究） |
| 选择理由 | 相比加权线性融合（weighted sum of scores），RRF 不要求两路分数量纲一致（BM25分数与余弦相似度量纲完全不同），无需额外归一化步骤，是信息检索领域广泛使用且参数极少的稳健融合方法，适合 Route A 下"锁定单一配置、不做消融矩阵"的要求。 |
| Top-k（每路进入融合前） | 各召回 Top-20，融合后取 Top-10 作为最终上下文候选（数值为本阶段默认值，Step 3 执行时应用 RQ1-4/D01-D10 查询做覆盖率验证后可按证据调整，但调整须记录版本变更，不得在无验证记录的情况下随意改动）。 |
| 去重规则 | 按 `evidence_id` 去重（同一块不会同时以两个排名出现在融合结果中）。 |
| Coverage pass（全文覆盖） | 按 Route A 设计，除 Top-k 检索外，叠加"全文 coverage pass"：对每篇论文的全部 evidence blocks 做一次不依赖检索排名的强制全量遍历式抽取（用于 Agent A 全文十维抽取，而不仅是检索命中块），以避免 Top-k-only 漏召回没有关键词命中的方程/反例/局限段落。 |

---

## 5. 已执行的验证记录

| 验证项 | 结果 |
|---|---|
| `fastembed` 安装与模型下载 | 成功（`sentence-transformers`+torch 因沙箱磁盘/overlay限制安装失败，已改用 `fastembed`+onnxruntime 路线，记录在"错误与弃用方案"） |
| 239个证据块全量 embedding | 成功，`batch_size=4`，384维，约50秒 |
| `tiktoken cl100k_base` 全量 token 统计 | 成功，见第2节数据 |
| `rank_bm25` 建索引 + 示例查询检索 | 成功，返回语义相关结果 |
| Dense 向量示例查询检索 | 成功，返回语义相关结果（余弦相似度0.69–0.71区间，结果与 BM25 有重合也有互补，初步印证 H3 混合检索假设方向合理，但这不是正式的 RQ-E3 对照实验，仅为配置可用性冒烟测试） |

**重要边界声明：** 本节验证仅确认"配置可运行、输出合理"，**不构成** README 中 RQ-E1–E5 的正式实验证据，也不满足 G0–G5 消融比较（该比较按 Route A 决策已明确不执行）。正式的检索�covered率/召回评估需在 Step 3 用标注好的 D01–D10 相关 evidence IDs 查询集完成后才能下结论。

---

## 6. 错误与弃用方案记录

- `pip install sentence-transformers`：两次尝试均在安装 torch 依赖时报 `OSError: [Errno 28] No space left on device`，即便 `df -h` 显示磁盘空间充足（20G 可用）——怀疑是沙箱写时复制层（overlay）对单次写入/大文件有隐藏限额，与 `df` 报告的宿主机级别统计不一致。已放弃该路线，改用 `fastembed`（基于 onnxruntime，无需 torch，体积更小）。
- 默认 `fastembed` batch_size 在本沙箱（1.9GB内存）直接对239个块编码时导致 onnxruntime 内存分配失败（请求约3GB attention buffer）；已改用 `batch_size=4` 规避，不是模型或向量本身的问题。
