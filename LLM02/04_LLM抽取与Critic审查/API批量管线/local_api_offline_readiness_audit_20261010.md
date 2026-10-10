# Step 4 API 批量管线：本地/离线运行核验

- **核验日期：**2026-10-10
- **核验对象：**`step4_api_batch_extraction.py`、`llm_api_client.py`、Stage 03 `HybridIndex`、`requirements.txt` 与 API 管线配置模板。
- **核验方式：**静态检查、Python 编译、loopback 本地 HTTP mock 传输测试、无 API 调用的 dry-run 入口测试。
- **未执行：**没有真实本地模型服务器/权重/用户 API 凭据，因此没有真实模型推理或外网 API 调用；也未安装依赖、未改代码、未生成抽取结果。

## 一、结论

**分层结论：**

1. **本地 API 传输层：条件可用。**`llm_api_client.py` 的 `openai_compatible` 适配器可以把自定义 `base_url` 指向本机 OpenAI-Chat-Completions-compatible 服务；我用仅绑定 `127.0.0.1` 的 mock 服务验证了 `/v1/chat/completions` POST、响应解析，以及 `/v1/models` GET。此测试没有访问外网，不等于已验证 Ollama、LM Studio、vLLM 等任一真实本地服务。
2. **完整本地 Step 4 管线：当前环境未能跑通。**执行无网络 `--all` dry-run 时，在 Stage 03 反序列化 BM25 索引处即因缺少 `rank_bm25` 失败；`fastembed` 与 `python-dotenv` 也未安装。`requirements.txt` 列出了这些依赖，但仅凭当前工作区无法确认用户本地环境已安装。
3. **对当前 v1.2 公式排除范围：原 API 批处理脚本不可直接用于未来 PDF。**脚本硬编码 v1.0 提示词，并读取 `schema_v2.json`（其内部 `schema_version` 为 v1.1）；Agent A/B 指令会分析 D03 方程类型/`equation_detail`。直接运行会违反当前明确的“D03 方程范围外”约束。应先开发一个**非破坏性、版本化的 v1.2 text-only API 分支**。
4. **完整离线保证：尚无。**客户端不限制 endpoint 必须为本机；示例 `.env` 默认指向 CSTCloud。Stage 03 查询还会惰性加载 FastEmbed 模型，首次使用可能需要下载模型。需要配置本地服务、预置依赖与权重，并加本地 endpoint 防外联检查后，才能称为严格离线运行。

**因此：**如果“线下调用 API”指本地模型服务、PDF 内容不出本机，接口架构支持这种方向；但当前管线**不是开箱即用的离线 v1.2 全流程**。不建议原样对扩展 PDF 执行正式批次。

## 二、核验记录

| 项目 | 结果 | 说明 |
|---|---|---|
| 三个 Python 文件 `py_compile` | 通过 | API 客户端、Step 4 编排器、Stage 03 检索模块均无语法错误 |
| Step 4 CLI `--help` | 通过 | 参数入口可加载 |
| 本地 mock `POST /v1/chat/completions` | 通过 | 请求命中 `127.0.0.1`，返回的模型名/usage/text 被正确解析 |
| 本地 mock `GET /v1/models` | 通过 | 模型列表解析成功 |
| 空 API key 行为 | 已验证为拒绝 | `openai_compatible` 当前强制要求非空 API key；没有 key 的本地服务器也需给客户端提供非空占位 key（服务器必须忽略它/接受该值），或修改客户端允许省略 Authorization header |
| 无网络 `--all` dry-run | 未完成 | 失败于 `ModuleNotFoundError: No module named 'rank_bm25'`，发生在检索索引加载阶段，尚未调用模型，也未写批次产物 |
| 工作区依赖 | 不齐 | 已有 `requests`、`numpy`；缺 `rank_bm25`、`fastembed`、`python-dotenv`。当前未发现管线 `.env` 或 FastEmbed/HuggingFace 本地模型缓存 |
| 真实本地模型调用 | 未测试 | 当前没有可用本地模型 server/模型 ID/服务配置；mock 只验证协议接线，不验证生成能力、格式遵循或速度 |

当前5篇在 coverage pass 中每篇约有 **28–69 个 evidence blocks、2.6万–7.5万字符的证据文本**（尚未加 schema、system prompt 和 JSON 开销）。这不是 token 数；本地模型需用其实际 tokenizer 做输入长度预检。脚本目前没有显式 context-length 预检或自动切分策略。

## 三、要让本机 OpenAI-compatible 服务接入的配置条件

`llm_api_client.py` 会把配置的 `base_url` 拼成 `{base_url}/chat/completions`，因此 `base_url` 应是 API 根路径（例如包含 `/v1`，但不要包含 `/chat/completions`）。本地服务及模型须已在运行/加载。

```dotenv
AGENT_A_PROVIDER=openai_compatible
AGENT_A_BASE_URL=http://127.0.0.1:<port>/v1
AGENT_A_API_KEY=<服务要求的key，或服务接受的非空本地占位值>
AGENT_A_MODEL=<本机服务公布的精确模型ID>
AGENT_A_FALLBACK_MODEL=
AGENT_A_CHAT_TEMPLATE_KWARGS={}

AGENT_B_PROVIDER=openai_compatible
AGENT_B_BASE_URL=http://127.0.0.1:<port>/v1
AGENT_B_API_KEY=<服务要求的key，或服务接受的非空本地占位值>
AGENT_B_MODEL=<本机服务公布的精确模型ID>
AGENT_B_FALLBACK_MODEL=
AGENT_B_CHAT_TEMPLATE_KWARGS={}
```

这是配置形状示例，不代表已验证某一服务器端口/模型。若本机 API 不鉴权，当前客户端仍会因空 key 主动报错；占位 key 只有在服务端忽略或接受 `Authorization: Bearer ...` 时才可用。更稳妥的代码改动是：只在配置了 key 时添加 Authorization header，并仍对需要鉴权的远端 provider 保留必填检查。

还需注意：

- `.env.example` 当前默认指向 `https://uni-api.cstcloud.cn/v1`。复制后若不改，PDF 证据会被发送到远端服务，并非离线运行。
- `.env.example` 预设的 fallback 模型名是 CSTCloud 模型名；本地服务若没有这些模型，应清空 fallback 或换成真实可用的本机模型 ID。若任一 fallback base URL 仍指向远端，外联仍可能发生。
- Agent B 的 `chat_template_kwargs={"enable_thinking": false}` 是非标准扩展字段；本地 server/model 未明确支持时应删除/置空。`seed` 也应保持 unset，除非该服务支持。
- `--list-models` 使用 `/models` 且也要求 API key。若本地服务不实现 `/models`，可直接配置确切模型 ID并先做一次单文档调用；不能把模型目录查询失败误当作 chat 接口不可用。
- 若 Step 4 运行于 Docker/WSL/另一台工作站，`127.0.0.1` 指向运行脚本的容器/系统自身，不一定是模型服务所在主机；须使用两者可达的本地网络地址，并控制防火墙范围。

## 四、扩展 PDF 的本地前处理依赖与路径限制

Step 4 API 脚本**不直接读取原始 PDF**。它读取当前 `evidence_blocks.jsonl` 与 Stage 03 的固定目录索引；`--all` 只处理当前索引中出现的 `doc_id`。扩展 PDF 还需先在本机完成解析/分块，再生成可追溯 evidence blocks 与 BM25/dense 索引。

当前 Stage 03 组件有两项离线/版本化限制：

1. `step3_hybrid_retrieval.py` 在每个查询时惰性加载 `fastembed.TextEmbedding(model_name="BAAI/bge-small-en-v1.5")`。当前索引虽已保存文档向量，但每个 query 仍需要 query embedding；若该权重未缓存，FastEmbed 可能尝试从网络取得。严格离线前应预装依赖并缓存/随项目提供该模型文件，且确认运行时不触发下载。
2. Step 3 builder / `HybridIndex` 将 evidence blocks、dense index、BM25 index 和 manifest 路径写死在现有 Stage 03 目录。重新建索引会写固定路径；当前 Step 4 也没有 `--index-dir` 或 `--evidence-path` 参数。扩展语料前需增加版本化索引目录/可配置路径，不能为了让新 PDF 被 `--all` 发现而静默覆盖当前索引或固定路径 manifest。

在本次检查中，现有5篇的 Stage 03 索引文件和 schema 文件均存在；这只能支持当前 pilot 的文件完整性检查，不代表扩展 PDF 的新索引已经生成。

## 五、与当前研究范围及审计要求的冲突/风险

### P0 — D03 公式范围

`step4_api_batch_extraction.py`：

- `load_schema()` 固定读取 `01_Prompt与Schema注册/schema_v2.json`，文件内版本是 v1.1；没有加载 `schema_v1.2.json`。
- A/B system prompts 内含 D03 方程抽取/核验指令；Agent B 有 equation check；输出结构包含 `equation_detail`。
- 编排按 schema 的所有维度调用 Agent A/B，未把 D03 作为 `Not_Analyzed_Out_Of_Scope` 范围状态跳过。

所以即使换成全本地模型，当前脚本仍会把公式内容纳入 prompt 和结论。**在保持现行范围时必须先制作 text-only v1.2 分支**：加载经批准的 v1.2 schema/prompt；D03 写固定范围状态而不调用模型；D01/D02 只用可独立成立的文字；D04–D10 沿用定义时明确版本与继承来源。

### P0 — 输出覆盖/运行清单合并

API 编排器用固定 `产出/` 路径按 `doc_id` 以写入模式保存 pass1/pass2/revision/verified 文件；再次处理同一 `doc_id` 会覆盖对应 JSON。运行清单则以追加模式写入。重新运行可能出现“新 JSON + 多轮混在一起的 manifest”，不利于逐版追溯。正式扩展批次前应改为唯一 `run_id`/版本子目录，或检测到同名输出时拒绝运行。

### P1 — 上下文与结果完整性

- Coverage pass 会把整篇论文的所有 evidence block 放进 Agent A 和 Agent B prompt。脚本没有按本机模型 context window 做 tokenizer 级预检、分批策略或超限处理；较长论文/较小本地模型可能报 context length error、截断或返回不完整 JSON。
- 现有校验会逐条校验 Agent A 记录，但应再加“必须恰好覆盖预期维度、无重复维度、无缺失维度”的文档级检查，并检查 completion 是否因 token 上限结束；不能仅凭输出文件名 `_verified_10d.json` 推定10维齐全。
- 本地 A/B “不同模型”标记只比较 `(provider, model)` 字符串。不同别名可能指向相同权重/模型家族；若结果要声称交叉模型核验，需核对实际 checkpoint/版本并如实披露同一本地服务栈。

## 六、建议的 Go/No-Go 顺序

**当前判定：NO-GO for production run with this script unchanged.**

1. 新建独立的 `v1.2 text-scope local API` 编排版本，不覆盖本脚本；修正 D03 处理、prompt/schema 版本与执行 manifest。
2. 增加真正的 local-only 配置/防护：验证 A/B 主 endpoint 与 fallback 均为本机/批准的局域网；避免示例中 CSTCloud 远程 endpoint 被误用；按后端协议处理可选 API key 和非标准扩展字段。
3. 为 Stage 03 增加版本化索引路径与显式参数；把新 PDF 的解析、分块、索引结果放入新批次目录，保留旧版 B001 文件/索引/manifest。
4. 安装 requirements，并在任何断网前缓存 FastEmbed query encoder 和本地 LLM 权重；记录 Python/依赖/模型版本与 hashes。
5. 加入 prompt token 预检、文档级 10维完整性检查、`run_id` 输出隔离和同名拒绝覆盖。
6. 在用户本机的真实本地模型服务上先跑一个单 PDF 文本范围 pilot；确认 endpoint 确为本机、运行时无外网依赖、D03 未进入模型输入、证据 ID 可回溯、输出不覆盖旧数据。通过后才批量跑扩展 PDF。

**本次核验没有对以上源码作改动。**本地 mock 测试证明 API client 的传输协议可以连到 localhost；它不证明真实本地模型的生成质量或整条 Step 1–4 离线流水线已经完成验证。