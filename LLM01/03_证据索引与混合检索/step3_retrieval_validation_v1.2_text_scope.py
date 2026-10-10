#!/usr/bin/env python3
"""Versioned, non-destructive Step 3 smoke check for v1.2 text-only RQ1.

This is NOT an independent gold-set IR evaluation. The reference evidence IDs
are the current same-session candidate D01/D02 evidence, used only to check
whether the existing hybrid index can surface plausible text evidence after
scope alignment. It deliberately excludes D03 equation-type retrieval and
never overwrites the legacy retrieval_validation_report.md/results.json.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parent
sys.path.insert(0, str(ROOT))

from step3_hybrid_retrieval import HybridIndex, FUSED_TOP_K, PER_LEG_TOP_K, RRF_K  # noqa: E402

OUT_DIR = ROOT / "03_检索运行清单"
OUT_JSON = OUT_DIR / "retrieval_validation_v1.2_D01-D02_text_scope_20261008.json"
OUT_MD = OUT_DIR / "retrieval_validation_v1.2_D01-D02_text_scope_20261008.md"
CANDIDATE_PATH = PROJECT / "04_LLM抽取与Critic审查" / "06_v1.2文本范围预分类" / "B001_RQ1_D01-D03_v1.2_text_only_preclassification.json"
SCHEMA_PATH = PROJECT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "schema_v1.2.json"
PROMPT_PATH = PROJECT / "04_LLM抽取与Critic审查" / "01_Prompt与Schema注册" / "agent_prompts_RQ1_v1.2_text_only.md"
EVIDENCE_PATH = PROJECT / "02_PDF清洗与分块" / "02_Chunks" / "evidence_blocks.jsonl"
INDEX_MANIFEST = OUT_DIR / "index_build_manifest.json"
LEGACY_REPORT = OUT_DIR / "retrieval_validation_report.md"
LEGACY_JSON = OUT_DIR / "retrieval_validation_results.json"

QUERIES = [
    {
        "query_id": "Q1-D01-text-direction",
        "dimension": "D01",
        "query": (
            "How does each paper's own method describe water-to-power effects and power-to-water effects, "
            "including water availability or water-system operation affecting power generation or grid operation, "
            "and electricity, prices, pumps, desalination or power-system operation affecting water supply? "
            "Distinguish one-way from bidirectional textual coupling."
        ),
        "candidate_dimension": "D01",
        "note": "Text-only query for direction evidence; not a decision about field-wide prevalence.",
    },
    {
        "query_id": "Q1-D02-cooling-model-vs-generic-network",
        "dimension": "D02",
        "query": (
            "Does the paper's own model text explicitly describe in-plant cooling-water demand or process for a power plant, "
            "such as cooling-water requirements represented as water-network demands, cooling-water supply or pumping, "
            "or plant-specific flow, temperature, constraint, control or performance? Distinguish this from background "
            "mentions of power-plant cooling and generic water distribution system pumps, tanks, pipes and water demands."
        ),
        "candidate_dimension": "D02",
        "note": "Neutral text-only query for cooling-specific modeling versus general WDS or background mention.",
    },
    {
        "query_id": "Q1-D02-generic-dependency-boundary",
        "dimension": "D02",
        "query": (
            "In a multilayer infrastructure model, does the text only state that power plants receive water from water-supply "
            "facilities and give cooling as an example of the water-to-power dependency, or does it describe a cooling-specific "
            "demand, physical process, state, constraint, control target or performance measure? Preserve the distinction "
            "between a modeled generic dependency link and an explicitly modeled in-plant cooling process."
        ),
        "candidate_dimension": "D02",
        "note": "Boundary query for the distinction clarified during the original-PDF review; it does not presuppose that the generic dependency is absent.",
    },
]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_candidate_references() -> dict[str, list[str]]:
    data = json.loads(CANDIDATE_PATH.read_text(encoding="utf-8"))
    refs: dict[str, list[str]] = {"D01": [], "D02": []}
    for rec in data["records"]:
        dim = rec["dimension_id"]
        if dim not in refs:
            continue
        for evidence in rec.get("evidence", []):
            eid = evidence["evidence_id"]
            if eid not in refs[dim]:
                refs[dim].append(eid)
    return refs


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("Refusing to overwrite a previous v1.2 retrieval validation run.")

    idx = HybridIndex()
    references = load_candidate_references()
    results = []
    for item in QUERIES:
        raw = idx.hybrid_search(item["query"])
        fused = raw["fused_top"]
        bm25 = raw["bm25_top"]
        dense = raw["dense_top"]
        ref_ids = references[item["candidate_dimension"]]
        if item["query_id"] == "Q1-D02-generic-dependency-boundary":
            ref_ids = [
                eid for eid in ref_ids
                if idx.by_id[eid]["doc_id"] == "B001-PDF-03"
            ]

        fused_ids = [eid for eid, _ in fused]
        bm25_ids = [eid for eid, _ in bm25]
        dense_ids = [eid for eid, _ in dense]
        result = {
            **item,
            "reference_ids_same_session_candidates_not_gold": ref_ids,
            "candidate_reference_hits_fused_top10": [eid for eid in ref_ids if eid in fused_ids],
            "candidate_reference_hits_either_top20": [eid for eid in ref_ids if eid in bm25_ids or eid in dense_ids],
            "candidate_reference_not_in_either_top20": [eid for eid in ref_ids if eid not in bm25_ids and eid not in dense_ids],
            "fused_top10": [
                {
                    "evidence_id": eid,
                    "rrf_score": score,
                    "doc_id": idx.by_id[eid]["doc_id"],
                    "section_title": idx.by_id[eid].get("section_title"),
                    "page_numbers": idx.by_id[eid].get("page_numbers"),
                    "formula_layout_risk": bool(idx.by_id[eid].get("formula_layout_risk", False)),
                    "contains_unmapped_glyph_marker": bool(idx.by_id[eid].get("contains_unmapped_glyph_marker", False)),
                    "text_excerpt": None,
                }
                for eid, score in fused
            ],
            "bm25_top20_ids": [eid for eid, _ in bm25],
            "dense_top20_ids": [eid for eid, _ in dense],
        }
        results.append(result)

    manifest = {
        "run_id": "B001-Step3-RQ1-v1.2-text-scope-20261008",
        "status": "same_session_engineering_smoke_check_not_independent_gold_set_evaluation",
        "date": "2026-10-08",
        "scope": "D01/D02 text-only; D03 equation-type retrieval excluded; D04-D10 not rerun",
        "research_goal_note": "The three candidate gap/frontier directions and overall research objective are unchanged. Retrieval tests evidence discoverability only; missing labels or retrieval hits in this five-paper pilot do not determine the research objective.",
        "fusion": {"rrf_k": RRF_K, "per_leg_top_k": PER_LEG_TOP_K, "fused_top_k": FUSED_TOP_K},
        "input_sha256": {
            "evidence_blocks": sha(EVIDENCE_PATH),
            "schema_v1_2": sha(SCHEMA_PATH),
            "prompt_v1_2": sha(PROMPT_PATH),
            "candidate_preclassification": sha(CANDIDATE_PATH),
            "index_build_manifest": sha(INDEX_MANIFEST),
            "legacy_report_not_modified": sha(LEGACY_REPORT),
            "legacy_results_not_modified": sha(LEGACY_JSON),
        },
        "queries": results,
    }
    OUT_JSON.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Step 3 v1.2 RQ1 文本范围检索检查（D01/D02）",
        "",
        "- **状态：**同会话 Agent 工程性 smoke check；非独立人工金标准检索评估，也不是 RQ/领域假设的确认性检验。",
        "- **范围：**仅 v1.2 D01/D02 文本查询；D03 方程类型检索不执行；D04-D10定义未变，本次不重跑。",
        "- **索引：**沿用已构建239块混合索引；不改 embedding、BM25、RRF参数，不覆盖旧报告。",
        "- **公式范围：**报告不复制任何检索块原文；仅保留ID、页码、`formula_layout_risk` 和字形风险元数据，避免公式转录；不分析公式。",
        "- **参考 ID：**由当前同会话候选记录抽取，仅作证据发现 smoke check；不是 independent gold set，不把命中率解释为正式 recall/accuracy。",
        "- **研究目标：**研究主线和三项候选方向保持不变。查询是否命中只反映当前 top-k 的证据可发现性；未命中不等同于论文未讨论该维度，Step 4仍需 coverage pass。",
        "",
        f"- evidence blocks SHA-256: `{manifest['input_sha256']['evidence_blocks']}`",
        f"- schema v1.2 SHA-256: `{manifest['input_sha256']['schema_v1_2']}`",
        f"- prompt SHA-256: `{manifest['input_sha256']['prompt_v1_2']}`",
        f"- legacy report SHA-256 (unchanged): `{manifest['input_sha256']['legacy_report_not_modified']}`",
        "",
    ]
    for r in results:
        hits10 = r["candidate_reference_hits_fused_top10"]
        hits20 = r["candidate_reference_hits_either_top20"]
        nothit = r["candidate_reference_not_in_either_top20"]
        lines += [
            f"## {r['query_id']} — {r['dimension']}",
            "",
            f"- **查询：** {r['query']}",
            f"- 当前候选引用 ID 数：{len(r['reference_ids_same_session_candidates_not_gold'])}（非金标准）",
            f"- 候选 ID 出现在 fused Top-10：{hits10}",
            f"- 候选 ID 出现在任一路 Top-20：{hits20}",
            f"- 候选 ID 未进入任一路 Top-20：{nothit}",
            "- **Fused Top-10 排名/元数据（不复制原文）：**",
        ]
        for rank, hit in enumerate(r["fused_top10"], start=1):
            lines.append(
                f"  {rank}. `{hit['evidence_id']}` — {hit['doc_id']}, pages {hit['page_numbers']}; "
                f"formula_layout_risk={hit['formula_layout_risk']}; "
                f"contains_unmapped_glyph_marker={hit['contains_unmapped_glyph_marker']}"
            )
        lines.append("")
    lines += [
        "## 解释与限制",
        "",
        "1. 结果只回答：当前锁定索引能否把一些与这些自然语言查询相符的块排到 top-k。",
        "2. 当前 candidate reference IDs 来自本会话候选输出，存在循环性；不报告平均 recall，不据此比较模型，不称为检索准确率。",
        "3. 负面标签需回看论文全文文本和方法/案例上下文；top-k 未命中不能作为“未提及/未建模”的证据。",
        "4. 原 `retrieval_validation_report.md` 与 `retrieval_validation_results.json` 保留原样；此报告仅作 v1.2 增补。",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_MD}")
    print(f"Wrote {OUT_JSON}")


if __name__ == "__main__":
    main()
