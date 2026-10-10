(() => {
  const state = {
    status: null, documents: [], directions: [], lastBrief: null, graph: null,
    remoteApiAllowed: false, workflowEnabled: false, runs: [], currentRun: null,
    selectedWorkflowStage: null, figuresLoaded: false,
  };
  const CSTCLOUD_BASE_URL = "https://uni-api.cstcloud.cn/v1";
  const $ = (id) => document.getElementById(id);
  const make = (tag, className = "", text = null) => {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== null) node.textContent = String(text);
    return node;
  };
  const esc = (value) => String(value ?? "");
  let toastTimer;

  async function api(path, options = {}) {
    const response = await fetch(path, { credentials: "same-origin", ...options });
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) throw new Error(typeof data === "object" ? (data.error || `HTTP ${response.status}`) : `HTTP ${response.status}`);
    return data;
  }

  function toast(message) {
    const node = $("toast");
    node.textContent = message;
    node.classList.add("show");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove("show"), 2600);
  }

  function updateRemoteApiState() {
    const provider = $("apiProvider");
    const base = $("apiBaseUrl");
    const model = $("apiModel");
    const key = $("apiKey");
    const toggle = $("remoteGenerateToggle");
    const note = $("remoteGenerateNote");
    const available = Boolean(state.remoteApiAllowed);
    if (!provider || !base || !model || !key || !toggle) return;

    const cstcloud = provider.value === "cstcloud";
    base.readOnly = cstcloud;
    base.placeholder = cstcloud ? CSTCLOUD_BASE_URL : "https://api.example.com/v1";
    if (cstcloud && !base.value.trim()) base.value = CSTCLOUD_BASE_URL;
    const configured = Boolean(base.value.trim() && model.value.trim() && (!cstcloud || key.value.trim()));
    toggle.disabled = !available || !configured;
    if (toggle.disabled) toggle.checked = false;

    if (available) {
      $("apiAvailability").textContent = "本机 loopback 可配置 · 默认不发送";
      $("apiAvailabilityTitle").textContent = "只在明确勾选并提交单次问答后调用外部服务";
      note.textContent = configured ? "配置完成 · 仍需本次单独勾选" : "先设置 Base URL、模型 ID 与 CSTCloud Key";
      if (cstcloud && !key.value.trim()) note.textContent = "CSTCloud 目录查询和问答都需要 API Key";
    } else {
      $("apiAvailability").textContent = "共享预览禁用凭据输入与外部请求 · 请在本机启动";
      $("apiAvailabilityTitle").textContent = "不要在共享预览中输入 API Key";
      note.textContent = "API 配置只在 127.0.0.1 本机启动时开放";
    }
    [provider, base, model, key].forEach((field) => { field.disabled = !available; });
    const loadButton = $("loadModelsButton");
    if (loadButton) loadButton.disabled = !available || !base.value.trim() || (cstcloud && !key.value.trim());
    const openButton = $("openApiSettings");
    if (openButton) openButton.disabled = false;
    const topButton = $("modelSettingsButton");
    if (topButton) topButton.disabled = false;
    $("networkModeChip").lastChild.textContent = ` ${toggle.checked ? "本次调用 API" : "默认离线"}`;
  }

  function showView(name) {
    document.querySelectorAll(".view").forEach((view) => view.classList.toggle("active", view.id === `view-${name}`));
    document.querySelectorAll(".nav-item").forEach((button) => button.classList.toggle("active", button.dataset.view === name));
    const names = { search: "证据检索", graph: "证据图谱", workflow: "阶段工作流", architecture: "项目架构", figures: "图表图库", library: "文献库", about: "范围与状态" };
    $("currentSection").textContent = names[name] || "平台";
    if (name === "graph") loadGraph();
    if (name === "library") renderDocuments();
    if (name === "workflow") loadRuns();
    if (name === "figures") loadFigures();
  }

  function setStatus(status) {
    state.status = status;
    $("statDocs").textContent = String(status.corpus_size ?? "—").padStart(2, "0");
    $("statBlocks").textContent = String(status.evidence_block_count ?? "—");
    $("statEdges").textContent = String(status.graph_edge_count ?? "—");
    $("sideDocCount").textContent = String(status.corpus_size ?? "—");
    $("sideChunkCount").textContent = String(status.evidence_block_count ?? "—");
    $("releaseShort").textContent = (status.release_id || "").replace("B001-", "");
    const configured = Boolean(status.local_chat?.configured);
    $("chatStatus").textContent = configured ? `已配置 · ${status.local_chat.model || "本地模型"}` : "未配置";
    const toggle = $("generateToggle");
    const note = $("generateToggleNote");
    toggle.disabled = !configured;
    note.textContent = configured ? "显式启用后才调用本机模型" : "默认关闭 · 当前未配置";
    state.remoteApiAllowed = Boolean(status.external_api?.allowed);
    state.workflowEnabled = Boolean(status.local_workflows?.enabled);
    const missingStep2 = status.local_workflows?.step02_missing_dependencies || [];
    $("workflowAvailability").textContent = !state.workflowEnabled
      ? "共享预览禁用上传与阶段运行"
      : (missingStep2.length ? `loopback 已开放 · Step 02 缺少 ${missingStep2.join("、")}` : "loopback · 本机隔离工作流已开放");
    $("uploadStatus").textContent = state.workflowEnabled ? "仅本机隔离 run" : "预览中禁用";
    updateRemoteApiState();
    $("aboutRelease").textContent = status.release_id || "未识别 release";
    renderReleaseFacts(status);
  }

  function renderReleaseFacts(status) {
    const target = $("releaseFacts");
    target.replaceChildren();
    const facts = [
      ["Release 状态", status.release_status],
      ["语料规模", `${status.corpus_size} 篇 / ${status.evidence_block_count} 个证据块`],
      ["分析记录", `${status.active_record_count} 条 / 9 个活动维度`],
      ["图谱关系", `${status.graph_edge_count} 条追溯关系`],
      ["Dense 文档向量", status.dense?.index_present ? `${status.dense.index_model} · 已随 release 保存` : "未找到"],
      ["Dense 查询编码器", status.dense?.query_encoder_enabled ? "显式启用（仅本地缓存）" : "未启用；不会自动下载"],
      ["生成模型", status.local_chat?.configured ? `${status.local_chat.model} · loopback only` : "未配置 · 证据包模式"],
      ["外部 API", status.external_api?.allowed ? "仅显式单次 QA · Key不保存" : "当前预览禁用 · 本机 loopback 开放"],
      ["正式 release", "只读；新 PDF 写入隔离 run"],
      ["网页工作流", status.local_workflows?.enabled ? "Step 02 + BM25-only Step 03" : "共享预览禁用上传与阶段运行"],
      ["批量云端证据", "未获默认授权；Step 04 runner 尚未接入"],
    ];
    for (const [label, value] of facts) {
      const row = make("div", "fact-row");
      row.append(make("span", "", label), make("b", "", value));
      target.append(row);
    }
  }

  function populateDocFilter() {
    const select = $("docFilter");
    for (const doc of state.documents) {
      const option = document.createElement("option");
      option.value = doc.doc_id;
      option.textContent = `${doc.doc_id} · ${String(doc.title || "").slice(0, 38)}`;
      select.append(option);
    }
  }

  function renderDocuments() {
    const grid = $("documentGrid");
    if (!grid) return;
    grid.replaceChildren();
    $("libraryCount").textContent = `${state.documents.length} 篇`;
    for (const doc of state.documents) {
      const card = make("article", "document-card");
      const top = make("div", "document-card-top");
      top.append(make("div", "document-icon", "▤"));
      const info = make("div");
      info.append(make("div", "document-id", doc.doc_id));
      info.append(make("h3", "document-title", doc.title || doc.source_filename));
      info.append(make("div", "document-authors", doc.authors || "作者信息未提供"));
      top.append(info);
      const meta = make("div", "document-metadata");
      meta.append(make("span", "", doc.pub_year || "年份待核"));
      meta.append(make("span", "", `${doc.total_pages || "—"} 页`));
      meta.append(make("span", "", `${doc.evidence_block_count || 0} 个证据块`));
      if (doc.journal) meta.append(make("span", "", doc.journal));
      const footer = make("div", "document-card-footer");
      const hash = make("small", "", `SHA-256 · ${(doc.pdf_sha256 || "").slice(0, 12)}…`);
      const open = make("a", "pdf-link", "打开原始 PDF ↗");
      open.href = doc.pdf_url;
      open.target = "_blank";
      open.rel = "noopener noreferrer";
      footer.append(hash, open);
      card.append(top, meta, footer);
      grid.append(card);
    }
  }

  function renderNotices(notices, extraError = null) {
    const target = $("noticeStack");
    target.replaceChildren();
    const all = [...(notices || [])];
    if (extraError) all.unshift(`本地生成未完成：${extraError}。已保留检索证据包。`);
    for (const item of all) {
      const note = make("div", extraError && item.includes("生成未完成") ? "notice" : "notice info", item);
      target.append(note);
    }
  }

  function renderResults(search) {
    const list = $("resultsList");
    list.replaceChildren();
    const hits = search.hits || [];
    $("resultMeta").textContent = search.out_of_scope ? "超出公式分析范围" : `${hits.length} 条证据 · 通道：${(search.active_channels || []).join(" + ") || "—"}`;
    renderNotices(search.notices || [], null);
    if (search.out_of_scope) {
      const empty = make("div", "empty-state");
      empty.append(make("div", "empty-glyph", "!"), make("strong", "", "该问题超出当前分析范围"), make("p", "", search.notice || "公式转录、推导和方程类型分析不在当前研究范围内。"));
      list.append(empty);
      return;
    }
    if (!hits.length) {
      const empty = make("div", "empty-state");
      empty.append(make("div", "empty-glyph", "⌕"), make("strong", "", "没有找到匹配证据"), make("p", "", "可尝试改用英文领域术语，或在“范围与状态”查看已知检索边界。"));
      list.append(empty);
      return;
    }
    hits.forEach((hit, index) => {
      const card = make("article", "result-card");
      const top = make("div", "result-card-top");
      top.append(make("span", "rank-badge", String(index + 1).padStart(2, "0")));
      const title = make("div", "result-title");
      const id = make("div", "evidence-id", hit.evidence_id);
      const docTitle = make("div", "result-doc-title", `${hit.doc_id} · ${hit.title || "来源文献"}`);
      const meta = make("div", "result-meta");
      const pages = Array.isArray(hit.pages) && hit.pages.length ? `PDF 页 ${hit.pages.join(", ")}` : "页码待核";
      meta.append(make("span", "meta-pill", pages));
      if (hit.section_id || hit.section_title) meta.append(make("span", "meta-pill", `${hit.section_id || ""} ${hit.section_title || ""}`.trim()));
      if (hit.formula_layout_risk) meta.append(make("span", "meta-pill warn", "公式版面风险 · 未解析"));
      title.append(id, docTitle, meta);
      top.append(title);
      card.append(top);
      if (hit.channels?.length) {
        const channels = make("div", "channel-row");
        for (const channel of hit.channels) channels.append(make("span", "channel-tag", channel));
        card.append(channels);
      }
      card.append(make("p", "result-excerpt", hit.text));
      const bottom = make("div", "result-bottom");
      const refs = make("div", "record-ref");
      for (const ref of hit.record_refs || []) {
        const pending = ref.doc_id === "B001-PDF-03" && ref.dimension_id === "D02";
        refs.append(make("span", `record-chip${pending ? " pending" : ""}`, `${ref.dimension_id} · ${ref.primary_label}${pending ? " · 未裁定" : ""}`));
      }
      const open = make("a", "open-source", "查看原文 ↗");
      open.href = hit.pdf_url;
      open.target = "_blank";
      open.rel = "noopener noreferrer";
      bottom.append(refs, open);
      card.append(bottom);
      card.addEventListener("click", (event) => {
        if (event.target.closest("a")) return;
        openEvidenceDetail(hit.evidence_id);
      });
      list.append(card);
    });
  }

  function renderBrief(packet, generated = null, generationError = null) {
    const body = $("answerBody");
    body.replaceChildren();
    const content = generated?.answer || packet?.answer_text || "检索完成。";
    const intro = make("p", "brief-intro", content);
    body.append(intro);
    if (generated?.citations?.length) {
      const modelLine = make("div", "brief-citation");
      const isRemote = generated.execution_mode === "external_api";
      const sourceLabel = isRemote ? `EXTERNAL API · ${generated.provider || "provider"}` : "LOCAL MODEL";
      modelLine.append(make("b", "", `${sourceLabel} · ${generated.model || ""}`), make("span", "", `生成状态：${generated.status}；引用编号已校验，语义支持未自动验证。`));
      body.append(modelLine);
    }
    const citations = packet?.citations || [];
    if (citations.length) {
      for (const citation of citations.slice(0, 4)) {
        const box = make("div", "brief-citation");
        box.append(make("b", "", `[${citation.citation_id}] · ${citation.doc_id} · p.${(citation.pages || []).join(", ") || "?"}`));
        box.append(make("span", "", citation.quote));
        box.addEventListener("click", () => openEvidenceDetail(citation.citation_id));
        box.tabIndex = 0;
        box.setAttribute("role", "button");
        body.append(box);
      }
    }
    if (generationError) {
      body.append(make("div", "notice", `生成未完成：${generationError}。已保留本地检索证据包。`));
    }
    if (packet?.notices?.length) {
      const note = make("p", "brief-intro", packet.notices.join(" "));
      body.append(note);
    }
    $("copyBrief").disabled = false;
    state.lastBrief = `${content}\n\n${citations.map((c) => `[${c.citation_id}] ${c.doc_id} p.${(c.pages || []).join(", ")}\n${c.quote}`).join("\n\n")}`;
  }

  async function submitQuery(queryOverride = null) {
    const query = (queryOverride ?? $("queryInput").value).trim();
    if (!query) {
      toast("先输入一个研究问题或检索词。");
      return;
    }
    $("queryInput").value = query;
    const button = document.querySelector(".submit-search");
    button.disabled = true;
    button.textContent = "检索中…";
    const useRemoteApi = $("remoteGenerateToggle").checked;
    $("resultMeta").textContent = useRemoteApi ? "本机检索后按本次授权调用外部 API…" : "正在本地检索证据与来源…";
    $("resultsList").replaceChildren();
    const loading = make("div", "empty-state loading-state");
    loading.append(make("div", "empty-glyph", "···"), make("strong", "", "正在检索"), make("p", "", useRemoteApi ? "检索在本机完成；本次问题与最多5条非公式风险证据将发送至所选 API。" : "本次请求在本机处理，不访问外部网络。"));
    $("resultsList").append(loading);
    try {
      const payload = {
        query,
        top_k: 8,
        mode: $("modeFilter").value,
        direction: $("directionFilter").value,
        doc_id: $("docFilter").value,
        generate: $("generateToggle").checked,
        ...(useRemoteApi ? { remote_api: {
          provider: $("apiProvider").value,
          base_url: $("apiBaseUrl").value.trim(),
          model: $("apiModel").value.trim(),
          api_key: $("apiKey").value,
        } } : {}),
      };
      const result = await api("/api/qa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      renderResults(result.search || {});
      renderBrief(result.evidence_packet || {}, result.generated_answer || null, result.generation_error || null);
      if (result.search?.query_expansions?.length) {
        const exp = result.search.query_expansions.join(" · ");
        const note = make("div", "notice info", `检索词扩展（仅用于召回）：${exp}`);
        $("noticeStack").append(note);
      }
    } catch (error) {
      renderNotices([], null);
      $("resultMeta").textContent = "检索失败";
      $("resultsList").replaceChildren(make("div", "empty-state", `无法检索：${error.message}`));
      toast(`本地请求失败：${error.message}`);
    } finally {
      button.disabled = false;
      button.innerHTML = "检索 <span>→</span>";
    }
  }

  async function loadGraph() {
    const direction = $("graphDirection").value;
    try {
      const graph = await api(`/api/graph?direction=${encodeURIComponent(direction)}`);
      state.graph = graph;
      window.renderEvidenceGraph?.(graph);
    } catch (error) {
      toast(`无法加载图谱：${error.message}`);
    }
  }

  async function openEvidenceDetail(evidenceId) {
    try {
      const item = await api(`/api/evidence/${encodeURIComponent(evidenceId)}`);
      window.openGraphNodeDetails?.({ ...item, id: `evidence:${item.evidence_id}`, type: "evidence", label: item.evidence_id }, item.record_refs || []);
      showView("graph");
    } catch (error) {
      toast(`无法加载证据：${error.message}`);
    }
  }

  function openGraphNodeDetails(node, relatedRecords = []) {
    const panel = $("graphDetail");
    if (!panel || !node) return;
    panel.replaceChildren();
    panel.append(make("div", "detail-kicker", (node.type || "node").toUpperCase().replaceAll("_", " ")));
    panel.append(make("h3", "detail-title", node.title || node.label || node.id));

    if (node.type === "evidence") {
      const doc = state.documents.find((item) => item.doc_id === node.doc_id);
      panel.append(make("span", "detail-label", "原文证据块"));
      panel.append(make("div", "detail-quote", node.text || ""));
      panel.append(make("span", "detail-label", "来源定位"));
      panel.append(make("div", "detail-body", `${node.doc_id || ""} · ${doc?.title || ""}\n${(node.pages || node.page_numbers || []).map((p) => `PDF p.${p}`).join(" · ")}\n${node.section_id || ""} ${node.section_title || ""}`));
      if (node.formula_layout_risk) panel.append(make("span", "detail-badge pending", `公式版面风险 ${node.formula_layout_risk_score ?? ""} · 未做解析`));
      for (const directionId of node.direction_refs || []) panel.append(make("span", "detail-badge", `关联方向 ${directionId}`));
      const refs = relatedRecords.length ? relatedRecords : (node.record_refs || []);
      if (refs.length) {
        panel.append(make("span", "detail-label", "关联的先导编码记录（非独立金标准）"));
        for (const record of refs) {
          const pending = record.doc_id === "B001-PDF-03" && record.dimension_id === "D02";
          const badge = make("span", `detail-badge${pending ? " pending" : ""}`, `${record.doc_id} · ${record.dimension_id} · ${record.primary_label || ""}${pending ? " · 未裁定" : ""}`);
          panel.append(badge);
        }
      }
      const link = make("a", "detail-link", "在 PDF 中打开来源页 ↗");
      link.href = node.pdf_url || `/pdf/${node.doc_id}#page=${(node.pages || node.page_numbers || [1])[0]}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      panel.append(link);
    } else if (node.type === "document") {
      panel.append(make("span", "detail-label", "文献元信息"));
      panel.append(make("div", "detail-body", `${node.doc_id}\n${node.year || "年份待核"} · ${node.title || ""}\n${node.doi || "DOI 未提供"}`));
      const link = make("a", "detail-link", "打开原始 PDF ↗");
      link.href = node.pdf_path ? `/${node.pdf_path}` : `/pdf/${node.doc_id}`;
      if (node.pdf_path) link.href = `/pdf/${node.doc_id}`;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      panel.append(link);
    } else if (node.type === "direction") {
      panel.append(make("span", "detail-label", "待证伪/证据挑战的既有候选方向"));
      panel.append(make("div", "detail-body", node.hypothesis_to_test || ""));
      panel.append(make("span", "detail-label", "先导解释（非定论）"));
      panel.append(make("div", "detail-body", node.interpretation || node.pilot_result || ""));
      for (const dim of node.dimensions || []) panel.append(make("span", "detail-badge", dim));
      panel.append(make("span", "detail-badge pending", "5篇先导 · 未确认领域级空白"));
    } else if (node.type === "record") {
      panel.append(make("span", "detail-label", "主标签候选与状态"));
      panel.append(make("div", "detail-body", `${node.primary_label || ""}\n核验状态：${node.verification_status || ""}\n记录来源：${node.record_origin || ""}\n${node.mechanism_judgment || ""}`));
      if (node.doc_id === "B001-PDF-03" && node.dimension_id === "D02") panel.append(make("span", "detail-badge pending", "未裁定；候选标签不代表用户批准"));
    } else if (node.type === "dimension") {
      panel.append(make("span", "detail-label", "操作化分析维度"));
      panel.append(make("div", "detail-body", node.title || "此维度仅用于编码，不单独等于研究发现。"));
    } else {
      panel.append(make("div", "detail-body", node.title || node.label || node.id));
    }
    if (node.status) panel.append(make("span", "detail-label", `状态：${node.status}`));
  }
  window.openGraphNodeDetails = openGraphNodeDetails;

  function openApiSettings() {
    const dialog = $("apiSettingsDialog");
    if (!dialog) return;
    updateRemoteApiState();
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "open");
  }

  function closeApiSettings() {
    const dialog = $("apiSettingsDialog");
    if (dialog?.open && typeof dialog.close === "function") dialog.close();
    else dialog?.removeAttribute("open");
  }

  async function loadModelCatalog() {
    const button = $("loadModelsButton");
    const note = $("modelCatalogStatus");
    const list = $("apiModelList");
    button.disabled = true;
    note.textContent = "正在按本次请求连接服务商 /models；不会发送论文内容…";
    list.replaceChildren();
    try {
      const data = await api("/api/models", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: $("apiProvider").value,
          base_url: $("apiBaseUrl").value.trim(),
          api_key: $("apiKey").value,
        }),
      });
      const models = data.models || [];
      for (const modelId of models) {
        const option = document.createElement("option");
        option.value = modelId;
        list.append(option);
      }
      note.textContent = models.length
        ? `已获取 ${models.length} 个模型 ID；目录只在内存显示，未写入配置文件。`
        : "服务商目录返回为空；可手动输入账号允许使用的精确模型 ID。";
      if (models.length && !$("apiModel").value.trim()) $("apiModel").value = models[0];
      updateRemoteApiState();
    } catch (error) {
      note.textContent = `目录获取失败：${error.message}`;
      toast("没有保存 API Key；可检查本机网络、Key 或服务商模型目录权限。");
    } finally {
      updateRemoteApiState();
    }
  }

  function workflowStatusLabel(status) {
    const labels = {
      awaiting_uploads: "等待 PDF", blocked_awaiting_uploads: "待上传",
      ready: "待运行", completed: "已完成", running: "运行中",
      blocked_missing_dependencies: "缺少依赖", partial_bm25_ready: "BM25部分就绪",
      blocked_pending_step2: "等待 Step 02", not_ready: "未接入",
      failed: "失败 · 保留部分产物", step02_failed: "Step 02 失败",
      ready_for_step02: "可运行 Step 02", ready_for_stage03_bm25: "可运行 Step 03",
      partial_ready_bm25_only: "BM25-only", running_step02: "Step 02 运行中",
      running_stage03: "Step 03 运行中", stage03_failed: "Step 03 失败",
    };
    return labels[status] || status || "未就绪";
  }

  function formatBytes(bytes) {
    const size = Number(bytes || 0);
    if (size < 1024) return `${size} B`;
    if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
    return `${(size / (1024 * 1024)).toFixed(1)} MB`;
  }

  function renderSelectedFiles() {
    const target = $("uploadFileList");
    target.replaceChildren();
    const files = Array.from($("pdfFiles").files || []);
    if (!files.length) {
      target.append(make("span", "", "未选择文件"));
      return;
    }
    for (const file of files) {
      const row = make("div", "upload-file-item");
      row.append(make("strong", "", file.name), make("span", "", formatBytes(file.size)));
      if (!file.name.toLowerCase().endsWith(".pdf")) row.append(make("span", "file-error", "不是 .pdf"));
      target.append(row);
    }
  }

  async function loadRuns(selectRunId = null) {
    if (!state.workflowEnabled) {
      $("runSelect").disabled = true;
      $("createRun").disabled = true;
      $("refreshRuns").disabled = true;
      $("pdfFiles").disabled = true;
      $("uploadPdfs").disabled = true;
      $("workflowAvailability").textContent = "共享预览禁用上传与阶段运行";
      $("currentRunMeta").textContent = "请在本机启动平台（127.0.0.1）以启用 loopback-only 隔离工作流。";
      return;
    }
    $("runSelect").disabled = false;
    $("createRun").disabled = false;
    $("refreshRuns").disabled = false;
    $("pdfFiles").disabled = false;
    try {
      const data = await api("/api/workflows");
      state.runs = data.runs || [];
      const select = $("runSelect");
      const requested = selectRunId || state.currentRun?.run_id || select.value;
      select.replaceChildren();
      const empty = document.createElement("option");
      empty.value = "";
      empty.textContent = "请选择或新建 run";
      select.append(empty);
      for (const run of state.runs) {
        const option = document.createElement("option");
        option.value = run.run_id;
        option.textContent = `${run.label} · ${run.upload_count} 篇 · ${workflowStatusLabel(run.status)}`;
        select.append(option);
      }
      const found = state.runs.some((run) => run.run_id === requested);
      select.value = found ? requested : "";
      if (select.value) await loadRun(select.value);
      else if (!state.currentRun || !state.runs.some((run) => run.run_id === state.currentRun.run_id)) {
        state.currentRun = null;
        renderRun(null);
      }
      const missingStep2 = state.status?.local_workflows?.step02_missing_dependencies || [];
      $("workflowAvailability").textContent = missingStep2.length
        ? `本机隔离工作流 · Step 02 缺少 ${missingStep2.join("、")}`
        : "loopback · 文件与产物保存在本机";
    } catch (error) {
      $("workflowAvailability").textContent = "工作区读取失败";
      $("currentRunMeta").textContent = error.message;
      toast(`无法读取本机隔离工作区：${error.message}`);
    }
  }

  async function createWorkflowRun() {
    if (!state.workflowEnabled) return toast("共享预览不能创建运行；请使用本机 127.0.0.1 启动。 ");
    const label = `隔离 PDF run · ${new Date().toLocaleString()}`;
    try {
      const run = await api("/api/workflows", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ label }),
      });
      state.currentRun = run;
      await loadRuns(run.run_id);
      toast("已创建隔离 run；正式 release 未改动。现在可选择 PDF 上传。 ");
    } catch (error) {
      toast(`创建 run 失败：${error.message}`);
    }
  }

  async function loadRun(runId) {
    if (!runId) {
      state.currentRun = null;
      renderRun(null);
      return;
    }
    try {
      state.currentRun = await api(`/api/workflows/${encodeURIComponent(runId)}`);
      renderRun(state.currentRun);
    } catch (error) {
      toast(`无法读取运行记录：${error.message}`);
    }
  }

  function renderRun(run) {
    state.currentRun = run;
    const uploadButton = $("uploadPdfs");
    const selectedFiles = Array.from($("pdfFiles").files || []);
    uploadButton.disabled = !state.workflowEnabled || !run || !selectedFiles.length || ["running_step02", "running_stage03", "step02_failed"].includes(run.status);
    if (!run) {
      $("currentRunMeta").textContent = state.workflowEnabled ? "尚无选中的运行。" : "本机 loopback 才开放上传与任务执行。";
      $("uploadedList").replaceChildren();
      $("workflowArtifactList").replaceChildren(make("div", "artifact-empty", "当前 run 尚无可查看产物。"));
      $("workflowCanvasTitle").textContent = "阶段结果画布";
      $("workflowCanvasMeta").textContent = "选择或创建一个隔离 run。";
      $("workflowCanvasStamp").textContent = "尚未运行";
      $("workflowCanvasContent").replaceChildren(make("div", "canvas-placeholder", "选择一个 run 和阶段后，在此查看状态及产物。"));
      $("workflowSearchRow").hidden = true;
      $("runStage02").disabled = true;
      $("runStage03").disabled = true;
      $("stageState01").textContent = "等待 PDF";
      $("stageState02").textContent = "等待";
      $("stageState03").textContent = "未就绪";
      document.querySelectorAll("[data-stage-card]").forEach((card) => {
        card.classList.remove("stage-card-active");
        delete card.dataset.status;
      });
      return;
    }
    const uploads = run.uploads || [];
    $("currentRunMeta").textContent = `${run.run_id} · ${uploads.length} 篇 · 状态：${workflowStatusLabel(run.status)} · 正式 release 未改动`;
    const uploadedTarget = $("uploadedList");
    uploadedTarget.replaceChildren();
    if (!uploads.length) {
      uploadedTarget.append(make("div", "artifact-empty", "尚未上传 PDF。上传只登记到当前 run，不会进入正式文献库。"));
    } else {
      for (const item of uploads) {
        const row = make("div", "uploaded-file-row");
        row.append(make("strong", "", item.filename), make("span", "", formatBytes(item.size_bytes)), make("code", "", `SHA-256 ${String(item.sha256 || "").slice(0, 16)}…`));
        uploadedTarget.append(row);
      }
    }
    const stages = run.stages || {};
    const stageKeys = ["01_pdf_registration", "02_pdf_clean_chunk", "03_bm25_index", "04_llm_extract_critic", "05_human_review_metrics", "06_synthesis_frdi", "07_run_figures_tables"];
    stageKeys.forEach((key, index) => {
      const stage = stages[key] || {};
      const stateNode = $(`stageState${String(index + 1).padStart(2, "0")}`);
      if (stateNode) stateNode.textContent = workflowStatusLabel(stage.status);
      const card = document.querySelector(`[data-stage-card="${key}"]`);
      if (card) {
        card.classList.toggle("stage-card-active", key === state.selectedWorkflowStage);
        card.dataset.status = stage.status || "not_ready";
      }
    });
    const stage2 = stages["02_pdf_clean_chunk"] || {};
    const stage3 = stages["03_bm25_index"] || {};
    $("runStage02").disabled = !state.workflowEnabled || !uploads.length || !["ready", "blocked_missing_dependencies"].includes(stage2.status);
    $("runStage02").textContent = stage2.status === "blocked_missing_dependencies" ? "依赖安装后重试 Step 02" : stage2.status === "completed" ? "Step 02 已完成 · 不覆盖" : "确认并运行 Step 02";
    $("runStage03").disabled = !state.workflowEnabled || stage3.status !== "ready";
    $("runStage03").textContent = stage3.status === "partial_bm25_ready" ? "BM25 已生成 · 不覆盖" : "确认并运行 Step 03";
    $("workflowSearchRow").hidden = stage3.status !== "partial_bm25_ready";
    if (state.selectedWorkflowStage && stages[state.selectedWorkflowStage]) openWorkflowStage(state.selectedWorkflowStage);
    else openWorkflowStage("01_pdf_registration");
  }

  function openWorkflowStage(stageId) {
    state.selectedWorkflowStage = stageId;
    const run = state.currentRun;
    const stage = run?.stages?.[stageId];
    const card = document.querySelector(`[data-stage-card="${stageId}"]`);
    document.querySelectorAll("[data-stage-card]").forEach((node) => node.classList.toggle("stage-card-active", node === card));
    const titles = {
      "01_pdf_registration": "01 · PDF 上传与登记",
      "02_pdf_clean_chunk": "02 · PDF 清洗与分块",
      "03_bm25_index": "03 · 本地 BM25 索引",
      "04_llm_extract_critic": "04 · LLM 抽取与 Critic",
      "05_human_review_metrics": "05 · 人工核验与指标",
      "06_synthesis_frdi": "06 · 跨文献综合与 FRDI",
      "07_run_figures_tables": "07 · 图表与章节输出",
    };
    $("workflowCanvasTitle").textContent = titles[stageId] || "阶段结果画布";
    $("workflowCanvasMeta").textContent = stage?.summary || "选择或创建一个 run，并查看此阶段的执行范围。";
    $("workflowCanvasStamp").textContent = run ? workflowStatusLabel(stage?.status) : "尚未运行";
    const artifacts = (run?.artifacts || []).filter((item) => item.stage_id === stageId);
    const list = $("workflowArtifactList");
    list.replaceChildren();
    if (!artifacts.length) {
      list.append(make("div", "artifact-empty", "此阶段尚无已登记产物。"));
    } else {
      for (const artifact of artifacts) {
        const row = make("div", "artifact-row");
        const preview = make("button", "artifact-preview-button");
        preview.type = "button";
        preview.append(make("strong", "", artifact.filename), make("small", "", `${formatBytes(artifact.size_bytes)} · SHA-256 ${String(artifact.sha256 || "").slice(0, 12)}…`));
        preview.addEventListener("click", () => previewArtifact(run.run_id, artifact));
        const download = make("a", "artifact-download", "下载");
        download.href = `/api/workflows/${encodeURIComponent(run.run_id)}/artifacts/${encodeURIComponent(artifact.artifact_id)}`;
        download.textContent = "下载";
        row.append(preview, download);
        list.append(row);
      }
    }
    const content = $("workflowCanvasContent");
    content.replaceChildren();
    if (!run) {
      content.append(make("div", "canvas-placeholder", "新 run 与正式 release 隔离。创建 run 后可上传 PDF 并逐阶段执行。"));
      return;
    }
    const summary = make("div", "canvas-summary");
    summary.append(make("span", "canvas-kicker", `RUN ${run.run_id}`));
    summary.append(make("strong", "", stage?.title || titles[stageId] || "阶段状态"));
    summary.append(make("p", "", stage?.summary || "当前阶段尚未开始。"));
    summary.append(make("div", "canvas-scope-list", `执行状态：${workflowStatusLabel(stage?.status)}\n执行通道：${stage?.execution || "local_only"}\n外部数据发送：${stage?.external_data_sent === true ? "有记录" : "无（此阶段本地运行 / 未运行）"}`));
    content.append(summary);
    if (stage?.missing_dependencies?.length) {
      content.append(make("div", "workflow-warning", `缺少依赖：${stage.missing_dependencies.join("、")}。安装“平台/requirements-local.txt”后可在此 run 重试；本次没有处理 PDF。`));
    }
    if (stage?.not_implemented?.length) {
      content.append(make("div", "workflow-warning", `尚未实现：${stage.not_implemented.join("、")}。当前结果不得称为完整混合索引。`));
    }
    if (stage?.error_code) content.append(make("div", "workflow-warning", `运行状态：${stage.error_code}。部分新 run 文件保留供审查，不会自动删除或覆盖。`));
    if (stage?.log_tail) {
      const details = document.createElement("details");
      details.className = "run-log-details";
      const summaryLine = document.createElement("summary");
      summaryLine.textContent = "查看本阶段日志尾部";
      const pre = document.createElement("pre");
      pre.textContent = stage.log_tail;
      details.append(summaryLine, pre);
      content.append(details);
    }
    const indexReady = run.stages?.["03_bm25_index"]?.status === "partial_bm25_ready";
    $("workflowSearchRow").hidden = !indexReady;
  }

  async function previewArtifact(runId, artifact) {
    const content = $("workflowCanvasContent");
    content.replaceChildren(make("div", "canvas-loading", `正在读取并校验 ${artifact.filename}…`));
    try {
      const data = await api(`/api/workflows/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifact.artifact_id)}?preview=1`);
      content.replaceChildren();
      const header = make("div", "artifact-preview-header");
      header.append(make("strong", "", data.filename), make("span", "", `SHA-256 ${String(data.sha256 || "").slice(0, 16)}…`));
      const pre = make("pre", "artifact-text-preview", data.text || "");
      content.append(header, pre);
      if (data.truncated) content.append(make("div", "notice info", `画布预览限 ${data.max_preview_characters} 字符；可下载完整文件。`));
    } catch (error) {
      content.replaceChildren(make("div", "workflow-warning", error.message));
      toast(`产物预览失败：${error.message}`);
    }
  }

  async function uploadSelectedPdfs() {
    const run = state.currentRun;
    const files = Array.from($("pdfFiles").files || []);
    if (!run || !files.length) return toast("先选择一个隔离 run 和至少一个 PDF。 ");
    if (files.length > 10 || files.some((file) => !file.name.toLowerCase().endsWith(".pdf"))) return toast("最多一次选择10个 .pdf 文件。 ");
    if (files.some((file) => file.size > 50 * 1024 * 1024)) return toast("单个 PDF 不能超过50 MB。 ");
    const list = files.map((file) => `• ${file.name}（${formatBytes(file.size)}）`).join("\n");
    if (!window.confirm(`将以下文件上传到本机隔离 run：\n\n${list}\n\n不会并入正式样本；不会发送到云端。继续？`)) return;
    const button = $("uploadPdfs");
    button.disabled = true;
    let count = 0;
    try {
      for (const file of files) {
        button.textContent = `上传中 ${count + 1}/${files.length}…`;
        await api(`/api/workflows/${encodeURIComponent(run.run_id)}/files?filename=${encodeURIComponent(file.name)}`, {
          method: "POST",
          headers: { "Content-Type": "application/pdf" },
          body: file,
        });
        count += 1;
      }
      $("pdfFiles").value = "";
      renderSelectedFiles();
      await loadRuns(run.run_id);
      toast(`已将 ${count} 篇 PDF 登记到隔离 run；未改动正式 release。`);
    } catch (error) {
      await loadRuns(run.run_id);
      toast(`上传在第 ${count + 1} 个文件中止：${error.message}。已成功登记的文件仍留在此 run。`);
    } finally {
      button.textContent = "上传到当前 run";
      renderRun(state.currentRun);
    }
  }

  async function runWorkflowStage(stageId) {
    const run = state.currentRun;
    if (!run) return toast("先创建或选择隔离 run。 ");
    const stage = run.stages?.[stageId];
    if (!stage) return;
    const stageName = stage.title || stageId;
    const scope = stageId === "02_pdf_clean_chunk"
      ? `将对当前 run 的 ${run.uploads?.length || 0} 篇 PDF 在本机运行 Step 1 切片和 Step 2 分块。不会联网、不会调用模型、不会改动正式5篇样本。`
      : `将对当前 run 的 Step 2 evidence blocks 在本机生成 BM25-only 索引。Dense/图谱未包含；不会联网或发送内容。`;
    if (!window.confirm(`确认运行：${stageName}\n\n${scope}\n\n输出写入新的 run 子目录，不覆盖历史结果。`)) return;
    const button = $(stageId === "02_pdf_clean_chunk" ? "runStage02" : "runStage03");
    button.disabled = true;
    button.textContent = "本机运行中…";
    state.selectedWorkflowStage = stageId;
    try {
      const updated = await api(`/api/workflows/${encodeURIComponent(run.run_id)}/stages/${encodeURIComponent(stageId)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirm: true }),
      });
      state.currentRun = updated;
      renderRun(updated);
      if (updated.stages?.[stageId]?.status === "blocked_missing_dependencies") {
        toast("Step 02 未启动：本机缺少 PDF 解析依赖。请先安装项目依赖。 ");
      } else if (updated.stages?.[stageId]?.status === "failed") {
        toast("阶段未完成；部分新 run 产物已保留供审查。 ");
      } else {
        toast(`${stageName} 阶段已记录；请在结果画布查看状态与产物。`);
      }
    } catch (error) {
      toast(`${stageName} 未运行：${error.message}`);
      await loadRun(run.run_id);
    } finally {
      renderRun(state.currentRun);
    }
  }

  async function searchWorkflowRun(event) {
    event.preventDefault();
    const run = state.currentRun;
    const query = $("workflowQuery").value.trim();
    if (!run || !query) return toast("先输入本地检索词。 ");
    const target = $("workflowSearchResults");
    target.replaceChildren(make("div", "canvas-loading", "本机 BM25 检索中…"));
    try {
      const result = await api(`/api/workflows/${encodeURIComponent(run.run_id)}/search?q=${encodeURIComponent(query)}&top_k=10`);
      target.replaceChildren();
      if (!result.hits?.length) target.append(make("div", "artifact-empty", "没有匹配的本地 BM25 证据。"));
      for (const hit of result.hits || []) {
        const card = make("article", "workflow-hit");
        card.append(make("div", "workflow-hit-meta", `${hit.evidence_id} · ${hit.doc_id} · p.${(hit.pages || []).join(", ") || "?"} · score ${hit.score}`));
        if (hit.formula_layout_risk) card.append(make("span", "detail-badge pending", "公式版面风险 · 原文保留 · 未解析"));
        card.append(make("p", "", hit.text));
        target.append(card);
      }
      for (const notice of result.notices || []) target.append(make("div", "notice info", notice));
    } catch (error) {
      target.replaceChildren(make("div", "workflow-warning", error.message));
    }
  }

  async function loadFigures() {
    if (state.figuresLoaded) return;
    const target = $("figureGrid");
    try {
      const data = await api("/api/figures");
      target.replaceChildren();
      const figures = data.figures || [];
      for (const figure of figures) {
        const card = make("article", "figure-card");
        const head = make("div", "figure-card-head");
        const title = make("div");
        title.append(make("div", "figure-number", figure.figure), make("h2", "", figure.version));
        const status = make("span", `figure-version-tag${figure.status.includes("历史档案") ? " historical" : " provisional"}`, figure.status);
        head.append(title, status);
        const imageLink = document.createElement("a");
        imageLink.href = figure.url;
        imageLink.target = "_blank";
        imageLink.rel = "noopener noreferrer";
        imageLink.className = "figure-image-link";
        const image = document.createElement("img");
        image.src = figure.url;
        image.alt = `${figure.figure} · ${figure.version}`;
        image.loading = "lazy";
        imageLink.append(image);
        card.append(head, imageLink, make("p", "figure-warning", figure.warning));
        target.append(card);
      }
      state.figuresLoaded = true;
      if (!figures.length) target.append(make("div", "empty-state", "未找到固定目录中的图表文件。"));
    } catch (error) {
      target.replaceChildren(make("div", "workflow-warning", `图表目录读取失败：${error.message}`));
    }
  }

  async function openHelp() {
    showView("about");
  }

  async function initialize() {
    try {
      const [status, docs, directions] = await Promise.all([
        api("/api/status"), api("/api/documents"), api("/api/directions"),
      ]);
      setStatus(status);
      state.documents = docs.documents || [];
      state.directions = directions.directions || [];
      populateDocFilter();
      renderDocuments();
    } catch (error) {
      toast(`平台数据未通过检查：${error.message}`);
    }
  }

  document.querySelectorAll(".nav-item[data-view]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.view)));
  document.querySelectorAll("[data-open-view]").forEach((button) => button.addEventListener("click", () => showView(button.dataset.openView)));
  $("helpButton").addEventListener("click", openHelp);
  $("modelSettingsButton").addEventListener("click", openApiSettings);
  $("openApiSettings").addEventListener("click", openApiSettings);
  $("closeApiSettings").addEventListener("click", closeApiSettings);
  $("closeApiSettingsFooter").addEventListener("click", closeApiSettings);
  $("apiSettingsDialog").addEventListener("click", (event) => {
    if (event.target === $("apiSettingsDialog")) closeApiSettings();
  });
  $("loadModelsButton").addEventListener("click", loadModelCatalog);
  $("apiProvider").addEventListener("change", () => {
    const base = $("apiBaseUrl");
    if ($("apiProvider").value === "cstcloud") base.value = CSTCLOUD_BASE_URL;
    else if (base.value.trim() === CSTCLOUD_BASE_URL) base.value = "";
    $("apiModelList").replaceChildren();
    $("modelCatalogStatus").textContent = "模型目录尚未读取；可手动输入准确模型 ID。";
    updateRemoteApiState();
  });
  ["apiBaseUrl", "apiModel", "apiKey"].forEach((id) => $(id).addEventListener("input", updateRemoteApiState));
  $("generateToggle").addEventListener("change", () => {
    if ($("generateToggle").checked) $("remoteGenerateToggle").checked = false;
    updateRemoteApiState();
  });
  $("remoteGenerateToggle").addEventListener("change", () => {
    if ($("remoteGenerateToggle").checked) $("generateToggle").checked = false;
    updateRemoteApiState();
  });
  window.addEventListener("pagehide", () => { $("apiKey").value = ""; });
  $("searchForm").addEventListener("submit", (event) => { event.preventDefault(); submitQuery(); });
  document.querySelectorAll(".query-chip").forEach((button) => button.addEventListener("click", () => submitQuery(button.dataset.query)));
  $("graphDirection").addEventListener("change", loadGraph);
  $("createRun").addEventListener("click", createWorkflowRun);
  $("refreshRuns").addEventListener("click", () => loadRuns());
  $("runSelect").addEventListener("change", (event) => loadRun(event.target.value));
  $("pdfFiles").addEventListener("change", () => { renderSelectedFiles(); renderRun(state.currentRun); });
  $("uploadPdfs").addEventListener("click", uploadSelectedPdfs);
  $("runStage02").addEventListener("click", () => runWorkflowStage("02_pdf_clean_chunk"));
  $("runStage03").addEventListener("click", () => runWorkflowStage("03_bm25_index"));
  document.querySelectorAll("[data-stage-open]").forEach((button) => button.addEventListener("click", () => openWorkflowStage(button.dataset.stageOpen)));
  document.querySelectorAll("[data-stage-card]").forEach((card) => card.addEventListener("click", (event) => {
    if (event.target.closest("button") || event.target.closest("a")) return;
    openWorkflowStage(card.dataset.stageCard);
  }));
  $("workflowSearchForm").addEventListener("submit", searchWorkflowRun);
  $("fitGraph").addEventListener("click", () => {
    const scroll = $("graphScroll");
    if (scroll) { scroll.scrollLeft = 0; scroll.scrollTop = 0; }
    loadGraph();
  });
  $("copyBrief").addEventListener("click", async () => {
    if (!state.lastBrief) return;
    try {
      await navigator.clipboard.writeText(state.lastBrief);
      toast("证据摘要已复制。");
    } catch {
      toast("浏览器未授权剪贴板；可手动选择文本复制。");
    }
  });
  initialize();
})();
