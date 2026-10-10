(() => {
  const NS = "http://www.w3.org/2000/svg";
  const byId = (items) => new Map(items.map((item) => [item.id, item]));
  const el = (tag, attrs = {}, text = null) => {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, String(value));
    if (text !== null) node.textContent = text;
    return node;
  };
  const short = (value, max) => {
    const text = String(value || "");
    return text.length > max ? `${text.slice(0, max - 1)}…` : text;
  };

  function renderEvidenceGraph(graph) {
    const svg = document.getElementById("evidenceGraph");
    if (!svg) return;
    svg.replaceChildren();
    const allNodes = graph?.nodes || [];
    const allEdges = graph?.edges || [];
    const nodes = byId(allNodes);
    const directions = allNodes.filter((n) => n.type === "direction");
    const evidence = allNodes.filter((n) => n.type === "evidence");
    const documents = allNodes.filter((n) => n.type === "document");
    const citations = allEdges.filter((e) => e.relation === "CITES_PILOT_SYNTHESIS_EVIDENCE");
    const sourceEdges = allEdges.filter((e) => e.relation === "FROM_SOURCE_DOCUMENT");

    const directionEvidence = new Map();
    const evidenceDirections = new Map();
    for (const edge of citations) {
      if (!directionEvidence.has(edge.from)) directionEvidence.set(edge.from, []);
      directionEvidence.get(edge.from).push(edge.to);
      if (!evidenceDirections.has(edge.to)) evidenceDirections.set(edge.to, []);
      evidenceDirections.get(edge.to).push(edge.from);
    }
    const sortedEvidenceIds = [...new Set(citations.map((edge) => edge.to))].sort((a, b) => a.localeCompare(b));
    const evidenceById = byId(evidence);
    const docByEvidence = new Map();
    for (const edge of sourceEdges) docByEvidence.set(edge.from, edge.to);
    const visibleDocs = [...new Set(sortedEvidenceIds.map((id) => docByEvidence.get(id)).filter(Boolean))]
      .map((id) => nodes.get(id)).filter(Boolean).sort((a, b) => a.doc_id.localeCompare(b.doc_id));

    const rowGap = 56;
    const top = 78;
    const height = Math.max(470, top + sortedEvidenceIds.length * rowGap + 76);
    const width = 1160;
    svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
    svg.setAttribute("height", String(height));
    svg.setAttribute("preserveAspectRatio", "xMinYMin meet");
    svg.append(el("title", {}, "研究方向、先导引用证据与来源文献的追溯图"));

    const defs = el("defs");
    const marker = el("marker", { id: "arrowHead", markerWidth: 8, markerHeight: 8, refX: 7, refY: 4, orient: "auto", markerUnits: "strokeWidth" });
    marker.append(el("path", { d: "M0,0 L8,4 L0,8 z", fill: "#bdcbd7" }));
    defs.append(marker);
    svg.append(defs);

    const headers = [
      [52, "EXISTING CANDIDATE"],
      [402, "CITED EVIDENCE BLOCK"],
      [850, "SOURCE PAPER"],
    ];
    for (const [x, label] of headers) svg.append(el("text", { x, y: 30, class: "graph-column-label" }, label));

    const evidenceY = new Map(sortedEvidenceIds.map((id, index) => [id, top + index * rowGap]));
    const directionY = new Map();
    for (const direction of directions) {
      const ids = (directionEvidence.get(direction.id) || []).filter((id) => evidenceY.has(id));
      const ys = ids.map((id) => evidenceY.get(id));
      const center = ys.length ? ys.reduce((sum, y) => sum + y, 0) / ys.length : height / 2;
      directionY.set(direction.id, center - 28);
    }
    const docY = new Map(visibleDocs.map((doc, index) => [doc.id, Math.max(86, ((index + 1) * (height - 150)) / (visibleDocs.length + 1))]));

    const directionW = 264, evidenceW = 358, documentW = 262;
    const directionX = 46, evidenceX = 396, documentX = 850;
    const directionH = 56, evidenceH = 42, documentH = 54;

    // Provenance paths first, so the cards render above the lines.
    for (const edge of citations) {
      if (!directionY.has(edge.from) || !evidenceY.has(edge.to)) continue;
      const startX = directionX + directionW;
      const startY = directionY.get(edge.from) + directionH / 2;
      const endX = evidenceX;
      const endY = evidenceY.get(edge.to) + evidenceH / 2;
      svg.append(el("path", {
        d: `M ${startX} ${startY} C ${startX + 55} ${startY}, ${endX - 65} ${endY}, ${endX} ${endY}`,
        class: "graph-edge synthesis", "marker-end": "url(#arrowHead)",
      }));
    }
    for (const edge of sourceEdges) {
      if (!evidenceY.has(edge.from) || !docY.has(edge.to)) continue;
      const startX = evidenceX + evidenceW;
      const startY = evidenceY.get(edge.from) + evidenceH / 2;
      const endX = documentX;
      const endY = docY.get(edge.to) + documentH / 2;
      svg.append(el("path", {
        d: `M ${startX} ${startY} C ${startX + 48} ${startY}, ${endX - 55} ${endY}, ${endX} ${endY}`,
        class: "graph-edge", "marker-end": "url(#arrowHead)",
      }));
    }

    function addCard(node, x, y, w, h, kind, title, subtitle, related = []) {
      const stateClass = node.unresolved ? " pending" : "";
      const group = el("g", { class: `graph-node ${kind}${stateClass}`, tabindex: 0, role: "button", "aria-label": `${title}. ${subtitle}` });
      group.append(el("rect", { x, y, width: w, height: h, rx: kind === "evidence" ? 9 : 11 }));
      if (kind === "direction") {
        group.append(el("circle", { cx: x + 17, cy: y + 18, r: 4, fill: "#6f9fc8" }));
      } else if (kind === "evidence") {
        group.append(el("circle", { cx: x + 14, cy: y + 14, r: 3.5, fill: node.formula_layout_risk ? "#d69a4c" : "#64b2a0" }));
      } else {
        group.append(el("path", { d: `M ${x + 12} ${y + 14} h 9 v 10 h -9 z M ${x + 14} ${y + 17} h 5 M ${x + 14} ${y + 20} h 5`, fill: "none", stroke: "#c2914c", "stroke-width": 1 }));
      }
      const textX = x + (kind === "evidence" ? 26 : 31);
      group.append(el("text", { x: textX, y: y + 19, class: "node-title" }, short(title, kind === "evidence" ? 45 : 34)));
      group.append(el("text", { x: textX, y: y + 34, class: "node-sub" }, short(subtitle, kind === "evidence" ? 52 : 42)));
      group.addEventListener("click", () => window.openGraphNodeDetails?.(node, related));
      group.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          window.openGraphNodeDetails?.(node, related);
        }
      });
      svg.append(group);
    }

    for (const direction of directions) {
      const y = Math.max(48, Math.min(height - directionH - 35, directionY.get(direction.id) || height / 2));
      addCard(direction, directionX, y, directionW, directionH, "direction", `${direction.id} · ${direction.rq || "RQ"}`, direction.title || "既有研究方向");
    }

    const records = allNodes.filter((n) => n.type === "record");
    const recordEvidence = new Map();
    for (const edge of allEdges.filter((e) => e.relation === "CITES_EVIDENCE")) {
      if (!recordEvidence.has(edge.to)) recordEvidence.set(edge.to, []);
      const record = nodes.get(edge.from);
      if (record) recordEvidence.get(edge.to).push(record);
    }
    for (const evidenceId of sortedEvidenceIds) {
      const node = evidenceById.get(evidenceId);
      if (!node) continue;
      const y = evidenceY.get(evidenceId);
      const relatedRecords = recordEvidence.get(evidenceId) || [];
      const unresolved = relatedRecords.some((r) => r.doc_id === "B001-PDF-03" && r.dimension_id === "D02") || relatedRecords.some((r) => r.verification_status === "adjudication_required");
      const displayNode = { ...node, unresolved, direction_refs: (evidenceDirections.get(evidenceId) || []).map((id) => nodes.get(id)?.label || id), record_refs: relatedRecords };
      const sub = `${node.doc_id} · p.${(node.page_numbers || []).join(", ") || "?"}${node.formula_layout_risk ? " · formula risk" : ""}${unresolved ? " · D02 未裁定" : ""}`;
      addCard(displayNode, evidenceX, y, evidenceW, evidenceH, "evidence", node.label, sub, relatedRecords);
    }

    for (const doc of visibleDocs) {
      const y = docY.get(doc.id);
      addCard(doc, documentX, y, documentW, documentH, "document", doc.doc_id, `${doc.year || "年份未核"} · ${short(doc.title, 29)}`);
    }

    const countNode = document.getElementById("graphCount");
    if (countNode) countNode.textContent = `${directions.length} 方向 · ${sortedEvidenceIds.length} 引用证据 · ${visibleDocs.length} 文献`;
    return { nodes: allNodes.length, displayedEvidence: sortedEvidenceIds.length };
  }

  window.renderEvidenceGraph = renderEvidenceGraph;
})();
