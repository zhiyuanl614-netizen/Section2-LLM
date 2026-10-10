#!/usr/bin/env python3
"""Step 7 — FRDI（Frontier Research Direction Index）计算脚本 v1.0（2026-10-06）。

**强制声明（务必随任何引用本脚本输出的产出一并重复）：**
FRDI 在本流程中是"本受限5篇语料内的探索性候选方向优先级指数"，
不是已验证、可跨领域比较的前沿指数。权重、归一化和缺失值规则在本文件内
一次性文档化并代码化（README P0-7 要求的"冻结"），但因本项目是单次会话
内的探索性分析而非独立于数据观察之外的预注册，不构成严格意义上的
盲法预注册；本脚本运行后不会根据结果反向调整下列打分规则或权重
（该承诺本身也只能依赖本次会话记录自证，无法由第三方外部验证）。

本脚本只做：
  1. 读取已冻结的 ESI/TGM/LCI 原始评分输入表（见下方 ACHIEVEMENT_SCORES /
     LCI_SCORES 常量，评分依据已在 Step 6 synthesis_v1.md 和 Step 5
     错误分析中有据可查，不是本脚本临时编造）；
  2. 用固定代数公式计算 ESI、TGM（含出版年敏感性分析）、LCI 和 FRDI
     （含权重敏感性分析）；
  3. 输出 frdi_results_v1.json。
语义判断（某论文在某方向上处于哪个成就等级、某局限性陈述与某候选方向的
关联强度）已经由 Agent A/B 在 Step 4-6 完成，本脚本不重新做语义判断。
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # Section2-LLM/
SYNTHESIS_FP = ROOT / "06_跨文献综合与FRDI/01_跨文献LLM综合/synthesis_v1.json"
STEP1_FP = ROOT / "02_PDF清洗与分块/01_Zones/step1_sliced_pdf_corpus.json"
OUT_FP = Path(__file__).resolve().parent / "frdi_results_v1.json"

DOCS = ["B001-PDF-01", "B001-PDF-02", "B001-PDF-03", "B001-PDF-04", "B001-PDF-05"]

# ---------------------------------------------------------------------------
# 1. ESI 输入：每篇文献在每个候选方向上的"成就等级"（ordinal achievement score）
#    评分量表在计算前冻结，依据见 synthesis_v1.md 第3节对应 D0X 标签组合：
#
#    方向 3-1（第3章，冷却水热-水力显式建模），量表 0-2：
#      0 = Mentioned_Only_Not_Modeled / Generic_Water_Network_Only（无冷却专属物理）
#      1 = Both_Present 但被判定为简化指数函数（非完整热力学模型）
#      2 = 完整冷却塔热力学联合建模（本语料中无此案例）
#    方向 4-1（第4章，cyber快感知驱动早期预警/主动控制），量表 0-2：
#      0 = D04=Not_Addressed（本语料全部5篇如此）
#      1 = D04有实现但非闭环实时触发
#      2 = D04为Explicit_Fast_Sensing_Mechanism且与D05/D06时间尺度差构念联动
#    方向 5-1（第5章，物理网络损失到人口/社会脆弱性全链条量化），量表 0-2：
#      0 = D07=Not_Stated_In_Text 或 D08=None_Reported（无关键设施/人类后果刻画）
#      1 = D07=Critical_Facility_Impact 但 D08 未报告人口/社会脆弱性指标
#      2 = 完整链条：具名关键设施 + 显式人口计数/社会脆弱性指数（本语料中无此案例）
# ---------------------------------------------------------------------------
ACHIEVEMENT_SCORES = {
    "3-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 1, "B001-PDF-05": 0},
    "4-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 0, "B001-PDF-05": 0},
    "5-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 1, "B001-PDF-05": 1},
}
ACHIEVEMENT_MAX = 2

# ---------------------------------------------------------------------------
# 2. LCI 输入：每篇文献 D10（局限性/未来方向）陈述与每个候选方向的关联强度，
#    0-3 级评分（量表定义见 error_analysis_v1.md 与 synthesis_v1.md 第3节RQ4）：
#      0 = 该文献的D10完全未提及与该方向相关的内容
#      1 = 切题但泛化/间接（例如笼统提及"韧性"或"未来研究"，不具体指向该构念）
#      2 = 明确点名了与该方向直接相关的具体因素，但未直接呼吁完全匹配该方向的未来工作
#      3 = 明确点名且呼吁的未来工作与该候选方向的核心陈述高度吻合
#    逐条评分依据（均为D10 mechanism_judgment/evidence的直接转述，可在
#    05_核验通过结果/*_verified_10d.json 中逐一核对）：
#      PDF-01 D10："extreme-weather resilience...unmodeled factor" -> 对5-1泛化相关(1)，与3-1/4-1无关(0)
#      PDF-02 D10："stochastic optimization...price/demand uncertainty" -> 与三个方向均不直接相关(0,0,0)
#      PDF-03 D10："flow-overload cascading failure unmodeled...real case study future work" -> 对5-1泛化相关(1，未来真实案例研究是迈向人口影响量化的前置步骤，但未直接呼吁)，与3-1/4-1无关(0)
#      PDF-04 D10："SCADA communication middleware...needed for realistic data exchange"(future work) -> 对4-1明确点名相关(2，SCADA中间件直接对应cyber通信基础设施，但未明确框定为"利用时间尺度差做早期预警"这一完整构念)；与3-1/5-1无关(0,0)
#      PDF-05 D10："unmodeled direct structural damage to WTPs...regional-scale extension needed" -> 对5-1泛化相关(1，WTP结构损伤和区域尺度扩展是迈向人口影响量化的相关但非直接陈述)，与3-1/4-1无关(0,0)
# ---------------------------------------------------------------------------
LCI_SCORES = {
    "3-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 0, "B001-PDF-05": 0},
    "4-1": {"B001-PDF-01": 0, "B001-PDF-02": 0, "B001-PDF-03": 0, "B001-PDF-04": 2, "B001-PDF-05": 0},
    "5-1": {"B001-PDF-01": 1, "B001-PDF-02": 0, "B001-PDF-03": 1, "B001-PDF-04": 0, "B001-PDF-05": 1},
}
LCI_MAX = 3

# 权重方案：主方案为等权重（避免被质疑为"按结果反推权重"）；另给出2个敏感性方案。
WEIGHT_SCHEMES = {
    "primary_equal": {"ESI": 1 / 3, "TGM": 1 / 3, "LCI": 1 / 3},
    "sensitivity_ESI_dominant": {"ESI": 0.6, "TGM": 0.2, "LCI": 0.2},
    "sensitivity_TGM_excluded": {"ESI": 0.5, "TGM": 0.0, "LCI": 0.5},
}


def compute_esi(direction_id):
    scores = ACHIEVEMENT_SCORES[direction_id]
    avg = sum(scores.values()) / len(scores) / ACHIEVEMENT_MAX
    return 1 - avg, scores


def compute_lci(direction_id):
    scores = LCI_SCORES[direction_id]
    avg = sum(scores.values()) / len(scores) / LCI_MAX
    return avg, scores


def compute_tgm(direction_id, year_by_doc):
    """TGM_k：方向k的非零成就论文的年份均值相对全语料年份均值的偏移，
    归一化到corpus年份跨度，再线性映射到[0,1]（0.5=中性/无偏移或无数据点）。
    若该方向在全部5篇中成就得分均为0（无数据点），返回中性值0.5并标记
    no_data_points=True（不得被解读为"已计算出零动量"）。
    """
    scores = ACHIEVEMENT_SCORES[direction_id]
    achievers = [doc for doc, s in scores.items() if s > 0]
    years = list(year_by_doc.values())
    corpus_mean = sum(years) / len(years)
    span = max(years) - min(years)
    if not achievers:
        return 0.5, {"no_data_points": True, "achievers": [], "corpus_mean_year": corpus_mean, "span": span}
    achiever_mean = sum(year_by_doc[d] for d in achievers) / len(achievers)
    momentum_raw = achiever_mean - corpus_mean
    momentum_norm = momentum_raw / span if span else 0.0
    momentum_01 = (max(-1.0, min(1.0, momentum_norm)) + 1) / 2
    return momentum_01, {
        "no_data_points": False,
        "achievers": achievers,
        "achiever_mean_year": achiever_mean,
        "corpus_mean_year": corpus_mean,
        "span": span,
        "momentum_raw": momentum_raw,
    }


def main():
    synthesis = json.loads(SYNTHESIS_FP.read_text(encoding="utf-8"))
    step1 = json.loads(STEP1_FP.read_text(encoding="utf-8"))
    pub_year = {d["doc_id"]: d["pub_year"] for d in step1}
    doi_year = {}
    for d in step1:
        warn = " ".join(d.get("metadata_warnings") or [])
        # DOI token year = printed year - 1 in every case observed in this corpus (see README);
        # extracted here by parsing the warning text rather than re-deriving independently.
        doi_token = None
        if "DOI string" in warn:
            import re as _re
            m = _re.search(r"year token (\d{4}) in DOI", warn)
            if m:
                doi_token = int(m.group(1))
        doi_year[d["doc_id"]] = doi_token if doi_token is not None else d["pub_year"]

    direction_ids = ["3-1", "4-1", "5-1"]
    results = {"directions": {}, "weight_schemes": WEIGHT_SCHEMES, "year_bases": {"printed_year": pub_year, "doi_token_year": doi_year}}

    for did in direction_ids:
        esi, esi_scores = compute_esi(did)
        lci, lci_scores = compute_lci(did)
        tgm_primary, tgm_primary_detail = compute_tgm(did, pub_year)
        tgm_sens, tgm_sens_detail = compute_tgm(did, doi_year)

        frdi_by_scheme = {}
        for scheme_name, w in WEIGHT_SCHEMES.items():
            frdi_by_scheme[scheme_name] = {
                "frdi_printed_year_basis": round(w["ESI"] * esi + w["TGM"] * tgm_primary + w["LCI"] * lci, 4),
                "frdi_doi_year_basis": round(w["ESI"] * esi + w["TGM"] * tgm_sens + w["LCI"] * lci, 4),
            }

        results["directions"][did] = {
            "ESI": round(esi, 4),
            "ESI_achievement_scores": esi_scores,
            "LCI": round(lci, 4),
            "LCI_scores": lci_scores,
            "TGM_printed_year_basis": round(tgm_primary, 4),
            "TGM_printed_year_detail": tgm_primary_detail,
            "TGM_doi_year_basis": round(tgm_sens, 4),
            "TGM_doi_year_detail": tgm_sens_detail,
            "FRDI_by_weight_scheme": frdi_by_scheme,
        }

    # Robustness summary: rank directions under every (weight_scheme x year_basis) combination
    scenarios = []
    for scheme_name in WEIGHT_SCHEMES:
        for year_basis in ["frdi_printed_year_basis", "frdi_doi_year_basis"]:
            ranking = sorted(
                direction_ids,
                key=lambda d: results["directions"][d]["FRDI_by_weight_scheme"][scheme_name][year_basis],
                reverse=True,
            )
            scenarios.append({"weight_scheme": scheme_name, "year_basis": year_basis, "ranking_high_to_low": ranking})
    results["robustness_scenarios"] = scenarios
    results["robustness_summary"] = {
        "always_lowest": "3-1" if all(s["ranking_high_to_low"][-1] == "3-1" for s in scenarios) else None,
        "n_scenarios": len(scenarios),
        "n_scenarios_4-1_above_5-1": sum(
            1 for s in scenarios if s["ranking_high_to_low"].index("4-1") < s["ranking_high_to_low"].index("5-1")
        ),
    }

    OUT_FP.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT_FP}")
    print(json.dumps(results["robustness_summary"], indent=2, ensure_ascii=False))
    for did in direction_ids:
        r = results["directions"][did]
        print(f"\n{did}: ESI={r['ESI']} LCI={r['LCI']} TGM(printed)={r['TGM_printed_year_basis']} TGM(doi)={r['TGM_doi_year_basis']}")
        for scheme in WEIGHT_SCHEMES:
            print(f"  {scheme}: {r['FRDI_by_weight_scheme'][scheme]}")


if __name__ == "__main__":
    main()
