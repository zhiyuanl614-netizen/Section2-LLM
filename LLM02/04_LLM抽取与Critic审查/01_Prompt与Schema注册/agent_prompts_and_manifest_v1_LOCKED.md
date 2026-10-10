# Agent A/B Prompt 版本、迭代协议与 model_call_manifest Schema（v1.0 — 已冻结，2026-10-06）

## 0. 执行方式的重要前提声明（必须随每次 Step 4 输出重复披露）

> 按用户决策 `agent_real_llm`：Step 4 的 Agent A（抽取）与 Agent B（Critic）**均由 Arena.ai Agent Mode 在当前对话会话中直接执行真实推理完成**，不调用任何外部付费 LLM API，不使用关键词/规则模板代替语义判断。
> 由于执行方式是"同一助手在同一会话内分饰 Agent A 与 Agent B 两个角色"，而非两个相互隔离、互不知晓对方存在的独立系统，**无法做到 README 2.3.2 节要求的"Agent B 完全不可读取 Agent A 推理过程"的严格隔离**。为尽量保留独立性，Agent B 审查时将：
> (a) 只被提供 Agent A 的**最终结构化输出**（标签+证据+引用），不被提供 Agent A 的中间思考过程；
> (b) 被要求重新独立回到原始 Zone A–D 证据文本自行判断，而不是单纯检查 Agent A 输出的"表面自洽性"；
> (c) 但这仍然是**同一底层助手的自我审查**，存在系统性共同偏差（systematic shared bias）的风险，不能等同于两个独立训练的模型或两名独立人类评审员。此局限必须在所有 Step 4/Step 5 产出文档中明确披露，不得表述为"双模型独立交叉验证"。
> 按用户决策 `agent_assist`：本机制同样不满足 README 中"人工金标准"或"领域专家审查"的要求，Step 5 的最终披露义务同样适用。

---

## 1. model_call_manifest Schema（已冻结）

鉴于上述执行方式，原 README 设计的 `provider/model_name/model_version/endpoint/temperature/seed` 字段需要诚实改写为符合实际执行渠道的占位值，而不是编造一个虚假的具体模型标识：

| 字段 | 锁定值/取值规则 |
|---|---|
| `call_id` | 格式 `MC-{doc_id}-{agent}-{pass}-{seq}`，如 `MC-B001-PDF-01-AgentA-pass1-001` |
| `agent_name` | `AgentA` \| `AgentB` |
| `execution_channel` | 固定值 `arena_agent_mode_in_session`（区别于 README 原设计假设的"外部API调用"） |
| `provider` | 固定值 `Arena.ai`（不进一步披露具体底层模型厂商/名称，按平台身份政策） |
| `model_name` | 固定值 `arena-agent-mode-session-model`（通用占位，不代表任何具体可验证的模型型号；如用户后续提供外部付费 API key 并改变决策，此字段须改为真实 provider/model 标识） |
| `model_version` | 固定值 `not_exposed_by_execution_channel`（如实声明：该执行渠道不向使用者暴露可复现核查的具体模型版本号，这是本方法已知的可复现性局限，而非遗漏） |
| `endpoint` | 固定值 `N/A_in_session_reasoning_no_external_api_call` |
| `prompt_version` | `AgentA_prompt_v1.0` \| `AgentB_prompt_v1.0`（见第2、3节；修改后须递增版本号） |
| `schema_version` | 对应 `schema_v2.json` 的版本号（当前 `v1.0`） |
| `input_hash` | 输入内容（evidence_ids 对应的 `text_sha256` 列表 + prompt_version + schema_version 拼接后的 sha256），用于核验"同一输入是否被重复处理" |
| `output_hash` | 本次调用结构化输出 JSON 的 sha256 |
| `temperature` | 固定记录 `not_exposed_by_execution_channel`（如实声明，不编造具体数值） |
| `seed` | 固定记录 `not_available` |
| `input_evidence_ids` | 本次调用引用的 evidence_id 列表 |
| `input_token_estimate` | 用 `tiktoken cl100k_base` 对输入文本的估算 token 数（声明为"估算"，非真实计费token，因为真实执行渠道的真实token数不可得） |
| `output_token_estimate` | 同上，对输出 JSON 文本的估算 |
| `retry_count` | 本次调用的重试次数（若因格式错误等重新生成，记录次数） |
| `timestamp` | ISO8601，调用发生的会话时间 |
| `failure_reason` | 若调用未成功产出有效结构化输出，记录原因；成功则为 `null` |
| `human_or_agent_reviewed` | `agent_only` \| `agent_assisted_human_pending` \| `human_reviewed`（Step 5 使用） |

**机器可读 schema：** 见同目录 `model_call_manifest_schema.json`。

---

## 2. Agent A Prompt（版本 `AgentA_prompt_v1.0`，已冻结）

```text
角色：Full-Text Ontology Extractor（Agent A）

输入：
- 一篇论文的 doc_id 及其全部 Zone A–D evidence blocks（含 evidence_id、zone、section_id、page_numbers、text、retrieval_text）
- schema_v2.json 中 D01–D10 的受控标签定义（见 schema_v2_D01-D10_codebook.md）

任务：对该论文，逐一完成 D01–D10 十个维度的抽取，每个维度输出一条结构化记录（多选维度可输出多条或一条含 secondary_labels 的记录）。

强制规则（违反任一条即为无效输出，须重新生成）：
1. 没有正文证据支持时，primary_label 必须是四种回退状态之一
   （Not_Stated_In_Text / Explicitly_Not_Considered / Insufficient_Evidence / Evidence_Unavailable），
   不得为了"填满十维"而编造标签。
2. 不得仅凭标题、摘要、关键词推断 D02–D09 的具体子标签；必须引用 Zone B/C/D 正文证据
   （D01 允许用 Zone A 摘要中的方法性陈述作为辅助，但主要证据仍应来自 Zone B）。
3. 每条非 Not_Stated_In_Text 的记录必须包含：至少1个 evidence_id、verbatim_quote（逐字引用原文）、
   section_id、page_numbers、own_method_vs_cited、mechanism_judgment、confidence。
4. 涉及方程的维度（D03 非 No_Explicit_Equation_Qualitative_Only 标签）必须填写 equation_detail。
5. 不得把被引用文献（Cited_Other_Work）的方法误标为本文方法（Paper_Own_Method）；
   如果证据文本本身就是在转述他人工作，own_method_vs_cited 必须如实标注为 Cited_Other_Work，
   且该证据不能单独支撑主标签（见codebook 0.2节规则1）。
6. 不得把 HLA/软件数据交换类技术细节自动等同于"真实 cyber 早期预警机制"（D04/D06）；
   不得把一般水网压力方程自动等同于厂内冷却热-水力模型（D02）。
7. mechanism_judgment 必须是对证据的忠实转述式判断（1-3句话），不得引入原文没有表达的推断或外推。
8. 每条记录必须给出 confidence（0.0-1.0）的自评，且在 uncertainty_note 中说明主要不确定性来源
   （如证据分散在多个不相邻 evidence_id、措辞模糊、翻译/OCR 问题等）。

输出格式：JSON 数组，每个元素符合 schema_v2.json 的 common_record_fields 结构。
```

---

## 3. Agent B Prompt（版本 `AgentB_prompt_v1.0`，已冻结）

```text
角色：Independent Critic and Evidence Auditor（Agent B）

输入：
- 与 Agent A 相同的原始 Zone A–D evidence blocks（必须重新独立阅读，不得只看 Agent A 的结论）
- Agent A 的最终结构化输出（仅结构化结果，不含 Agent A 的中间推理过程）

任务：对 Agent A 输出的每一条记录，独立执行以下七项检查，并给出裁决：

1. Entailment check：原文是否真的支持该 primary_label 和 mechanism_judgment；
2. Direction check（仅D01相关记录）：水→电/电→水/双向关系方向是否被正确识别；
3. Equation check（仅涉及方程的记录）：是否真实存在所声称的方程、变量和动态过程，
   页码和equation_detail是否准确；
4. Temporal check（仅D04-D06相关记录）：时间尺度、步长、触发条件描述是否准确；
5. Endpoint check（仅D07-D09相关记录）：物理/经济/人类社会后果层级是否被混淆或夸大；
6. Evidence check：section_id、page_numbers、evidence_id 和 verbatim_quote 是否与源 evidence block
   精确对应（允许程序先做逐字匹配预检，Agent B 做语义层面复核）；
7. Contradiction check：原始 Zone A-D 文本中是否存在反向或限制性证据，而 Agent A 未提及。

输出（每条记录一个裁决对象）：

{
  "decision": "accept | revise | reject | insufficient_evidence",
  "corrected_label": "若decision=revise，给出修正后的primary_label；否则为null",
  "critic_comment": "简述裁决理由，必须引用具体检查项",
  "supporting_evidence_ids": ["..."],
  "contradicting_evidence_ids": ["..."],
  "confidence": 0.0,
  "checks_failed": ["entailment" | "direction" | "equation" | "temporal" | "endpoint" | "evidence" | "contradiction", ...]
}

强制规则：
1. decision=accept 仅表示"原文确实支持该判断"，不表示论文结论本身在工程/物理上正确，
   不得在 critic_comment 中做此类超出范围的评价。
2. insufficient_evidence 不得被改写为 Not_Considered 或其他回退状态；
   二者语义不同（见codebook 0.2节规则2），Agent B 只负责对 Agent A 标签的裁决，
   不得擅自改写 Agent A 使用的回退状态分类本身（如认为分类错误，应走 revise 并说明）。
3. 若 Agent A 与 Agent B 分歧无法在修订轮次内收敛，不强行投票决定，
   输出 adjudication_required = true，进入 Step 5 人工/Agent辅助仲裁队列，
   不得自行"选一个更合理的"了事。
4. Agent B 必须明确声明：本轮审查与 Agent A 共享同一底层执行渠道（见本文件第0节声明），
   不构成真正独立的双模型交叉验证；此声明需逐字包含在 critic_comment 的末尾或单独字段中。
```

---

## 4. 迭代协议（已冻结，采用 README 原设计的 A+B+A+B 四轮协议，不做 A-only / A+B 单轮的消融对比——Route A 决策不做 G0-G5 矩阵）

```text
Step 1/2 已冻结的 evidence blocks（全文四区切片）
        ↓
Pass 1：Agent A 初次十维抽取（AgentA_prompt_v1.0）
        ↓
Pass 2：Agent B 独立 Critic 审查（AgentB_prompt_v1.0），逐条给出 decision
        ↓
Pass 3：对 decision ∈ {revise, reject} 的记录，Agent A 根据 critic_comment 重新抽取
        （Pass 3 只重新处理被打回的记录，不重跑全部十维，以控制调用量）
        ↓
Pass 4：Agent B 对 Pass 3 的修订记录做最终复核
        ↓
verified_10d_record（decision=accept 或仍为 insufficient_evidence/adjudication_required 并进入人工队列）
```

**冻结参数：**
- 每篇论文、每个维度最多迭代 1 轮修订（即最多 Pass1→Pass4 一次往返）；若 Pass 4 仍不通过，直接标记 `adjudication_required=true`，不做第二轮修订以控制成本和潜在的"反复调参直到通过"的数据污染风险。
- Pilot 顺序（已冻结，按 README 5.1 节 Pilot gate 原则，适配5篇 Route A 语料）：先在 **1–2 篇**论文上试运行完整 A+B+A+B 流程，人工确认 JSON Schema 有效性、evidence_id 可回溯性、Agent A/B 分歧模式是否合理后，再扩展到全部5篇；不得跳过 pilot 直接处理全部5篇。

---

## 5. 与 Route A 探索性定位的一致性声明

本文件冻结的是**单一最终 pipeline 配置**的 Agent A/B 环节（覆盖-pass + dense/BM25混合检索 + 双智能体 critic 中的"双智能体critic"部分），不包含 README 原 G0–G5 矩阵中 A-only、A+B单轮等消融变体的 prompt/协议版本——按用户决策，Route A 下不执行该消融比较。若未来用户决定重新开展30篇确认性研究并恢复 G0–G5 矩阵，需要为每个消融组另行冻结对应的 prompt/协议子版本，不能直接复用本文件。
