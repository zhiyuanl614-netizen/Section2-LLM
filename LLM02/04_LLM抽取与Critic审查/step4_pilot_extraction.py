#!/usr/bin/env python3
"""Step 4 pilot: Agent A -> Agent B -> Agent A(revise) -> Agent B(final) on
B001-PDF-01 and B001-PDF-05, per agent_prompts_and_manifest_v1_LOCKED.md.

This script does NOT call any external LLM. The structured content in
AGENT_A_PASS1 and AGENT_B_PASS2 below is the actual output of the Arena.ai
Agent performing the real extraction/critic reasoning directly in-session
(user decision `agent_real_llm`), transcribed here for persistence, hashing,
and manifest logging. Re-running this script does not re-derive the
judgments; it reproducibles the artifact files deterministically from the
already-performed reasoning.
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
# Agent A — Pass 1 (initial extraction), produced by direct agent reasoning
# over the full Zone A-D text of each pilot document (coverage pass).
# ---------------------------------------------------------------------------
AGENT_A_PASS1 = {
    "B001-PDF-01": [
        dict(dimension_id="D01", primary_label="Bidirectional_Coupled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own two-stage dispatch treats WSS loads (desalination, pumping) as "
                                 "controllable resources driven by MG/EG price and fluctuation signals (Power->Water), "
                                 "while WSS hydraulic stability/split-system constraints bound MG dispatch and the WSS "
                                 "actively supports the external grid (Water->Power), i.e. explicit bidirectional coupling.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-01-ZA-ABSTRACT-C001", "B001-PDF-01-ZB-S06-2-2-C001"),
             verbatim_quote="the day-head decisions fully consider the real-time power fluctuation, and the real-time "
                            "stage corrects renewable generation deviation and supports external grid",
             equation_detail=None, confidence=0.85),
        dict(dimension_id="D02", primary_label="Generic_Water_Network_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The water supply model covers desalination (DD), reservoirs, water pumps (WP), water "
                                 "tanks and distribution pipes for island community usage; no power-plant cooling "
                                 "water/condenser thermal process is modeled.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-01-ZB-S05-2-1-C001"),
             verbatim_quote="The WSS consists of a DD, reservoirs, WPs, WTs, water pipes, and water usage loads.",
             equation_detail=None, confidence=0.9),
        dict(dimension_id="D03", primary_label="Hydraulic_Pressure_Flow_Equation",
             secondary_labels=["Energy_Power_Balance_Equation", "Economic_Cost_Coupling_Equation"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Eqs (1)-(8) define nodal correlation matrices and pressure/flow balance for the split "
                                 "WSS; Eq (34) balances DD/WP/PV/Wind/Load power; the MILP objective (40) jointly "
                                 "minimizes cost across water and power variables.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-01-ZB-S05-2-1-C001", "B001-PDF-01-ZB-S05-2-1-C002",
                              "B001-PDF-01-ZB-S06-2-2-C003", "B001-PDF-01-ZB-S07-2-3-C001"),
             verbatim_quote="(1) expresses the nodal correlation relationship before and after the large system "
                            "splitting, (2) denotes the pipe flow balance constraint",
             equation_detail=dict(equation_number="(1)-(8)", variables="Z,I,A nodal correlation matrices; Q flow; H pressure head",
                                   physical_meaning="nodal hydraulic coupling before/after WSS splitting", page=3),
             confidence=0.8),
        dict(dimension_id="D04", primary_label="Not_Addressed", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method", mechanism_judgment="No sensing/communication/monitoring architecture is described anywhere in the paper.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.9),
        dict(dimension_id="D05", primary_label="Explicit_MultiTimescale_Model", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The method explicitly separates a day-ahead stage (hourly) from a real-time stage "
                                 "(minute-level, via Latin hypercube sampling), i.e. a formal two-timescale structure.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-01-ZB-S06-2-2-C001", "B001-PDF-01-ZB-S06-2-2-C002"),
             verbatim_quote="we can use Latin hypercube sampling method to simulate the real-time power on the "
                            "minute-time scale",
             equation_detail=None, confidence=0.95),
        dict(dimension_id="D06", primary_label="Proactive_Anticipatory_Control", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The day-ahead stage explicitly hardens the schedule against simulated real-time "
                                 "fluctuation scenarios ahead of time (Latin hypercube sampling of anticipated "
                                 "fluctuation), which is an anticipatory design choice motivated by the stated "
                                 "shortcoming of classic day-ahead models.",
             uncertainty_note="The real-time stage's MPC-based correction could also be read as reactive (responds "
                               "to realized deviations); primary label reflects the day-ahead stage's explicit "
                               "anticipatory design, which is the paper's main proactive contribution.",
             evidence_ids=ev("B001-PDF-01-ZB-S06-2-2-C001", "B001-PDF-01-ZB-S06-2-2-C002"),
             verbatim_quote="a novel day-head model considering the real-time power fluctuation is proposed",
             equation_detail=None, confidence=0.75, justification_explicit=True),
        dict(dimension_id="D07", primary_label="Not_Stated_In_Text", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper is a steady-state optimal scheduling study with no disturbance/failure "
                                 "scenario or cascading-impact analysis in its own method.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.85),
        dict(dimension_id="D08", primary_label="None_Reported", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="No population, critical-facility, or social-vulnerability impact metric appears "
                                 "anywhere in the case study.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.85),
        dict(dimension_id="D09", primary_label="Synthetic_Test_System_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The case study uses 'the typical WSS [10]' with no named real city/utility; "
                                 "simulations coded in MATLAB/Gurobi on a generic grid-connected MG test setup.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-01-ZD-S09-3-1-C001"),
             verbatim_quote="A grid-connected MG integrating a WSS is used to verify the effectiveness of the "
                            "proposed strategy.",
             equation_detail=None, confidence=0.8),
        dict(dimension_id="D10", primary_label="Validation_Generalizability_Limitation",
             secondary_labels=["Future_Work_Direction"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Authors acknowledge theoretical details neglected relative to practical application "
                                 "and plan a real case study; they also flag extreme-weather resilience as unaddressed "
                                 "future work.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-01-ZD-S14-4-C001"),
             verbatim_quote="some technical details neglected in the theoretical discussion of this paper may be of "
                            "great importance in practical application. Therefore, we will conduct a real case study "
                            "in the future. Additionally, the extreme weather significantly affects the reliability "
                            "of the power supply. The resilience of power gird integrating water supply systems will "
                            "also our future work.",
             equation_detail=None, confidence=0.8),
    ],
    "B001-PDF-05": [
        dict(dimension_id="D01", primary_label="Power_to_Water", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper explicitly restricts its own dependent-failure model to a one-way "
                                 "power-to-water dependency and explicitly states the reverse direction is not modeled.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-05-ZC-S10-2-4-C001", "B001-PDF-05-ZD-S17-4-C003"),
             verbatim_quote="this study strictly concentrates on the unidirectional power-to-water dependency",
             equation_detail=None, confidence=0.97),
        dict(dimension_id="D02", primary_label="Mentioned_Only_Not_Modeled", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's own model covers substation power supply to water-treatment-plant pumps, "
                                 "not power-plant cooling water; its own limitations section explicitly names "
                                 "power-plant/substation cooling-system water dependency as unaddressed future work.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-05-ZD-S17-4-C003"),
             verbatim_quote="Quantifying the energy dependence of power plants or substation cooling systems on "
                            "water supply capacity will be a critical focus for future research.",
             equation_detail=None, confidence=0.8),
        dict(dimension_id="D03", primary_label="Hydraulic_Pressure_Flow_Equation",
             secondary_labels=["Energy_Power_Balance_Equation"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Eq.(13) is a first-principles energy-transfer equation converting the electrical "
                                 "power consumed by water pumps into hydraulic power (flow x head); Eqs.(5)-(9) are "
                                 "ACOPF power-balance equations feeding the dependency model.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-05-ZC-S10-2-4-C002", "B001-PDF-05-ZC-S10-2-4-C003", "B001-PDF-05-ZC-S09-2-3-2-C002"),
             verbatim_quote="Eq. (13) describes the energy transfer between the power and water pressure by the "
                            "pumps in the water treatment plant.",
             equation_detail=dict(equation_number="(13)",
                                   variables="rho water density, g gravity, Qe volumetric flow rate, H* total nodal head, eta_e efficiency",
                                   physical_meaning="direct energy-transfer equation converting electrical pump power into hydraulic power",
                                   page=6),
             confidence=0.95),
        dict(dimension_id="D04", primary_label="Not_Addressed", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="This is a probabilistic post-event seismic performance model (QMC damage sampling), "
                                 "not a real-time sensing/communication architecture.",
             uncertainty_note=None, evidence_ids=[], verbatim_quote=None, equation_detail=None, confidence=0.85),
        dict(dimension_id="D05", primary_label="Single_Timescale_Only", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The model compares pre- vs post-earthquake steady-state snapshots via QMC sampling; "
                                 "the paper self-describes this as a steady-state analysis.",
             uncertainty_note="Tentative label pending Critic review -- see pass 2.",
             evidence_ids=ev("B001-PDF-05-ZD-S17-4-C003"),
             verbatim_quote="This study conducts a steady-state power flow analysis tailored to city-scale "
                            "distribution networks in evaluating the seismic performance of the PS.",
             equation_detail=None, confidence=0.6),
        dict(dimension_id="D06", primary_label="Proactive_Anticipatory_Control", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The paper's sensitivity analysis leads to an explicit recommendation to "
                                 "proactively prioritize grid power assignment to water treatment plants as an "
                                 "emergency mitigation strategy.",
             uncertainty_note="Derived mitigation recommendation from sensitivity analysis, not an implemented "
                               "closed-loop real-time controller.",
             evidence_ids=ev("B001-PDF-05-ZC-S15-3-4-C003", "B001-PDF-05-ZD-S17-4-C003"),
             verbatim_quote="proactively prioritizing grid power assignment to WTPs (i.e., assign power supply to "
                            "WTPs by residual power capacity in substations) serves as a highly effective "
                            "emergency response strategy to maximize the seismic performance of WDS.",
             equation_detail=None, confidence=0.8, justification_explicit=True),
        dict(dimension_id="D07", primary_label="Critical_Facility_Impact", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The dependent-failure model explicitly characterizes cascading failure propagation "
                                 "from the power system to named critical facilities (water treatment plants) via "
                                 "energy conservation, beyond generic physical-network service loss.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-05-ZD-S17-4-C001"),
             verbatim_quote="This dependent failure model characterizes the cascading failure propagation process "
                            "between these two heterogeneous infrastructure systems through energy conservation "
                            "based on the dependent substations and pumps of the water treatment plant.",
             equation_detail=None, confidence=0.85),
        dict(dimension_id="D08", primary_label="Named_Case_Region_Impact", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="The case study is grounded in a real named region (Shelby County, Tennessee, plus "
                                 "a second NY, China case); no explicit population-count or social-vulnerability-index "
                                 "metric is reported.",
             uncertainty_note="No demographic/vulnerability quantification found; only named-region case selection.",
             evidence_ids=ev("B001-PDF-05-ZD-S11-3-C001"),
             verbatim_quote="This section first introduces the power-water system (PWS) case in Shelby County, "
                            "Tennessee.",
             equation_detail=None, confidence=0.9),
        dict(dimension_id="D09", primary_label="Real_World_Named_Region", secondary_labels=[],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Validation uses real documented WDS/PS topology for Shelby County, Tennessee "
                                 "(9 water sources, 71 pipelines, 49 user nodes; 8 power plants, 51 substations, "
                                 "71 distribution lines) and a second real case in NY, China.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-05-ZD-S11-3-C001"),
             verbatim_quote="the water distribution system (WDS) of this PWS comprises 9 water sources, 71 "
                            "pipelines, and 49 user nodes, whereas its power system (PS) consists of 8 power "
                            "plants, 21 12-kV substations, 30 23-kV substations, and 71 distribution lines.",
             equation_detail=None, confidence=0.95),
        dict(dimension_id="D10", primary_label="Missing_Factor_Limitation",
             secondary_labels=["Model_Simplification_Limitation", "Scalability_Limitation", "Future_Work_Direction"],
             own_method_vs_cited="Paper_Own_Method",
             mechanism_judgment="Authors explicitly list unaddressed reverse PS-on-WDS dependency, steady-state/"
                                 "distribution-only scope needing regional-scale extension, and unmodeled direct "
                                 "structural damage to WTPs, each tied to a named future-research direction.",
             uncertainty_note=None,
             evidence_ids=ev("B001-PDF-05-ZD-S17-4-C003", "B001-PDF-05-ZD-S17-4-C004"),
             verbatim_quote="the reverse dependency of the PS on the WDS is not addressed. Quantifying the energy "
                            "dependence of power plants or substation cooling systems on water supply capacity will "
                            "be a critical focus for future research.",
             equation_detail=None, confidence=0.9),
    ],
}

# ---------------------------------------------------------------------------
# Agent B — Pass 2 (independent critic), produced by direct agent reasoning
# re-reading the SAME raw evidence blocks independently (not Agent A's
# reasoning trace) and applying the 7 checks from AgentB_prompt_v1.0.
# ---------------------------------------------------------------------------
AGENT_B_PASS2 = {
    "B001-PDF-01": {
        "D01": dict(decision="accept", corrected_label=None,
                    critic_comment="Entailment/direction checks pass: abstract and S06-2-2-C001 jointly support both "
                                    "directions (price-driven load control = Power->Water; WSS load shifting supports "
                                    "EG = Water->Power). Evidence check: quotes match verbatim source. "
                                    "[Shared-execution-channel caveat per prompt file section 0 applies.]",
                    supporting_evidence_ids=["B001-PDF-01-ZA-ABSTRACT-C001", "B001-PDF-01-ZB-S06-2-2-C001"],
                    contradicting_evidence_ids=[], confidence=0.85, checks_failed=[]),
        "D02": dict(decision="accept", corrected_label=None,
                    critic_comment="Entailment passes; no cooling-specific language present anywhere in Zone B, "
                                    "correctly excludes Explicit_InPlant_Cooling_Model.",
                    supporting_evidence_ids=["B001-PDF-01-ZB-S05-2-1-C001"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
        "D03": dict(decision="accept", corrected_label=None,
                    critic_comment="Equation check passes: eq numbers and variable descriptions match the cited "
                                    "evidence blocks' verbatim equation text.",
                    supporting_evidence_ids=["B001-PDF-01-ZB-S05-2-1-C001", "B001-PDF-01-ZB-S07-2-3-C001"],
                    contradicting_evidence_ids=[], confidence=0.8, checks_failed=[]),
        "D04": dict(decision="accept", corrected_label=None,
                    critic_comment="Independent re-read of all 28 blocks confirms no sensing/communication content.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.9, checks_failed=[]),
        "D05": dict(decision="accept", corrected_label=None,
                    critic_comment="Temporal check passes: day-ahead (hourly) vs real-time (minute, Latin hypercube) "
                                    "is an explicit, well-evidenced two-timescale structure.",
                    supporting_evidence_ids=["B001-PDF-01-ZB-S06-2-2-C001", "B001-PDF-01-ZB-S06-2-2-C002"],
                    contradicting_evidence_ids=[], confidence=0.95, checks_failed=[]),
        "D06": dict(decision="accept", corrected_label=None,
                    critic_comment="Accept with the uncertainty already flagged by Agent A; day-ahead stage is "
                                    "genuinely anticipatory per its own stated design rationale (justification_explicit=true "
                                    "is well supported). No contradiction found in Zone B/C text.",
                    supporting_evidence_ids=["B001-PDF-01-ZB-S06-2-2-C001"], contradicting_evidence_ids=[],
                    confidence=0.78, checks_failed=[]),
        "D07": dict(decision="accept", corrected_label=None,
                    critic_comment="Endpoint check passes: confirmed no disturbance/cascading scenario anywhere in "
                                    "the document; Not_Stated_In_Text is the correct fallback (not "
                                    "Explicitly_Not_Considered, since the paper never explicitly disclaims modeling "
                                    "cascading failure -- it simply never addresses it).",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.85, checks_failed=[]),
        "D08": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed no human/social impact content anywhere in the document.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.85, checks_failed=[]),
        "D09": dict(decision="accept", corrected_label=None,
                    critic_comment="Evidence check passes; 'typical WSS [10]' with MATLAB/Gurobi simulation and no "
                                    "named city correctly supports Synthetic_Test_System_Only.",
                    supporting_evidence_ids=["B001-PDF-01-ZD-S09-3-1-C001"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=[]),
        "D10": dict(decision="revise", corrected_label="Validation_Generalizability_Limitation",
                    critic_comment="Entailment check: the quote also explicitly flags extreme-weather resilience as "
                                    "NOT currently modeled ('will also our future work'), which is a named omitted "
                                    "factor, not only a generic future-work pointer. Secondary labels should include "
                                    "Missing_Factor_Limitation in addition to Future_Work_Direction; Agent A's pass-1 "
                                    "secondary_labels list was incomplete.",
                    supporting_evidence_ids=["B001-PDF-01-ZD-S14-4-C001"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=["entailment"]),
    },
    "B001-PDF-05": {
        "D01": dict(decision="accept", corrected_label=None,
                    critic_comment="Direction check passes: 'strictly concentrates on the unidirectional "
                                    "power-to-water dependency' is an unambiguous, explicit statement.",
                    supporting_evidence_ids=["B001-PDF-05-ZC-S10-2-4-C001"], contradicting_evidence_ids=[],
                    confidence=0.97, checks_failed=[]),
        "D02": dict(decision="accept", corrected_label=None,
                    critic_comment="Entailment passes: the own-method model is WTP-pump power consumption, not "
                                    "power-plant cooling; the explicit future-work sentence about 'power plants or "
                                    "substation cooling systems' correctly supports Mentioned_Only_Not_Modeled "
                                    "rather than Not_Stated_In_Text.",
                    supporting_evidence_ids=["B001-PDF-05-ZD-S17-4-C003"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=[]),
        "D03": dict(decision="accept", corrected_label=None,
                    critic_comment="Equation check passes: Eq.(13) is verbatim-confirmed as an energy-transfer "
                                    "(electrical-to-hydraulic power) equation; page and variable list match source.",
                    supporting_evidence_ids=["B001-PDF-05-ZC-S10-2-4-C002", "B001-PDF-05-ZC-S10-2-4-C003"],
                    contradicting_evidence_ids=[], confidence=0.95, checks_failed=[]),
        "D04": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed: this is a probabilistic post-event QMC model, no sensing/comm content.",
                    supporting_evidence_ids=[], contradicting_evidence_ids=[], confidence=0.85, checks_failed=[]),
        "D05": dict(decision="revise", corrected_label="Not_Addressed",
                    critic_comment="Temporal check FAILS as labeled: the paper's 'steady-state' framing is a "
                                    "pre/post-earthquake snapshot comparison, not an engagement with the "
                                    "water-thermal-hydraulic-vs-power slow/fast timescale construct that D05 asks "
                                    "about at all. Labeling it Single_Timescale_Only risks implying the paper "
                                    "considered and rejected an explicit multi-timescale treatment of this specific "
                                    "construct, which it did not -- it simply operates in a different analytical "
                                    "frame (probabilistic damage sampling, not dispatch/control timescales). "
                                    "Not_Addressed is the more accurate and honest fallback.",
                    supporting_evidence_ids=["B001-PDF-05-ZD-S17-4-C003"], contradicting_evidence_ids=[],
                    confidence=0.75, checks_failed=["temporal"]),
        "D06": dict(decision="accept", corrected_label=None,
                    critic_comment="Entailment check passes: 'proactively prioritizing' is a verbatim match; "
                                    "uncertainty note correctly distinguishes this from an implemented controller.",
                    supporting_evidence_ids=["B001-PDF-05-ZC-S15-3-4-C003"], contradicting_evidence_ids=[],
                    confidence=0.8, checks_failed=[]),
        "D07": dict(decision="accept", corrected_label=None,
                    critic_comment="Endpoint check passes: water treatment plants are explicitly named as the "
                                    "impacted critical facility, matching the codebook's own D07 example; this is "
                                    "correctly distinguished from generic Physical_Network_Service_Loss_Only.",
                    supporting_evidence_ids=["B001-PDF-05-ZD-S17-4-C001"], contradicting_evidence_ids=[],
                    confidence=0.85, checks_failed=[]),
        "D08": dict(decision="accept", corrected_label=None,
                    critic_comment="Confirmed no population/social-vulnerability metric; Named_Case_Region_Impact "
                                    "correctly reflects the real Shelby County / NY case selection without "
                                    "overclaiming demographic analysis.",
                    supporting_evidence_ids=["B001-PDF-05-ZD-S11-3-C001"], contradicting_evidence_ids=[],
                    confidence=0.9, checks_failed=[]),
        "D09": dict(decision="accept", corrected_label=None,
                    critic_comment="Evidence check passes: real topology counts (9 water sources, 71 pipelines, "
                                    "etc.) for a named region are verbatim-confirmed.",
                    supporting_evidence_ids=["B001-PDF-05-ZD-S11-3-C001"], contradicting_evidence_ids=[],
                    confidence=0.95, checks_failed=[]),
        "D10": dict(decision="accept", corrected_label=None,
                    critic_comment="Contradiction/evidence checks pass: three distinct named limitations (reverse "
                                    "dependency, steady-state/distribution-only scope, unmodeled WTP structural "
                                    "damage) are each independently verbatim-confirmed in Zone D.",
                    supporting_evidence_ids=["B001-PDF-05-ZD-S17-4-C003", "B001-PDF-05-ZD-S17-4-C004"],
                    contradicting_evidence_ids=[], confidence=0.9, checks_failed=[]),
    },
}

# ---------------------------------------------------------------------------
# Agent A -- Pass 3 (revision of only the records Agent B marked 'revise')
# ---------------------------------------------------------------------------
AGENT_A_PASS3_REVISIONS = {
    "B001-PDF-01": {
        "D10": dict(primary_label="Validation_Generalizability_Limitation",
                     secondary_labels=["Missing_Factor_Limitation", "Future_Work_Direction"],
                     mechanism_judgment="Revised per Agent B: authors acknowledge neglected theoretical-to-practical "
                                         "details (validation/generalizability gap) AND explicitly flag extreme-"
                                         "weather resilience as a currently-unmodeled factor slated for future work.",
                     confidence=0.85),
    },
    "B001-PDF-05": {
        "D05": dict(primary_label="Not_Addressed", secondary_labels=[],
                     mechanism_judgment="Revised per Agent B: the paper's steady-state QMC damage-sampling framing "
                                         "does not engage with the water-thermal-hydraulic-vs-power timescale "
                                         "construct at all; Not_Addressed is the accurate fallback rather than "
                                         "forcing a Single_Timescale_Only reading of an unrelated analytical frame.",
                     confidence=0.8),
    },
}

# ---------------------------------------------------------------------------
# Agent B -- Pass 4 (final review of the Pass-3 revisions only)
# ---------------------------------------------------------------------------
AGENT_B_PASS4 = {
    "B001-PDF-01": {"D10": dict(decision="accept", confidence=0.85,
                                 critic_comment="Revision correctly adds Missing_Factor_Limitation; now fully "
                                                "supported by the verbatim quote. Final.")},
    "B001-PDF-05": {"D05": dict(decision="accept", confidence=0.8,
                                 critic_comment="Revision to Not_Addressed is well-justified and more accurate. Final.")},
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
                                 for eid in r["evidence_ids"]})
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

    # Merge into verified_10d_record per document (use the already-enriched
    # pass1 records -- with section_id/page_numbers/agent_a_model_call_id --
    # written just above, not the raw AGENT_A_PASS1 source tuples).
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

    with open(out_log / "model_call_manifest.jsonl", "w", encoding="utf-8") as f:
        for e in manifest_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"Wrote Agent A pass1/pass3, Agent B pass2/pass4, verified records for "
          f"{len(AGENT_A_PASS1)} documents, {len(manifest_entries)} manifest entries.")


if __name__ == "__main__":
    sys.exit(main())
