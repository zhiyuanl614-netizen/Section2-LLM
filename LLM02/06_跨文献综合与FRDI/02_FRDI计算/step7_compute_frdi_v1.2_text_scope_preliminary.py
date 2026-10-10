#!/usr/bin/env python3
"""Exploratory v1.2 FRDI sensitivity calculation using text-only dimensions.

This script is versioned and non-destructive. It does not read D03/equation
labels or paper equations. Scores are same-session provisional judgments and
must not be represented as independently validated or preregistered.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # Section2-LLM/
LEDGER = ROOT / "04_LLM抽取与Critic审查/06_v1.2文本范围预分类/B001_v1.2_scope_aligned_50record_provisional_ledger.json"
SYNTHESIS = ROOT / "06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.2_text_scope_preliminary.json"
STEP1 = ROOT / "02_PDF清洗与分块/01_Zones/step1_sliced_pdf_corpus.json"
OUT_JSON = Path(__file__).resolve().parent / "frdi_results_v1.2_text_scope_preliminary.json"
OUT_MD = Path(__file__).resolve().parent / "frdi_v1.2_text_scope_preliminary.md"
DOCS = [f"B001-PDF-{i:02d}" for i in range(1, 6)]
MAX_ACHIEVEMENT = 2
MAX_LCI = 3
WEIGHTS = {
    "equal": {"ESI": 1 / 3, "TGM": 1 / 3, "LCI": 1 / 3},
    "ESI_dominant": {"ESI": 0.6, "TGM": 0.2, "LCI": 0.2},
    "TGM_excluded": {"ESI": 0.5, "TGM": 0.0, "LCI": 0.5},
}

# Text-only achievement rubric. No equation type or formula detail is used.
# 3-1: 0=no cooling-specific process/demand represented in prose; 1=cooling
# demand/supply appears as an explicit modeled water-service object; 2=clear
# detailed process coupling described in prose. The five-paper pilot has no 2.
ACHIEVEMENT_BASE = {
    "3-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 1, "B001-PDF-05": 0},
    "4-1": {doc: 0 for doc in DOCS},
    "5-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 1, "B001-PDF-05": 1},
}

# Author-stated limitations/future directions, scored on a same-session 0-3
# relevance rubric: 0 none; 1 indirect/general; 2 explicit related factor; 3
# direct author-stated future work aligned with the candidate direction.
LCI_BASE = {
    "3-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 0, "B001-PDF-05": 3},
    "4-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 2, "B001-PDF-05": 0},
    "5-1": {"B001-PDF-01": 1, "B001-PDF-02": 0, "B001-PDF-03": 1, "B001-PDF-04": 0, "B001-PDF-05": 1},
}

SCORING_RATIONALE = {
    "achievement": {
        "3-1": "PDF-04 earns 1 because its prose describes cooling-water requirements as water-system demands and cooling-water supply/pumping; PDF-03 remains 0 under the strict cooling-specific threshold, with score 1 shown as a sensitivity because the generic plant-water dependency is modeled.",
        "4-1": "All papers receive 0 for the complete candidate construct: no record establishes explicit fast information-layer sensing linked to slower physical dynamics and used for early warning/closed-loop control. Broad proactive/multistage labels alone do not meet the construct.",
        "5-1": "PDF-04 and PDF-05 earn 1 for facility/region-level intermediate outcomes without the complete explicit population/social-vulnerability endpoint; the other three receive 0.",
    },
    "LCI": {
        "3-1": "PDF-05's author-stated future work explicitly calls for quantifying power-plant/substation cooling-system dependence on water-supply capacity (evidence B001-PDF-05-ZD-S17-4-C003), scored 3 under the stated relevance rubric. This corrects the v1.0 Step 7 input, which had assigned 0.",
        "4-1": "PDF-04's future-work statement about SCADA communication middleware is directly related to information-layer infrastructure but does not itself describe the complete sensing/time-scale/control construct; score 2.",
        "5-1": "PDF-01, PDF-03 and PDF-05 have general/indirect future directions relevant to resilience or regional extension, scored 1 each; no document directly calls for the full population/social-vulnerability chain.",
    },
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def year_maps() -> tuple[dict[str, int], dict[str, int]]:
    docs = json.loads(STEP1.read_text(encoding="utf-8"))
    printed = {d["doc_id"]: int(d["pub_year"]) for d in docs}
    doi_tokens: dict[str, int] = {}
    for d in docs:
        warnings = " ".join(d.get("metadata_warnings") or [])
        m = re.search(r"year token (\d{4}) in DOI", warnings)
        doi_tokens[d["doc_id"]] = int(m.group(1)) if m else int(d["pub_year"])
    return printed, doi_tokens


def tgm(scores: dict[str, int], years: dict[str, int]) -> tuple[float, dict]:
    achievers = [doc for doc, score in scores.items() if score > 0]
    vals = list(years.values())
    corpus_mean = sum(vals) / len(vals)
    span = max(vals) - min(vals)
    if not achievers:
        return 0.5, {"no_data_points": True, "achievers": [], "corpus_mean_year": corpus_mean, "span": span}
    achiever_mean = sum(years[doc] for doc in achievers) / len(achievers)
    raw = achiever_mean - corpus_mean
    normalized = raw / span if span else 0.0
    result = (max(-1.0, min(1.0, normalized)) + 1) / 2
    return result, {
        "no_data_points": False,
        "achievers": achievers,
        "achiever_mean_year": achiever_mean,
        "corpus_mean_year": corpus_mean,
        "span": span,
        "raw_offset_years": raw,
    }


def calc_scenario(achievements: dict, lci: dict, years: dict) -> dict:
    out = {}
    for did in ["3-1", "4-1", "5-1"]:
        scores = achievements[did]
        esi = 1 - (sum(scores.values()) / len(scores) / MAX_ACHIEVEMENT)
        lci_score = sum(lci[did].values()) / len(lci[did]) / MAX_LCI
        tgm_score, detail = tgm(scores, years)
        out[did] = {
            "ESI": esi,
            "ESI_achievement_scores": scores,
            "LCI": lci_score,
            "LCI_author_limitation_scores": lci[did],
            "TGM_year_proxy": tgm_score,
            "TGM_detail": detail,
            "FRDI_by_weight": {
                name: sum(weights[k] * {"ESI": esi, "TGM": tgm_score, "LCI": lci_score}[k] for k in weights)
                for name, weights in WEIGHTS.items()
            },
        }
    return out


def main() -> None:
    if OUT_JSON.exists() or OUT_MD.exists():
        raise FileExistsError("Refusing to overwrite a previous v1.2 FRDI output")
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    synthesis = json.loads(SYNTHESIS.read_text(encoding="utf-8"))
    printed, doi_token = year_maps()

    scenarios = []
    for d03_score in [0, 1]:
        achievements = json.loads(json.dumps(ACHIEVEMENT_BASE))
        achievements["3-1"]["B001-PDF-03"] = d03_score
        for pdf05_lci_score in [2, 3]:
            lci = json.loads(json.dumps(LCI_BASE))
            lci["3-1"]["B001-PDF-05"] = pdf05_lci_score
            for year_name, years in [("printed_publication_year", printed), ("DOI_embedded_year_token_sensitivity", doi_token)]:
                result = calc_scenario(achievements, lci, years)
                for weight_name in WEIGHTS:
                    order = sorted(result, key=lambda d: result[d]["FRDI_by_weight"][weight_name], reverse=True)
                    scenarios.append({
                        "PDF03_achievement_score": d03_score,
                        "PDF05_3_1_LCI_score": pdf05_lci_score,
                        "year_basis": year_name,
                        "weight_scheme": weight_name,
                        "scores": {d: round(result[d]["FRDI_by_weight"][weight_name], 4) for d in result},
                        "ranking_high_to_low": order,
                    })

    base = calc_scenario(ACHIEVEMENT_BASE, LCI_BASE, printed)
    base_doi = calc_scenario(ACHIEVEMENT_BASE, LCI_BASE, doi_token)
    output = {
        "report_id": "Step7-v1.2-text-scope-FRDI-preliminary-20261008",
        "status": "exploratory_sensitivity_analysis_not_final_priority_ranking",
        "formula_scope": "No paper-equation details, D03 labels, or equation-type claims used.",
        "research_objective_unchanged": True,
        "research_gap_hypotheses": [g["id"] for g in synthesis["candidate_directions"]],
        "provenance": {
            "achievement_scores": "same-session text-based scoring from the provisional 5-paper ledger; D01/D02 and D04-D10 only; D03 excluded",
            "LCI_scores": "same-session text-based reading of author limitations/future-work statements; PDF-05 cooling-system future work for 3-1 corrected from legacy v1.0 score 0 to base score 3",
            "publication_years": "Printed publication year is the primary proxy; DOI-embedded year token is a sensitivity only and is not assumed to be publication year.",
            "review_independence": "No independent human gold standard or independent reviewer sign-off.",
        },
        "scoring_rubric": {
            "achievement_0_to_2": {
                "0": "No clear text description of the target achievement in the paper's own method.",
                "1": "Partial/proxy achievement described in text.",
                "2": "Detailed achievement of the full candidate construct described in text; none observed in this pilot.",
            },
            "LCI_0_to_3": {
                "0": "No relevant author-stated limitation/future direction.",
                "1": "Indirect or general relation.",
                "2": "Explicitly named related factor, but not a direct call for the complete candidate direction.",
                "3": "Direct author-stated future work aligned with the candidate direction.",
            },
        },
        "scoring_rationales": SCORING_RATIONALE,
        "base_case": {
            "scenario": "PDF-03 strict cooling-specific score=0; PDF-05 LCI for 3-1=3",
            "printed_year_basis": base,
            "DOI_token_year_sensitivity": base_doi,
        },
        "sensitivity_scenarios": scenarios,
        "year_data": {"printed_publication_year": printed, "DOI_embedded_year_token_sensitivity": doi_token},
        "inputs": {
            "achievement_scores_base": ACHIEVEMENT_BASE,
            "LCI_scores_base": LCI_BASE,
            "weight_schemes": WEIGHTS,
        },
        "source_sha256": {
            "provisional_ledger": sha(LEDGER),
            "synthesis_v1_2_preliminary": sha(SYNTHESIS),
            "step1_corpus_years": sha(STEP1),
        },
        "limitations": [
            "N=5; scores are ordinal, same-session and exploratory, not independently validated.",
            "D02 PDF-03 remains unresolved; the alternative achievement score is a sensitivity, not an adjudicated label.",
            "PDF-05's cooling-system future-work statement directly relates to 3-1; the prior v1.0 Step 7 LCI score of 0 omitted it. The v1.2 score is corrected, but the rubric is still subjective.",
            "Publication years are weak momentum proxies; the printed year for PDF-05 is 2027, later than the current date, and the DOI-embedded token can differ by 1-3 years. No field trend is inferred.",
            "FRDI is an exploratory within-pilot prioritization aid, not a field-wide or statistically validated index and not a substitute for the three research questions.",
        ],
    }
    OUT_JSON.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    base_table = []
    for did in ["3-1", "4-1", "5-1"]:
        r = base[did]
        rdoi = base_doi[did]
        base_table.append((did, r["ESI"], r["LCI"], r["TGM_year_proxy"], rdoi["TGM_year_proxy"], r["FRDI_by_weight"]))

    lines = [
        "# Step 7 — FRDI v1.2（文本范围探索性敏感性分析）",
        "",
        "- **状态：**预备、探索性敏感性分析；不是定稿的研究方向优先级排序，不覆盖旧 `frdi_v1.*` 产物。",
        "- **目标：**三项候选方向 3-1/4-1/5-1 均保留。FRDI只作样本内比较辅助，不决定是否保留某个研究问题或章节。",
        "- **范围：**以文字标签 D01/D02 与沿用的 D04-D10作成就输入，完全排除 D03 方程类型和论文公式细节。",
        "- **审核：**分数由同会话 Agent 设定；无独立专家/盲审，也非外部预注册。",
        "",
        "## 1. 文本成就与作者局限评分",
        "",
        "| 候选方向 | 成就得分（PDF-01→05） | 作者局限/未来工作关联得分（PDF-01→05） |",
        "|---|---|---|",
    ]
    for did in ["3-1", "4-1", "5-1"]:
        a = base[did]["ESI_achievement_scores"]
        l = base[did]["LCI_author_limitation_scores"]
        lines.append(f"| {did} | {list(a.values())} | {list(l.values())} |")
    lines += [
        "",
        "**评分说明：**3-1 的基础成就评分只衡量文字是否描述了厂内冷却水模型对象，不使用任何方程详情；PDF-04得1，PDF-03按严格冷却专属阈值得0并另设敏感性。LCI方面，PDF-05的作者明确把冷却系统对供水能力的依赖列为未来工作，因此本版将其 3-1 关联分从旧版的0修正为3（直接匹配），同时对分值2做敏感性分析。",
        "",
        "## 2. 基准成分（打印出版年为主，DOI年令牌仅作敏感性）",
        "",
        "| 候选方向 | ESI | LCI | TGM（打印年） | TGM（DOI令牌年） | FRDI等权（打印年） | FRDI等权（DOI令牌年） |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for did, esi, lci, tgm_print, tgm_doi, frdi_print in base_table:
        frdi_doi = base_doi[did]["FRDI_by_weight"]["equal"]
        lines.append(f"| {did} | {esi:.3f} | {lci:.3f} | {tgm_print:.3f} | {tgm_doi:.3f} | {frdi_print['equal']:.3f} | {frdi_doi:.3f} |")

    top_counts = {did: sum(s["ranking_high_to_low"][0] == did for s in scenarios) for did in ["3-1", "4-1", "5-1"]}
    rank_text = lambda values: " > ".join(sorted(values, key=values.get, reverse=True))
    lines += [
        "",
        "## 3. 必要敏感性",
        "",
        "脚本对以下情形组合计算完整的权重（等权、ESI主导、剔除TGM）与年份基准敏感性，并保存在同目录 JSON：",
        "",
        f"- **24个组合的第一位计数：**4-1={top_counts['4-1']}/24，5-1={top_counts['5-1']}/24，3-1={top_counts['3-1']}/24。此计数仅是当前主观评分和权重设计的计算结果，不是方向优先级结论。",
        f"- **等权排序：**打印年基准 `{rank_text({d: base[d]['FRDI_by_weight']['equal'] for d in base})}`；DOI年令牌敏感性 `{rank_text({d: base_doi[d]['FRDI_by_weight']['equal'] for d in base_doi})}`，其中4-1与5-1分值非常接近。",
        f"- **权重敏感性：**打印年下，ESI主导为 `{rank_text({d: base[d]['FRDI_by_weight']['ESI_dominant'] for d in base})}`；剔除TGM为 `{rank_text({d: base[d]['FRDI_by_weight']['TGM_excluded'] for d in base})}`。可见排序受所选权重影响，不应当作稳健的单一赢家。",
        "",
        "1. **PDF-03边界：**严格冷却专属阈值记成就0；若专家判断通用依赖足以构成部分成就，另算分值1。后者是计算敏感性，不自动改动 D02 标签。",
        "2. **PDF-05 LCI：**基础分3表示作者明确将冷却系统供水依赖列为未来工作；分2作为较保守解释。旧 v1.0 FRDI把这条证据记为0，本版予以纠正。",
        "3. **年份基准：**PDF-05打印卷期年为2027（晚于本项目当前日期2026-10-08），而其 DOI 年令牌为2026；PDF-04打印年2022、DOI令牌2019。DOI令牌年不自动等于首次公开年份，因此只作敏感性；不从这5篇推断领域时间趋势。",
        "",
        "## 4. 解读边界",
        "",
        "- ESI、LCI、TGM及合成分数都是同会话的探索性序数/时间代理；微小排序差不代表统计差异。",
        "- 若 PDF-03 D02边界改变、或 PDF-05未来工作关联强度有不同专家意见，3-1排序可能改变；应报告情景范围而非单一‘赢家’。",
        "- FRDI不得替代文献学习提出的研究问题，也不得用低优先级否定3-1/4-1/5-1任何章节方向。",
        "- 本指数仅回答‘在当前假设下如何对5篇先导语料作探索性排序’，不能验证领域级 gap，也不是论文方法或研究方向的质量评价。",
        "",
        "## 5. 版本化结果",
        "",
        f"- 机器可读结果：`{OUT_JSON.name}`",
        f"- 可复算脚本：`{Path(__file__).name}`",
        f"- 先导证据综合：`{SYNTHESIS.relative_to(ROOT)}`",
        f"- 输入 ledger SHA-256：`{sha(LEDGER)}`",
        "",
    ]
    OUT_MD.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT_JSON}")
    print(f"Wrote {OUT_MD}")
    print("Base equal-weight printed-year FRDI:", {d: round(base[d]["FRDI_by_weight"]["equal"], 4) for d in base})


if __name__ == "__main__":
    main()
