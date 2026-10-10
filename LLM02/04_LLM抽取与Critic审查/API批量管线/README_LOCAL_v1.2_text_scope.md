# v1.2 本地 API 批处理：隔离版执行说明

- **版本：**Step 3/4 v1.2 local text-scope branch（2026-10-10）
- **定位：**本地 PDF → 本地切片/证据块 → 本地 BM25/dense 检索 → loopback/批准的私有网段 OpenAI-compatible LLM API。
- **不覆盖：**原 `step4_api_batch_extraction.py`、原 Stage 03 固定索引、现有 B001 结果及 API 管线 `产出/`。新的 Step 1/2 wrapper 要求全新输出目录；Step 3 构建器拒绝覆盖；新 Step 4 只写 `产出_v1.2_local_text_scope/<run_id>/`。
- **范围：**Agent A/B 处理 D01、D02、D04–D10；D03 由程序本地写成 `Not_Analyzed_Out_Of_Scope` 状态记录，单独放入 `06_范围状态_D03/`，不进入9维核验结果文件、模型输入、结论或质量指标。`B001-PDF-03:D02` 仍未获用户定稿；模型输入会移除该文献的 D02 `boundary_rule` 与 `interpretation_note`，改传中性的人工裁定提示，并且无论模型候选标签如何都强制标为 `adjudication_required`；不能视为任何未确认选项已获批准。新结果仍需人工/领域研究者抽查。

## 1. 文件

- `step1_run_versioned_batch_local.py`：调用原 Step 1 切片器，但强制新目录，并生成含 PDF SHA-256 的 `run_manifest.json`。
- `step2_run_versioned_local.py`：调用原 Step 2 chunker，但强制新目录，并记录 Step 1/input/output hashes。
- `../../03_证据索引与混合检索/step3_build_hybrid_index_v1_2_local.py`：从指定证据块构建**新目录**中的 BM25/dense 索引；默认模型本地加载、目标目录已存在即拒绝覆盖。
- `../../03_证据索引与混合检索/step3_hybrid_retrieval_v1_2_local.py`：按显式 evidence/index 路径加载索引；核对 evidence/index SHA-256、embedding 模型名与 evidence ID 顺序；默认 FastEmbed `local_files_only=True`。BM25 使用 pickle，只加载可信本机索引目录（hash 是完整性核验，不是数字签名）。
- `llm_api_client_v1_2_local.py`：只支持 `openai_compatible` 本地端点或 `dry_run`；无远端 provider/fallback，允许服务不鉴权，禁用代理环境变量和 HTTP redirect。
- `step4_api_batch_extraction_v1_2_local_text.py`：读取 schema/prompt、路径可配置、D03 单独 status-only 文件、tokenizer 预检可选强制、run_id 隔离且拒绝重跑覆盖。
- `agent_prompts_v1.2_local_text_scope.json`：版本化 prompt；不把 D03 维度或 schema 发给模型。
- `.env.local.example`：本地 API 配置模板。与原 `.env.example` 区分；原模板默认指向 CSTCloud。
- `tests/test_v1_2_local_text_pipeline.py`、`tests/test_v1_2_local_index.py`、`tests/test_v1_2_local_synthesis.py`：12项 loopback mock、dry-run、stub index、payload 隔离、完整五篇门槛和引用校验测试，不调用真实模型或下载真实 embedding 权重。

## 2. 安装与离线准备

在运行机器上一次性安装项目依赖：

```bash
python -m pip install -r ../../requirements.txt
```

还需准备本地 API 服务及其本地模型权重，并确认它实现 OpenAI Chat Completions 路由。严格断网前，FastEmbed embedding 权重也必须缓存到本机；新的检索模块在运行时使用 `local_files_only=True`，缺权重会失败关闭，不会静默联网下载。

可在获准联网的准备环境中显式下载/预热 FastEmbed 模型，再复制完整 cache 到离线机器：

```bash
python ../../03_证据索引与混合检索/step3_build_hybrid_index_v1_2_local.py \
  --evidence-blocks /path/to/versioned/evidence_blocks.jsonl \
  --index-dir /path/to/new-index-v1.2 \
  --embedding-cache-dir /path/to/fastembed-cache \
  --allow-model-download
```

正式离线构建时**不要**带 `--allow-model-download`；默认只读指定缓存。FastEmbed 官方示例支持 `cache_dir` 与 `local_files_only` 的本地模型准备/加载方式，见 [Qdrant FastEmbed on-device guide](https://qdrant.tech/documentation/edge/edge-fastembed-embeddings/)。如果安装的 FastEmbed 不支持 `local_files_only`，新代码会中止，需升级/确认本地包版本后再继续。

如果需要 token 级 context 预检，还需在本地安装 `transformers`，并准备与每个实际模型匹配的 tokenizer 文件目录。Tokenizer 必须来自本地路径，加载时设置 `local_files_only=True`；不提供时只会明确警告，若加 `--require-token-preflight` 则真实调用前会拒绝运行。

## 3. 为新 PDF 建立隔离输入与索引

Step 4 不读原始 PDF。先为新批次指定新 batch ID、新输出目录；不得把新文件追加进原 B001 固定产物路径：

```bash
python step1_run_versioned_batch_local.py \
  --input-dir /path/to/new-pdfs \
  --output-dir /path/to/project-data/B002/step1 \
  --batch-id B002 \
  --files paper-a.pdf paper-b.pdf

python step2_run_versioned_local.py \
  --input /path/to/project-data/B002/step1/step1_sliced_pdf_corpus.json \
  --source-manifest /path/to/project-data/B002/step1/run_manifest.json \
  --output-dir /path/to/project-data/B002/step2

python ../../03_证据索引与混合检索/step3_build_hybrid_index_v1_2_local.py \
  --evidence-blocks /path/to/project-data/B002/step2/evidence_blocks.jsonl \
  --index-dir /path/to/project-data/B002/step3_index \
  --embedding-cache-dir /path/to/fastembed-cache
```

`step1_run_versioned_batch_local.py` 在 Step 1 开始前核验 PDF 名称并记录输入哈希；输出目录必须不存在。Step 2 wrapper 也要求新目录，检查 Step 1 manifest 与文档文件名匹配，并保留输入/脚本/输出 hash。若步骤中途失败，wrapper 保留部分产物和 `failed` manifest 供审查，不删除、不复用目录。新 index builder 要求 `--index-dir` 不存在；不会覆盖旧 index。

## 4. 配置本地模型端点

复制模板：

```bash
cp .env.local.example .env.local
```

在 `.env.local` 中填入本机 API 的准确 model ID。常见本地服务可使用自身 `/v1` OpenAI-compatible 根路径；例如模板给了一个 loopback 地址形状，但应按你真正启动的服务确认端口和模型名。配置后可单独查询本地 `/models`（此操作不需要 evidence/index 参数）：

```bash
python step4_api_batch_extraction_v1_2_local_text.py --list-models
```

- 本机 API 不鉴权时，API key 可以留空；客户端不会发送 Authorization header。
- `.env.local` 可能包含密钥；当前工作区没有 Git 仓库或忽略规则，若之后初始化 Git，请先把 `.env.local` 加入 ignore，且不要把密钥写入共享文档。
- 如果模型服务位于另一台主机的私有 IP，必须显式加 `--allow-private-network`；公共地址和任意 DNS hostname 默认拒绝。
- 本地客户端不读取旧的 fallback 模型字段，也不支持云端自动 failover。
- 本地 server 未明示支持非标准字段前，不发送 `chat_template_kwargs`。
- `requests` 使用独立 session，`trust_env=False` 且禁止 HTTP redirect，避免 shell 代理或重定向让 prompt 被转发到其他 endpoint。若要求强保证，仍应通过操作系统防火墙阻断不需要的外网连接，并确认本地推理服务本身没有额外遥测/上传。

## 5. 试跑与扩展批次

先做不调用模型的结构 smoke test（仍需本地 evidence/index 与 FastEmbed cache 以检验真实检索路径）：

```bash
python step4_api_batch_extraction_v1_2_local_text.py \
  --evidence-blocks /path/to/project-data/B002/step2/evidence_blocks.jsonl \
  --index-dir /path/to/project-data/B002/step3_index \
  --doc-ids B002-PDF-01 \
  --dry-run
```

`dry_run` 输出都标记为 `dry_run_placeholder_non_data`，不可合并进结果或指标。随后对真实本地端点先试一篇，并建议配 tokenizer/context 上限：

```bash
python step4_api_batch_extraction_v1_2_local_text.py \
  --evidence-blocks /path/to/project-data/B002/step2/evidence_blocks.jsonl \
  --index-dir /path/to/project-data/B002/step3_index \
  --doc-ids B002-PDF-01 \
  --tokenizer-path-agent-a /path/to/local/tokenizer-a \
  --tokenizer-path-agent-b /path/to/local/tokenizer-b \
  --context-limit-agent-a 32768 \
  --context-limit-agent-b 32768 \
  --require-token-preflight
```

只有检查 endpoint、证据 ID/引用、维度完整性、运行清单、资源使用和人工抽查后，才运行 `--all`。context 超限时程序会失败并记录原因，不截断证据、不静默缩短上下文。由于每篇论文的 coverage pass 会把所有 evidence block 纳入提示，较长 PDF 可能需要更大 context；当前没有自动切块模型调用策略，因为分块会改变已锁定协议，需另立版本评估。

每次运行自动创建唯一 UTC `run_id` 目录；同名 run ID 已存在时拒绝运行。`model_call_manifest.jsonl` 仅追加在该次唯一目录内，运行配置会记录 evidence/schema/prompt/index、同目录 Step 2 lineage manifests 与执行代码的 SHA-256，并对 API key 脱敏。

## 6. 研究与审核边界

- D03 永远只在 `06_范围状态_D03/` 单独生成 `Not_Analyzed_Out_Of_Scope` 状态 JSON；不进入9维 `verified` 文件。它不是“无方程”的发现，也不作为 Agent A/B 输入、Step 5 标签分布或公式质量指标。
- Agent A/B 的不同本地 endpoint/model 名称不自动证明统计独立性。结果中的 `cross_model_independence` 为 `not_established_from_configuration_alone`；本流程不冒称独立人类专家终审。
- 只对证据 ID、同文档归属、schema 标签、引用位置、引用文本匹配、JSON 完整性作程序化预检；语义判断仍需人工抽查。结构校验通过不等于结论正确。
- API prompt 可能包含全文证据块。此本地分支只允许 loopback 或用户显式授权的私有 IP；实际数据路径还取决于模型服务自身部署与操作系统网络策略。
- 本目录运行结果是独立的 v1.2 provisional 批次；不得直接覆盖/混入 v1.0 `05_核验通过结果/`，也不得在没有确认标签/证据和研究范围前生成领域级结论。

## 7. 后续 Step 5–7：仅接真实本地 Step 4 ledger

三项候选方向已在论文第一节 Introduction 中通过领域文献对比提出。本 pipeline 将它们作为既有输入；不在线搜索，也不实现候选方向自动生成。以下下游命令必须使用完整5篇、同一个真实 `local_api_only` Step 4 run；不能把 dry-run、mock 或本说明中静态先导 ledger 当作新模型结果。

### 7.1 编译一份全新 local-run ledger

```bash
python '04_LLM抽取与Critic审查/06_v1.2文本范围预分类/compile_v1.2_local_run_ledger.py' \
  --run-dir '/path/to/产出_v1.2_local_text_scope/<complete-run-id>' \
  --evidence-blocks '/path/to/versioned/evidence_blocks.jsonl' \
  --output '/path/to/new-output/ledger_<unique-run-id>.json'
```

编译器要求 Step 4 run 中所有已请求文献均完成、失败数为0、schema/evidence 哈希匹配、manifest 为真实 local API 调用；并检查 PDF-03/D02 仍是未裁定状态。当前 B001 先导流程应提交5篇全量 run；即使 ledger 只编译了部分文献，Step 6 也会拒绝它。输出必须使用全新文件名。D04–D10 需来自这次真实 local Step 4，不会从 v1.0 搬入。

### 7.2 Step 5 描述频数与 Step 6 本地证据挑战

```bash
python '05_人工金标准与方法评估/02_评估指标/step5_v1.2.1_provisional_descriptive_counts.py' \
  --ledger '/path/to/new-output/ledger_<unique-run-id>.json' \
  --run-id 'step5-<unique-run-id>' \
  --output-dir '/path/to/new-output/step5'

python '06_跨文献综合与FRDI/01_跨文献LLM综合/step6_local_evidence_challenge_v1_2.py' \
  --ledger '/path/to/new-output/ledger_<unique-run-id>.json' \
  --evidence-blocks '/path/to/versioned/evidence_blocks.jsonl' \
  --env-file '04_LLM抽取与Critic审查/API批量管线/.env.local' \
  --tokenizer-path '/path/to/local/tokenizer' \
  --context-limit 32768 \
  --require-token-preflight
```

Step 6 仅对 Introduction 中已有的三项方向进行支持/反证/不确定性挑战，不重新提出或调整方向；必须为完整 `B001-PDF-01` 至 `B001-PDF-05` ledger。D03 在所有模型输入前被过滤，支持/反证必须引用本输入包中的精确 evidence ID 和原文，PDF-03/D02 未裁定标记不会被模型或程序升级成最终决定。Step 6 结果仍是本地模型的初步挑战，不是独立专家裁定或领域级验证。若尚未获得真实 local Step 4 ledger，不要运行此步骤；dry-run 输出不能用于 Step 5–7 指标/结论。

### 7.3 版本化制表和绘图

```bash
python '07_图表与章节输出/02_表格/step7_generate_tables_v1_2_text_scope.py' \
  --metrics '/path/to/new-output/step5/evaluation_metrics_v1.2.1_scope_aligned_provisional_<run-id>.json' \
  --output '/path/to/new-output/step7/chapter2_tables_v1.2.1_<unique-run-id>.xlsx'

python '07_图表与章节输出/01_图表_2-1至2-4/step7_generate_figures_v1_2_text_scope.py' \
  --metrics '/path/to/new-output/step5/evaluation_metrics_v1.2.1_scope_aligned_provisional_<run-id>.json' \
  --output-dir '/path/to/new-output/step7/figures_<unique-run-id>'
```

表格/图表生成器拒绝覆盖现有文件或目录；D03 只能以范围状态 metadata 显示，不进入九维主频数；PDF-03/D02 会显式标为未裁定。图表与表格要通过输入路径/哈希、run ID、样本与未裁定边界审核后再引用。

**当前状态（2026-10-10）：**12项测试全部通过，但仅测试 mock 与校验路径；尚无真实 Step 3/4 本地跑批、local-run ledger 或 Step 6 模型输出。本轮 Step 5/7 已生成的 static-pilot 产物仅反映旧 provisional ledger，不能替代真实 local-run 结果。
