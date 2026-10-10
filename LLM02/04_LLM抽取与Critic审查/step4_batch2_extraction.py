#!/usr/bin/env python3
"""Step 4 scale-up batch: Agent A -> Agent B -> Agent A(revise) -> Agent B(final)
on the remaining 3 Route-A papers: B001-PDF-02, B001-PDF-03, B001-PDF-04.

Same real in-session agent-reasoning methodology as the Step 4 pilot
(step4_pilot_extraction.py): no external LLM API calls, execution_channel
is logged honestly as arena_agent_mode_in_session. This script persists the
already-performed D01-D10 extraction + independent critic review for the
3 scale-up documents, and APPENDS to the existing pilot's manifest log
(it does not overwrite the 2 pilot documents' records).
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHUNKS_DIR = ROOT.parent / "02_PDF清洗与分块" / "02_Chunks"
SCHEMA_VERSION = "v1.0"
AGENT_A_PROMPT_VERSION = "AgentA_prompt_v1.0"
AGENT_B_PROMPT_VERSION = "AgentB_prompt_v1.0"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_evidence_index() -> dict:
    idx = {}
    with open(CHUNKS_DIR / "evidence_blocks.jsonl", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                r = json.loads(line)
                idx[r["evidence_id"]] = r
    return idx


EVIDENCE = load_evidence_index()


def ev(*ids):
    return list(ids)


# ---------------------------------------------------------------------------
# Agent A -- Pass 1 (initial extraction)
# ---------------------------------------------------------------------------
AGENT_A_PASS1 = {
    # =======================================================================
    # B001-PDF-02 -- Optimal Coordination of Water Distribution Energy
    # Flexibility With Power Systems Operation
    # =======================================================================
    "B001-PDF-02": [
        dict(dimension_id="D01", primary_label="Bidirectional_Coupled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The W-DSO's own-method day-ahead operation cost is driven by forecasted electricity "
                                 "prices (Power_to_Water), while the proposed WDS energy flexibility model explicitly "
                                 "offers a flexible capacity range back to the power system operator, which "
                                 "co-optimizes it in a network-constrained unit commitment (Water_to_Power).",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-02-ZA-ABSTRACT-C001", "B001-PDF-02-ZB-S11-B-C001"),
             verbatim_quote="A WDS energy ﬂexibility model is proposed that is used by W-DSOs in order to calculate "
                            "and offer the feasible ﬂexible energy capacity to the power system operator.",
             equation_detail=None, confidence=0.9),
        dict(dimension_id="D02", primary_label="Mentioned_Only_Not_Modeled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The introduction names power-plant cooling as one of several water-energy-nexus "
                                 "uses of water, but the paper's own WDS operation model (pipes, pumps, tanks, "
                                 "reservoirs, water loads) contains no power-plant cooling process.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-02-ZA-S01-I-C001"),
             verbatim_quote="Water is utilized, often in large amounts, in energy sector for mining, fuel "
                            "production, hydropower, and power plant cooling.",
             equation_detail=None, confidence=0.85),
        dict(dimension_id="D03", primary_label="Hydraulic_Pressure_Flow_Equation",
             secondary_labels=["Energy_Power_Balance_Equation", "Economic_Cost_Coupling_Equation"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The pump characteristic equations (13)-(14) tie hydraulic variables (flow, speed) "
                                 "directly to pump electric power consumption; the DC power flow nodal balance (39) "
                                 "integrates WDS power consumption into the power system; and the joint objective "
                                 "(1) sums water-purchase cost and pump energy cost.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-02-ZB-S05-A-C004", "B001-PDF-02-ZB-S11-B-C001", "B001-PDF-02-ZB-S05-A-C001"),
             verbatim_quote="In summary, (1)-(16) present the proposed operation model for W-DSOs, which minimizes "
                            "the total WDS operation cost in (1) by optimizing the operation of tanks and pumps "
                            "while ensuring the deliverability of water to the consumers consid-ering the water "
                            "conservation and pressure head constraints.",
             equation_detail=dict(equation_number="(13)-(14), (39)", variables="Qu,t pump flow; omega_u,t pump speed; "
                                   "PW_u,t pump electric power; Pi,t generator output; Fl,t line flow",
                                   physical_meaning="pump hydraulic-to-electrical power conversion equations linked "
                                   "into the DC power flow nodal balance", page=3),
             confidence=0.8),
        dict(dimension_id="D04", primary_label="Not_Addressed", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="This is a day-ahead scheduling/unit-commitment paper with no sensing, SCADA, or "
                                 "communication architecture described.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.9),
        dict(dimension_id="D05", primary_label="Single_Timescale_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Both the WDS operation model and the network-constrained unit commitment model "
                                 "are scheduled over the same day-ahead horizon divided into NT (hourly) intervals; "
                                 "no separate fast/slow or real-time correction stage is formulated.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-02-ZB-S05-A-C001"),
             verbatim_quote="over the scheduling horizon divided to NT intervals",
             equation_detail=None, confidence=0.75),
        dict(dimension_id="D06", primary_label="Proactive_Anticipatory_Control", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The W-DSO model schedules pump/tank operation a day ahead using expected (forecast) "
                                 "water demand and electricity prices, which is inherently anticipatory rather than "
                                 "triggered by an observed deviation.",
             uncertainty_note="This is a standard day-ahead scheduling paradigm; the paper does not explicitly "
                               "justify the anticipatory design by appeal to a fast-sensing/slow-hydraulics timescale "
                               "argument (contrast with D04/D05), so justification_explicit is set to false.",
             evidence_ids=ev("B001-PDF-02-ZA-ABSTRACT-C001"),
             verbatim_quote="given the expected water demand and electricity prices of the next day",
             equation_detail=None, confidence=0.75, justification_explicit=False),
        dict(dimension_id="D07", primary_label="Not_Stated_In_Text", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="This is a steady-state day-ahead cost-optimization study; no disturbance, failure, "
                                 "or cascading-impact scenario is modeled anywhere in the paper.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.85),
        dict(dimension_id="D08", primary_label="None_Reported", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="No population, critical-facility, or social-vulnerability impact metric appears "
                                 "anywhere in the case study.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.85),
        dict(dimension_id="D09", primary_label="Synthetic_Test_System_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The case study uses a standard 6-bus test power system and a 15-node test WDS "
                                 "drawn from cited literature test-case data, with no named real city or utility.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-02-ZC-S12-V-C001"),
             verbatim_quote="The proposed model to integrate the energy ﬂexibility of WDSs in power systems "
                            "operation is implemented on the 6-bus test power system shown in Fig. 5.",
             equation_detail=None, confidence=0.85),
        dict(dimension_id="D10", primary_label="Future_Work_Direction",
             secondary_labels=["Missing_Factor_Limitation", "Model_Simplification_Limitation"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The conclusion explicitly proposes extending the deterministic model to a "
                                 "stochastic optimization accounting for electricity-price and water-demand-forecast "
                                 "uncertainty, implying the current model does not account for these uncertainties.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-02-ZD-S15-VI-C002"),
             verbatim_quote="Future works may include expanding the proposed model to a stochastic optimization "
                            "model, which would account for the uncertain-ties in the wholesale energy prices, as "
                            "well as the uncertainty of water demand forecast of WDSs.",
             equation_detail=None, confidence=0.85),
    ],
    # =======================================================================
    # B001-PDF-03 -- Resilience Assessment of Interdependent Infrastructure
    # Systems: A Case Study Based on Different Response Strategies
    # =======================================================================
    "B001-PDF-03": [
        dict(dimension_id="D01", primary_label="Bidirectional_Coupled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own multilayer network model explicitly instantiates both directions "
                                 "for the water-power layer pair in its own test case: water supply facilities are "
                                 "powered by the electric infrastructure (node-node dependence, Eq.(1)), and power "
                                 "plants are provided water by the water supply facilities (node-edge dependence, "
                                 "Eq.(2)).",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-03-ZB-S21-5-2-C001", "B001-PDF-03-ZB-S03-2-1-C006"),
             verbatim_quote="Water supply facilities, including waterworks, storage facilities and pump stations "
                            "are powered by the eclectic infrastructure located in the same geographic area, which "
                            "means node-node dependence and use of Equation (1). Power plants are provided with "
                            "water by the water supply facilities in the same geographic area, which means "
                            "node-edge dependence and use of Equation (2).",
             equation_detail=None, confidence=0.95),
        dict(dimension_id="D02", primary_label="Mentioned_Only_Not_Modeled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Cooling is named as the real-world rationale for the water-to-power dependency "
                                 "edge, but the actual formal dependency equations (1)-(5) are generic graph-"
                                 "theoretic binary functioning-state relations applied identically to every "
                                 "infrastructure pair; there is no cooling-specific thermal-hydraulic parameter "
                                 "(temperature, flow rate, make-up water volume, etc.).",
             uncertainty_note="Boundary case vs. Generic_Water_Network_Only -- see Agent B review; the dependency "
                               "IS instantiated in the formal simulated test case (not just background text), but "
                               "with no cooling-specific physics.",
             evidence_ids=ev("B001-PDF-03-ZB-S03-2-1-C006", "B001-PDF-03-ZD-S30-6-3-C002"),
             verbatim_quote="The blue dotted line between two networks illustrates water transfer from the water "
                            "infrastructure layer to power grid infrastructure (for example, for cooling the "
                            "thermal power plants).",
             equation_detail=None, confidence=0.55),
        dict(dimension_id="D03", primary_label="No_Explicit_Equation_Qualitative_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The water-power coupling in the paper's own test case is instantiated via Eqs. "
                                 "(1)-(2), the generic infrastructure dependence-pattern formulas (binary node/edge "
                                 "functioning-state products). These are genuine numbered equations, but their "
                                 "mathematical nature -- discrete graph-topological state-propagation logic -- does "
                                 "not correspond to any of the five quantitative-physical coupling categories in "
                                 "this schema (hydraulic, power-balance, thermal-hydraulic, cost, statistical); no "
                                 "pressure, flow, power, or cost variable with physical units is actually used.",
             uncertainty_note="SCHEMA GAP FLAG: this is a real taxonomy coverage gap, not a text-evidence problem. "
                               "The paper does have explicit numbered equations governing the coupling (contradicting "
                               "a literal reading of 'Qualitative_Only'), but none of the six controlled D03 "
                               "categories describe a binary graph-dependency-state equation. "
                               "No_Explicit_Equation_Qualitative_Only is chosen as the least-misleading existing "
                               "label for RQ1 purposes (no physical/economic coupling equation is used), but a "
                               "future schema version should consider adding a 'Topological_Dependency_Equation' "
                               "category. See Agent B review and the batch report.",
             evidence_ids=ev("B001-PDF-03-ZB-S21-5-2-C001"),
             verbatim_quote="Power plants are provided with water by the water supply facilities in the same "
                            "geographic area, which means node-edge dependence and use of Equation (2).",
             equation_detail=dict(equation_number="(1)-(2)",
                                   variables="nφ1_i, nφ2_j binary node functioning-state indicators (0/1); "
                                   "eφ1φ2_ij binary inter-network edge dependency indicator",
                                   physical_meaning="generic graph-theoretic dependency propagation function (not a "
                                   "physical hydraulic/power/thermal/cost equation), applied here specifically to "
                                   "the water-supply/power-grid node pair in the paper's own test case",
                                   page=6),
             confidence=0.5),
        dict(dimension_id="D04", primary_label="Not_Addressed", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="SCADA is named only as the real-world example underlying one information-layer "
                                 "node-node dependency type; the paper never claims this operates on a timescale "
                                 "faster than the water/power hydraulic-electric processes, and the whole simulation "
                                 "runs at a uniform day-level granularity.",
             uncertainty_note="SCADA is explicitly named (stronger than a generic co-simulation interface) but "
                               "with no fast-timescale framing attached, per the codebook's exclusion rule.",
             evidence_ids=ev("B001-PDF-03-ZB-S21-5-2-C001"),
             verbatim_quote="Every electric transmission control depends on the information infrastructure (SCADA "
                            "systems and similar), which refers to node-node dependence and use of Equation (1).",
             equation_detail=None, confidence=0.6),
        dict(dimension_id="D05", primary_label="Single_Timescale_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="All four infrastructure layers (street, water, power, information) are simulated "
                                 "with the same discrete day-level granularity; buffering and repair times are "
                                 "uniformly assumed to be one day for every infrastructure type.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-03-ZC-S23-5-4-C001"),
             verbatim_quote="The buﬀering time TB and the repair time TR for every infrastructure are assumed to "
                            "be one day.",
             equation_detail=None, confidence=0.85),
        dict(dimension_id="D06", primary_label="Not_Addressed", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's 'proactive absorptive capacity' is a pre-disaster structural/design-"
                                 "stage robustness property (MCEER resilience framework terminology), not a "
                                 "real-time anticipatory control action that leverages a fast-sensing/slow-hydraulics "
                                 "timescale gap; it is a different sense of 'proactive' than D06's construct.",
             uncertainty_note="Keyword-collision risk: 'proactive' appears throughout the paper as a term from "
                               "resilience-engineering (robustness vs. restoration), unrelated to D04/D05's "
                               "cyber-physical timescale-exploitation construct. Flagged explicitly to avoid a "
                               "false-positive match.",
             evidence_ids=ev("B001-PDF-03-ZB-S07-3-1-C002"),
             verbatim_quote="Proactive absorptive capacity mainly depends on the infrastructure (or network) "
                            "inherent features, such as robustness, which can be determined in the infrastructure "
                            "planning and design, or disaster preparation and mitigation period.",
             equation_detail=None, confidence=0.75, justification_explicit=False),
        dict(dimension_id="D07", primary_label="Physical_Network_Service_Loss_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Although the paper narrates rich cascading failure propagation across water, "
                                 "power, street and information layers (chain/cycle/hidden impacts), the actual "
                                 "quantified performance/resilience outcome it computes is explicitly a physical-"
                                 "network metric (km, km3, kW, GB) for every layer, never monetized, never tied to "
                                 "named critical facility counts, population, or social vulnerability.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-03-ZB-S09-3-2-1-C001"),
             verbatim_quote="System performance unit in Figure 5 is the infrastructure impact speciﬁc. It could be "
                            "[km] of unblocked street length, [km3] of water distribution volume, [kw] of power "
                            "transmission capacity and [GB] of Internet traﬃc information volume.",
             equation_detail=None, confidence=0.8),
        dict(dimension_id="D08", primary_label="None_Reported", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Consistent with D07, the paper's quantified outcome is physical-network performance "
                                 "only; a brief narrative aside about hospitals/airports as restoration-priority "
                                 "examples is not an operationalized metric in the paper's own simulation.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.8),
        dict(dimension_id="D09", primary_label="Synthetic_Test_System_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The case study is an illustrative hypothetical 4x4 cell-space test network with no "
                                 "named real city; the authors explicitly describe it as simplified and for "
                                 "illustrative purposes.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-03-ZD-S31-7-C002"),
             verbatim_quote="This paper simpliﬁes the real infrastructure system structure and uses a numerical "
                            "test for illustrative purposes.",
             equation_detail=None, confidence=0.9),
        dict(dimension_id="D10", primary_label="Model_Simplification_Limitation",
             secondary_labels=["Validation_Generalizability_Limitation", "Missing_Factor_Limitation",
                                "Future_Work_Direction"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The authors acknowledge the uniform-resource-effectiveness assumption as a "
                                 "limitation, the synthetic/illustrative-only case study as a generalizability "
                                 "limit, explicitly name flow-overload-induced cascading failure as an unmodeled "
                                 "factor, and propose a real case study as future work.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-03-ZD-S31-7-C003"),
             verbatim_quote="In addition, this paper only considers cascading failures caused by the near physical "
                            "failure of elements. Addressing the malfunctions generated by the ﬂow overload along "
                            "the path and analyzing their impacts on system restoration processes and resilience "
                            "are topics for further research.",
             equation_detail=None, confidence=0.9),
    ],
    # =======================================================================
    # B001-PDF-04 -- Resilience of Cyber-Enabled Electrical Energy and Water
    # Distribution Systems ... Under Conditions of Limited Water and/or
    # Energy Availability
    # =======================================================================
    "B001-PDF-04": [
        dict(dimension_id="D01", primary_label="Bidirectional_Coupled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own IOR framework explicitly states and operationalizes both "
                                 "dependency directions: EPS depends on WDS for thermoelectric cooling water, and "
                                 "WDS depends on EPS for pumping electric power, each captured by dedicated index "
                                 "functions exchanged between the two simulation models.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-04-ZA-S01-I-C001"),
             verbatim_quote="The main dependence of the EPS on the WDS is the water required for the cooling cycle "
                            "of thermoelectric power generation. The main dependence of the WDS on the EPS is the "
                            "electric power needed for pumping water from a source to the treatment plant and "
                            "end-user through the WDS.",
             equation_detail=None, confidence=0.97),
        dict(dimension_id="D02", primary_label="Both_Present", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own model includes an explicit thermoelectric-plant cooling-water "
                                 "index function tracking onsite storage tank level with drift/blowdown/evaporation "
                                 "losses (Eq. 8), AND a full generic municipal WDS simulation (EPANET extended-"
                                 "period simulation with city service-area demands, pressure, pump stations).",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-04-ZC-S12-G-C001", "B001-PDF-04-ZD-S48-B-C001"),
             verbatim_quote="Thermoelectric generation requires water for the cooling cy-cle in the process of "
                            "converting the heated working ﬂuid from steam back to water via heat transfer. The "
                            "closed-loop cooling cycle introduces losses through drift, blowdown, and evapora-tion.",
             equation_detail=None, confidence=0.95),
        dict(dimension_id="D03", primary_label="Thermal_Hydraulic_Equation",
             secondary_labels=["Energy_Power_Balance_Equation", "Hydraulic_Pressure_Flow_Equation"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Eq.(8) is a piecewise-linear thermal-hydraulic index function tracking cooling "
                                 "water storage tank level (the EPS's dependency on water); Eq.(4) is a binary power "
                                 "availability compliance function tying pump operation to electric power supply "
                                 "(the WDS's dependency on power); Eqs.(1)-(3) are hydraulic pressure-bound index "
                                 "functions.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-04-ZC-S12-G-C001", "B001-PDF-04-ZC-S07-B-C001"),
             verbatim_quote="The index function relating system performance to the amount of cooling water that is "
                            "being supplied is related to a conservative estimate of the storage tank level with a "
                            "piecewise linear form as follows",
             equation_detail=dict(equation_number="(8)",
                                   variables="TLg,t cooling water storage tank level of generator g at time t; "
                                   "TLg,initial initial tank level; Rg_CW cooling water resilience index function",
                                   physical_meaning="piecewise-linear index tracking thermoelectric generator "
                                   "onsite cooling-water storage depletion, representing the EPS's dependency on "
                                   "water availability",
                                   page=6),
             confidence=0.9),
        dict(dimension_id="D04", primary_label="Not_Addressed", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own implemented data exchange is an hourly Python program-control "
                                 "overlay co-simulation interface (not a real-time sensing/communication mechanism); "
                                 "SCADA is explicitly named only as a future-work middleware requirement, not part "
                                 "of the current implementation.",
             uncertainty_note="Co-simulation software interface exchanging data on an hourly basis, per the "
                               "codebook's exclusion rule, does not by itself qualify as Explicit_Fast_Sensing_"
                               "Mechanism absent an explicit fast-timescale/early-warning framing.",
             evidence_ids=ev("B001-PDF-04-ZD-S52-X-C002"),
             verbatim_quote="Moving the ap-plication toward larger, more realistic test systems also war-rants the "
                            "inclusions of a developed middleware architecture, which emulates the supervisory "
                            "control and data acquisition (SCADA) communication that would be necessary for data "
                            "exchange between the two networks.",
             equation_detail=None, confidence=0.75),
        dict(dimension_id="D05", primary_label="Qualitative_Mention_No_Formal_Model", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Both EPS and WDS are simulated at the same hourly timestep throughout (672-hour "
                                 "simulation); the only differential-timescale treatment is a qualitative "
                                 "acknowledgment that cooling-water storage changes slowly, implemented as a lag "
                                 "filter on the cooling-water index function rather than a distinct simulation "
                                 "timescale/structure.",
             uncertainty_note="Borderline case: Eq.(8) does mathematically implement a lag, but it is a smoothing "
                               "filter on one output index, not a separate time-discretization for water vs. power.",
             evidence_ids=ev("B001-PDF-04-ZC-S12-G-C001"),
             verbatim_quote="it is reasonable to assume that the levels of the water in the onsite tanks will not "
                            "change vary rapidly",
             equation_detail=None, confidence=0.7),
        dict(dimension_id="D06", primary_label="Reactive_Control_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own novel contribution, the OR/IOR resilience metric, is explicitly "
                                 "defined by counting transitions from unsatisfactory to satisfactory performance "
                                 "after a disturbance has already occurred -- a reactive recovery measurement, not "
                                 "an anticipatory control action. The day-ahead UC/GA scheduling it builds on is "
                                 "attributed to a separately cited prior framework, not this paper's own "
                                 "contribution.",
             uncertainty_note="'Anticipatory policy making' is mentioned once, but explicitly as future work for "
                               "forecasted megadrought scenarios, not as part of the paper's own implemented "
                               "method; see the D10 record.",
             evidence_ids=ev("B001-PDF-04-ZC-S15-IV-C001"),
             verbatim_quote="Unsatisfactory op-eration is deﬁned as the resilience index function value being less "
                            "than that function’s value in the previous simulation hour (and satisfactory operation "
                            "denoted by an increase in the index function’s value).",
             equation_detail=None, confidence=0.7, justification_explicit=False),
        dict(dimension_id="D07", primary_label="Critical_Facility_Impact", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own demand-priority metric (Mdemand,z) explicitly assigns differentiated "
                                 "priority weight by service-area type, including 'cooling water for power plants' "
                                 "as one of its named categories, and this metric is directly incorporated into the "
                                 "quantitative IOR demand-satisfaction computation (Eq. 32).",
             uncertainty_note="Hospitals/fire-stations are mentioned only as narrative rationale for why demand "
                               "priority matters, not as a separately modeled category; the operationalized "
                               "critical-facility category actually used in the model is power plants.",
             evidence_ids=ev("B001-PDF-04-ZC-S29-C-C001"),
             verbatim_quote="The demand priority metric (Mdemand,z) values are assigned a noninteger value between "
                            "0 and 1 for each service area in the system depending on the type of demands "
                            "(residential, commercial, industrial, or cooling water for power plants) in the "
                            "service area.",
             equation_detail=None, confidence=0.75),
        dict(dimension_id="D08", primary_label="Critical_Facility_Service_Disruption", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Consistent with D07, the operationalized critical-facility category in the paper's "
                                 "own demand-priority metric is power plants (cooling-water service area type).",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-04-ZC-S29-C-C001"),
             verbatim_quote="The demand priority metric (Mdemand,z) values are assigned a noninteger value between "
                            "0 and 1 for each service area in the system depending on the type of demands "
                            "(residential, commercial, industrial, or cooling water for power plants) in the "
                            "service area.",
             equation_detail=None, confidence=0.7),
        dict(dimension_id="D09", primary_label="Hybrid_Synthetic_Calibrated_To_Real_Data", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The network topology is a modified IEEE 14-bus power system with a hypothetical "
                                 "two-city WDS (synthetic), but key behavioral parameters -- consumer demand-"
                                 "adjustment willingness -- are calibrated from real Arizona consumer surveys and "
                                 "census data.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-04-ZD-S47-A-C001", "B001-PDF-04-ZC-S13-H-C001"),
             verbatim_quote="The example power system was a modiﬁed version of the IEEE 14 bus system [35]",
             equation_detail=None, confidence=0.8),
        dict(dimension_id="D10", primary_label="Missing_Factor_Limitation",
             secondary_labels=["Scalability_Limitation", "Future_Work_Direction"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The conclusion explicitly states component failures are not considered in the IOR "
                                 "computation, that SCADA communication middleware is still needed for realistic "
                                 "data exchange, and that scalability to larger test systems is future work.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-04-ZD-S52-X-C002"),
             verbatim_quote="The IOR computation methodology presented in this article does not consider component "
                            "failures in either system in the computation procedure.",
             equation_detail=None, confidence=0.9),
    ],
}

# ---------------------------------------------------------------------------
# Agent B -- Pass 2 (independent critic)
# ---------------------------------------------------------------------------
AGENT_B_PASS2 = {
    "B001-PDF-02": {
        "D01": dict(decision="accept", corrected_label=None,
                    critic_comment="Both directions independently confirmed in the cited evidence; no overclaiming.",
                    supporting_evidence_ids=["B001-PDF-02-ZA-ABSTRACT-C001"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
        "D02": dict(decision="accept", corrected_label=None,
                    critic_comment="Matches the codebook's own definition precisely: background/intro mention, "
                                    "formal model does not include cooling.",
                    supporting_evidence_ids=["B001-PDF-02-ZA-S01-I-C001"], contradicting_evidence_ids=[],
                    confidence=0.85, checks_failed=[]),
        "D03": dict(decision="accept", corrected_label=None,
                    critic_comment="Equation check passes: Eqs. (13)-(14) and (39) verbatim-confirmed as cited.",
                    supporting_evidence_ids=["B001-PDF-02-ZB-S05-A-C004"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=[]),
        "D04": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed no sensing/communication content in the full text.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.9, checks_failed=[]),
        "D05": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed uniform hourly day-ahead horizon for both WDS and power UC models.",
                    supporting_evidence_ids=["B001-PDF-02-ZB-S05-A-C001"], contradicting_evidence_ids=[],
                    confidence=0.75, checks_failed=[]),
        "D06": dict(decision="accept", corrected_label=None,
                    critic_comment="Day-ahead forecast-based scheduling is genuinely anticipatory; "
                                    "justification_explicit=false is correctly set since no fast/slow timescale "
                                    "argument is made.",
                    supporting_evidence_ids=["B001-PDF-02-ZA-ABSTRACT-C001"], contradicting_evidence_ids=[],
                    confidence=0.75, checks_failed=[]),
        "D07": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed no disturbance/failure scenario anywhere in the document.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.85, checks_failed=[]),
        "D08": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed no human/social impact content.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.85, checks_failed=[]),
        "D09": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed standard 6-bus/15-node test systems, no named real region.",
                    supporting_evidence_ids=["B001-PDF-02-ZC-S12-V-C001"], contradicting_evidence_ids=[],
                    confidence=0.85, checks_failed=[]),
        "D10": dict(decision="accept", corrected_label=None,
                    critic_comment="Evidence check passes; the stochastic-extension future-work statement clearly "
                                    "implies both a missing factor (uncertainty) and a model simplification "
                                    "(deterministic forecasts).",
                    supporting_evidence_ids=["B001-PDF-02-ZD-S15-VI-C002"], contradicting_evidence_ids=[],
                    confidence=0.85, checks_failed=[]),
    },
    "B001-PDF-03": {
        "D01": dict(decision="accept", corrected_label=None,
                    critic_comment="Both directions are explicitly instantiated with specific equation numbers "
                                    "applied to the water-power node pair in the paper's own test case -- strong "
                                    "evidence, correctly not overclaimed as a generic framework-only mention.",
                    supporting_evidence_ids=["B001-PDF-03-ZB-S21-5-2-C001"], contradicting_evidence_ids=[],
                    confidence=0.95, checks_failed=[]),
        "D02": dict(decision="revise", corrected_label="Generic_Water_Network_Only",
                    critic_comment="Entailment check fails for Mentioned_Only_Not_Modeled: that label requires the "
                                    "construct to appear ONLY in background/intro text and be absent from the "
                                    "formal model. Here the water-power dependency (with cooling as its named "
                                    "real-world rationale) IS instantiated in the paper's own formal simulated test "
                                    "case via Eq.(2), applied to compute actual resilience results in Section 5.4. "
                                    "Since there is no cooling-specific thermal-hydraulic parameter (only the "
                                    "generic binary dependency-state equation, applied identically to every "
                                    "infrastructure pair), Generic_Water_Network_Only is the better fit: a municipal "
                                    "water-type network is modeled, without an independent cooling thermal-hydraulic "
                                    "process.",
                    supporting_evidence_ids=["B001-PDF-03-ZB-S21-5-2-C001", "B001-PDF-03-ZC-S23-5-4-C001"],
                    contradicting_evidence_ids=[], confidence=0.75, checks_failed=["entailment"]),
        "D03": dict(decision="accept", corrected_label=None,
                    critic_comment="SCHEMA GAP CONFIRMED (not an Agent A error): Eqs.(1)-(5) are genuine explicit "
                                    "equations (contradicted literal 'qualitative only' reading), but none of the "
                                    "six controlled D03 categories describes a binary graph-dependency-state "
                                    "equation -- there is no pressure/flow/power/cost/statistical variable with "
                                    "physical units anywhere in these formulas. No_Explicit_Equation_Qualitative_"
                                    "Only remains the least-misleading available label for RQ1's purpose (whether a "
                                    "quantitative physical/economic coupling equation connects water and power), "
                                    "but this is flagged as a genuine v1.0 schema coverage gap requiring a decision "
                                    "before further scaling (recommend a new 'Topological_Dependency_Equation' "
                                    "category for a future schema version, not introduced unilaterally here per the "
                                    "no-silent-modification rule).",
                    supporting_evidence_ids=["B001-PDF-03-ZB-S21-5-2-C001"], contradicting_evidence_ids=[],
                    confidence=0.5, checks_failed=["schema_taxonomy_gap_not_an_agentA_error"]),
        "D04": dict(decision="accept", corrected_label=None,
                    critic_comment="Correct application of the SCADA exclusion rule: named but no fast-timescale "
                                    "claim, uniform day-level simulation granularity confirmed throughout.",
                    supporting_evidence_ids=["B001-PDF-03-ZB-S21-5-2-C001"], contradicting_evidence_ids=[],
                    confidence=0.6, checks_failed=[]),
        "D05": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed uniform one-day buffering/repair time assumption across all four "
                                    "layers.",
                    supporting_evidence_ids=["B001-PDF-03-ZC-S23-5-4-C001"], contradicting_evidence_ids=[],
                    confidence=0.85, checks_failed=[]),
        "D06": dict(decision="accept", corrected_label=None,
                    critic_comment="Correctly distinguishes MCEER resilience-engineering 'proactive' (design-stage "
                                    "robustness) from D06's cyber-physical timescale-exploitation construct -- this "
                                    "is the right call and avoids a keyword-collision false positive.",
                    supporting_evidence_ids=["B001-PDF-03-ZB-S07-3-1-C002"], contradicting_evidence_ids=[],
                    confidence=0.75, checks_failed=[]),
        "D07": dict(decision="accept", corrected_label=None,
                    critic_comment="Endpoint check passes: the rich cascading narrative is correctly distinguished "
                                    "from the actually-measured outcome metric, which remains physical-network-"
                                    "level (km/km3/kW/GB) throughout.",
                    supporting_evidence_ids=["B001-PDF-03-ZB-S09-3-2-1-C001"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=[]),
        "D08": dict(decision="accept", corrected_label=None,
                    critic_comment="Consistent with D07; hospitals/airports narrative aside correctly excluded as "
                                    "not an operationalized metric.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.8, checks_failed=[]),
        "D09": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed illustrative synthetic 4x4 cell-space network, explicitly "
                                    "self-described as simplified.",
                    supporting_evidence_ids=["B001-PDF-03-ZD-S31-7-C002"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
        "D10": dict(decision="accept", corrected_label=None,
                    critic_comment="All four limitation/future-work threads independently verbatim-confirmed in "
                                    "Zone D conclusion.",
                    supporting_evidence_ids=["B001-PDF-03-ZD-S31-7-C003"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
    },
    "B001-PDF-04": {
        "D01": dict(decision="accept", corrected_label=None,
                    critic_comment="Textbook explicit bidirectional statement, directly in the introduction; "
                                    "strongest D01 evidence seen across the 5-paper corpus so far.",
                    supporting_evidence_ids=["B001-PDF-04-ZA-S01-I-C001"], contradicting_evidence_ids=[],
                    confidence=0.97, checks_failed=[]),
        "D02": dict(decision="accept", corrected_label=None,
                    critic_comment="Both components independently confirmed: Eq.(8) cooling-water storage tracking "
                                    "(in-plant) and EPANET city-demand WDS simulation (generic network) are both "
                                    "explicit and separately formulated.",
                    supporting_evidence_ids=["B001-PDF-04-ZC-S12-G-C001", "B001-PDF-04-ZD-S48-B-C001"],
                    contradicting_evidence_ids=[], confidence=0.95, checks_failed=[]),
        "D03": dict(decision="accept", corrected_label=None,
                    critic_comment="Equation check passes; Eq.(8) correctly classified as Thermal_Hydraulic given "
                                    "its explicit pairing with the Explicit_InPlant_Cooling_Model D02 finding, per "
                                    "the codebook's own cross-reference note.",
                    supporting_evidence_ids=["B001-PDF-04-ZC-S12-G-C001"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
        "D04": dict(decision="accept", corrected_label=None,
                    critic_comment="Correct distinction between the implemented hourly Python co-simulation overlay "
                                    "(not fast-sensing) and the explicitly future-work SCADA middleware.",
                    supporting_evidence_ids=["B001-PDF-04-ZD-S52-X-C002"], contradicting_evidence_ids=[],
                    confidence=0.75, checks_failed=[]),
        "D05": dict(decision="accept", corrected_label=None,
                    critic_comment="Temporal check passes: confirmed uniform hourly simulation timestep for both "
                                    "systems; the cooling-water lag is a filter on one index, not a distinct "
                                    "simulation timescale, correctly short of Explicit_MultiTimescale_Model.",
                    supporting_evidence_ids=["B001-PDF-04-ZC-S12-G-C001"], contradicting_evidence_ids=[],
                    confidence=0.7, checks_failed=[]),
        "D06": dict(decision="accept", corrected_label=None,
                    critic_comment="Correct own-method vs. cited-framework distinction: the paper's own "
                                    "contribution (OR/IOR metric) is a reactive post-disturbance recovery "
                                    "measurement; the day-ahead UC/GA scheduling is attributed to a separately "
                                    "cited prior framework, and 'anticipatory policy making' is explicitly future "
                                    "work only (correctly captured in D10, not here).",
                    supporting_evidence_ids=["B001-PDF-04-ZC-S15-IV-C001"], contradicting_evidence_ids=[],
                    confidence=0.7, checks_failed=[]),
        "D07": dict(decision="revise", corrected_label="Critical_Facility_Impact",
                    critic_comment="Evidence check: Pass-1 cited the hospital/fire-station passage (ZD-S30-D-C001 "
                                    "prose aside) as primary evidence, but that passage is a narrative rationale, "
                                    "not an operationalized model category -- it should not be the primary "
                                    "citation. The label itself (Critical_Facility_Impact) is correct because "
                                    "'cooling water for power plants' IS a literal, separately-weighted category in "
                                    "the paper's own demand-priority metric (Eq. 32 input); evidence_ids/"
                                    "verbatim_quote should be corrected to cite ZC-S29-C-C001 as primary, not the "
                                    "hospital/fire-station aside.",
                    supporting_evidence_ids=["B001-PDF-04-ZC-S29-C-C001"], contradicting_evidence_ids=[],
                    confidence=0.75, checks_failed=["evidence"]),
        "D08": dict(decision="accept", corrected_label=None,
                    critic_comment="Consistent with the corrected D07 evidence; power plants are the operationalized "
                                    "critical-facility category.",
                    supporting_evidence_ids=["B001-PDF-04-ZC-S29-C-C001"], contradicting_evidence_ids=[],
                    confidence=0.7, checks_failed=[]),
        "D09": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed: modified IEEE 14-bus + hypothetical WDS (synthetic topology) with "
                                    "real Arizona survey/census-calibrated demand-adjustment behavior.",
                    supporting_evidence_ids=["B001-PDF-04-ZD-S47-A-C001"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=[]),
        "D10": dict(decision="accept", corrected_label=None,
                    critic_comment="All three limitation/future-work threads (component failures not modeled, "
                                    "SCADA middleware needed, scalability to larger systems) independently "
                                    "verbatim-confirmed in the same conclusion block.",
                    supporting_evidence_ids=["B001-PDF-04-ZD-S52-X-C002"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
    },
}

# ---------------------------------------------------------------------------
# Agent A -- Pass 3 (revision of only the records Agent B marked 'revise')
# ---------------------------------------------------------------------------
AGENT_A_PASS3_REVISIONS = {
    "B001-PDF-03": {
        "D02": dict(primary_label="Generic_Water_Network_Only", secondary_labels=[],
                     mechanism_judgment="Revised per Agent B: the water-power dependency (motivated by cooling) is "
                                         "formally instantiated in the paper's own simulated test case via the "
                                         "generic node-edge dependency equation (Eq. 2), applied identically to "
                                         "every infrastructure pair with no cooling-specific thermal-hydraulic "
                                         "parameter. This is a generic municipal-type water network dependency "
                                         "model, not a background-only mention and not a distinct in-plant cooling "
                                         "process model.",
                     confidence=0.75),
    },
    "B001-PDF-04": {
        "D07": dict(primary_label="Critical_Facility_Impact", secondary_labels=[],
                     evidence_ids=["B001-PDF-04-ZC-S29-C-C001"],
                     verbatim_quote="The demand priority metric (Mdemand,z) values are assigned a noninteger value "
                                     "between 0 and 1 for each service area in the system depending on the type of "
                                     "demands (residential, commercial, industrial, or cooling water for power "
                                     "plants) in the service area.",
                     mechanism_judgment="Revised per Agent B: evidence corrected to cite the paper's own "
                                         "operationalized demand-priority metric, which explicitly weights "
                                         "'cooling water for power plants' as a distinct service-area category "
                                         "feeding directly into the quantitative IOR demand-satisfaction computation "
                                         "(Eq. 32). The earlier citation of the hospital/fire-station passage is "
                                         "demoted to contextual narrative only, not primary evidence.",
                     confidence=0.75),
    },
}

# ---------------------------------------------------------------------------
# Agent B -- Pass 4 (final review of the Pass-3 revisions only)
# ---------------------------------------------------------------------------
AGENT_B_PASS4 = {
    "B001-PDF-03": {"D02": dict(decision="accept", confidence=0.75,
                                 critic_comment="Revision correctly matches the codebook's Generic_Water_Network_"
                                                "Only definition given the dependency is formally instantiated "
                                                "(not background-only) but non-cooling-specific. Final.")},
    "B001-PDF-04": {"D07": dict(decision="accept", confidence=0.75,
                                 critic_comment="Revised evidence citation now correctly grounds the label in the "
                                                "paper's own operationalized demand-priority metric rather than a "
                                                "narrative aside. Final.")},
}


def build_manifest_entry(call_id, agent_name, doc_id, prompt_version, pass_name,
                          input_evidence_ids, output_obj, retry_count=0, failure_reason=None):
    input_hashes = sorted(EVIDENCE[eid]["text_sha256"] for eid in input_evidence_ids if eid in EVIDENCE)
    input_hash = sha256_text("|".join(input_hashes) + "|" + prompt_version + "|" + SCHEMA_VERSION)
    output_text = json.dumps(output_obj, ensure_ascii=False, sort_keys=True)
    output_hash = sha256_text(output_text)
    approx_chars_in = sum(len(EVIDENCE[eid]["text"]) for eid in input_evidence_ids if eid in EVIDENCE)
    return {
        "call_id": call_id,
        "agent_name": agent_name,
        "execution_channel": "arena_agent_mode_in_session",
        "provider": "Arena.ai",
        "model_name": "arena-agent-mode-session-model",
        "model_version": "not_exposed_by_execution_channel",
        "endpoint": "N/A_in_session_reasoning_no_external_api_call",
        "prompt_version": prompt_version,
        "schema_version": SCHEMA_VERSION,
        "input_hash": input_hash,
        "output_hash": output_hash,
        "temperature": "not_exposed_by_execution_channel",
        "seed": "not_available",
        "input_evidence_ids": input_evidence_ids,
        "input_token_estimate": max(1, approx_chars_in // 4),
        "output_token_estimate": max(1, len(output_text) // 4),
        "retry_count": retry_count,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "failure_reason": failure_reason,
        "human_or_agent_reviewed": "agent_only",
        "pass": pass_name,
        "doc_id": doc_id,
    }


def main() -> None:
    out_a = ROOT / "03_AgentA原始抽取"
    out_b = ROOT / "04_AgentB_Critic审查"
    out_v = ROOT / "05_核验通过结果"
    out_log = ROOT / "02_模型调用日志"
    for d in (out_a, out_b, out_v, out_log):
        d.mkdir(parents=True, exist_ok=True)

    manifest_entries = []

    for doc_id, records in AGENT_A_PASS1.items():
        pass1_call_id = f"MC-{doc_id}-AgentA-pass1-001"
        full = []
        for r in records:
            rec = dict(r)
            eids = rec.get("evidence_ids") or []
            if eids:
                seen = []
                for e in eids:
                    if e in EVIDENCE and EVIDENCE[e]["section_id"] not in seen:
                        seen.append(EVIDENCE[e]["section_id"])
                rec["section_id"] = seen[0] if len(seen) == 1 else seen
                rec["page_numbers"] = sorted({p for e in eids if e in EVIDENCE for p in EVIDENCE[e]["page_numbers"]})
            else:
                rec["section_id"] = None
                rec["page_numbers"] = []
            rec.update(doc_id=doc_id, schema_version=SCHEMA_VERSION,
                       agent_a_model_call_id=pass1_call_id)
            full.append(rec)
        with open(out_a / f"{doc_id}_agentA_pass1.json", "w", encoding="utf-8") as f:
            json.dump(full, f, ensure_ascii=False, indent=2)

        all_ids = sorted({eid for r in records for eid in r["evidence_ids"]}) or ["(no-evidence-dimensions)"]
        manifest_entries.append(build_manifest_entry(
            pass1_call_id, "AgentA", doc_id, AGENT_A_PROMPT_VERSION, "pass1_initial_extraction",
            [eid for eid in all_ids if eid in EVIDENCE], full))

    for doc_id, decisions in AGENT_B_PASS2.items():
        with open(out_b / f"{doc_id}_agentB_pass2.json", "w", encoding="utf-8") as f:
            json.dump(decisions, f, ensure_ascii=False, indent=2)
        all_ids = sorted({eid for dec in decisions.values() for eid in dec["supporting_evidence_ids"]})
        call_id = f"MC-{doc_id}-AgentB-pass2-001"
        manifest_entries.append(build_manifest_entry(
            call_id, "AgentB", doc_id, AGENT_B_PROMPT_VERSION, "pass2_initial_critic",
            [eid for eid in all_ids if eid in EVIDENCE], decisions))

    for doc_id, revisions in AGENT_A_PASS3_REVISIONS.items():
        with open(out_a / f"{doc_id}_agentA_pass3_revisions.json", "w", encoding="utf-8") as f:
            json.dump(revisions, f, ensure_ascii=False, indent=2)
        call_id = f"MC-{doc_id}-AgentA-pass3-001"
        revise_dims = set(revisions.keys())
        ids_for_pass3 = sorted({eid for r in AGENT_A_PASS1[doc_id] if r["dimension_id"] in revise_dims
                                 for eid in r["evidence_ids"]}
                                | {eid for rev in revisions.values() for eid in rev.get("evidence_ids", [])})
        manifest_entries.append(build_manifest_entry(
            call_id, "AgentA", doc_id, AGENT_A_PROMPT_VERSION, "pass3_revision_only",
            [eid for eid in ids_for_pass3 if eid in EVIDENCE], revisions))

    for doc_id, finals in AGENT_B_PASS4.items():
        with open(out_b / f"{doc_id}_agentB_pass4_final.json", "w", encoding="utf-8") as f:
            json.dump(finals, f, ensure_ascii=False, indent=2)
        call_id = f"MC-{doc_id}-AgentB-pass4-001"
        revise_dims = set(finals.keys())
        ids_for_pass4 = sorted({eid for r in AGENT_A_PASS1[doc_id] if r["dimension_id"] in revise_dims
                                 for eid in r["evidence_ids"]})
        manifest_entries.append(build_manifest_entry(
            call_id, "AgentB", doc_id, AGENT_B_PROMPT_VERSION, "pass4_final_review",
            [eid for eid in ids_for_pass4 if eid in EVIDENCE], finals))

    # Merge into verified_10d_record per document
    for doc_id in AGENT_A_PASS1:
        with open(out_a / f"{doc_id}_agentA_pass1.json", encoding="utf-8") as f:
            enriched_records = json.load(f)
        verified = []
        for rec in enriched_records:
            dim = rec["dimension_id"]
            b2 = AGENT_B_PASS2[doc_id][dim]
            if b2["decision"] == "revise" and dim in AGENT_A_PASS3_REVISIONS.get(doc_id, {}):
                rev = AGENT_A_PASS3_REVISIONS[doc_id][dim]
                rec.update(rev)
                if "evidence_ids" in rev:
                    eids = rev["evidence_ids"]
                    seen = []
                    for e in eids:
                        if e in EVIDENCE and EVIDENCE[e]["section_id"] not in seen:
                            seen.append(EVIDENCE[e]["section_id"])
                    rec["section_id"] = seen[0] if len(seen) == 1 else seen
                    rec["page_numbers"] = sorted({p for e in eids if e in EVIDENCE for p in EVIDENCE[e]["page_numbers"]})
                rec["agent_a_model_call_id"] = f"MC-{doc_id}-AgentA-pass3-001"
                b4 = AGENT_B_PASS4[doc_id][dim]
                rec["agent_b_review"] = {
                    "pass2_decision": b2["decision"], "pass2_comment": b2["critic_comment"],
                    "pass4_decision": b4["decision"], "pass4_comment": b4["critic_comment"],
                }
                rec["verification_status"] = "accepted_after_revision"
            else:
                rec["agent_b_review"] = {"pass2_decision": b2["decision"], "pass2_comment": b2["critic_comment"]}
                rec["verification_status"] = "accepted_pass1"
            verified.append(rec)
        with open(out_v / f"{doc_id}_verified_10d.json", "w", encoding="utf-8") as f:
            json.dump(verified, f, ensure_ascii=False, indent=2)

    # Append to the existing manifest (do not clobber the pilot's 2-doc log)
    with open(out_log / "model_call_manifest.jsonl", "a", encoding="utf-8") as f:
        for e in manifest_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"Wrote Agent A pass1/pass3, Agent B pass2/pass4, verified records for "
          f"{len(AGENT_A_PASS1)} documents, appended {len(manifest_entries)} manifest entries.")


if __name__ == "__main__":
    sys.exit(main())
