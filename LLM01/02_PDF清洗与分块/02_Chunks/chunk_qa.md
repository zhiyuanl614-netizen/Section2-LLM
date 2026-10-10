# Fine-grained evidence block QA

- Chunker version: `0.1.0`
- Config: target `180` words; maximum `240` words; overlap `0`.
- Boundary method: sentence-grouped within each section; unusually long sentences are split at clause punctuation, then at a word boundary if required.
- Offset basis: `char_start`/`char_end` are zero-based, end-exclusive Unicode-code-point indices into the exact Step 1 zone string, not raw PDF bytes or glyph positions. `source_excerpt` preserves the raw zone substring including inserted page tags for exact offset checking.
- `text` excludes inserted `[Page n]` tags and collapses layout whitespace; section/page metadata are preserved separately. No symbols were guessed or repaired.

## Per-document counts

| Doc ID | Evidence blocks | Zone A | Zone B | Zone C | Zone D | Unmapped glyph markers in blocks |
|---|---:|---:|---:|---:|---:|---:|
| B001-PDF-01 | 28 | 4 | 15 | 7 | 2 | 0 |
| B001-PDF-02 | 38 | 6 | 20 | 10 | 2 | 88 |
| B001-PDF-03 | 69 | 3 | 38 | 18 | 10 | 13 |
| B001-PDF-04 | 65 | 3 | 8 | 48 | 6 | 174 |
| B001-PDF-05 | 39 | 2 | 7 | 24 | 6 | 0 |

## QA checks

- Unique evidence IDs: `True`
- Offsets resolve to stored source excerpts: `True`
- Offsets are in bounds and non-overlapping within each source section: `True`
- Normalized source excerpt matches evidence `text`: `True`
- Page bounds/ranges and source PDF, Step 1 input, and Zone hashes are valid: `True`
- Evidence/retrieval-text hashes and section-heading matches are valid: `True`
- Stored word and character counts match the evidence text: `True`
- `retrieval_text` prepends the section heading to evidence `text`; source offsets address only the evidence substring, not the added heading.
- The 240-word cap applies to evidence `text`; `retrieval_text` additionally includes the section heading.
- No empty chunks: `True`
- All chunks are within the configured maximum: `True`
- Short chunks (<40 words): `3`; these are retained source units, not padded with guessed text.
- Heading/body audit notes: `13` total; empty parent/heading-only sections are logged as skipped, not fabricated.
- `text_sha256` and `retrieval_text_sha256` are recorded for each corresponding text field.

## Limitations and manual review

1. Step 1 did not retain paragraph bounding boxes or raw-PDF character offsets. These blocks are traceable to exact Step 1 zone strings, section headings, and extracted page tags/ranges; they are not raw-PDF character offsets.
2. PDF line breaks were reflowed to spaces. OCR/text extraction errors already present in the Zone input remain unchanged. `⟦PDF_GLYPH_U+XXXX⟧` markers are preserved and are not recovered symbols.
3. Chunk sizes are word-based because no target embedding tokenizer has been selected. Treat this as a versioned preprocessing default; tune it during retrieval pilot before indexing.
4. Zone A metadata labels are not evidence blocks; the abstract and retained contribution/intro text are included. Empty headings are omitted.

## Short-block review (<40 words)

| Evidence ID | Zone | Section | Pages | Words | Text sample |
|---|---|---|---|---:|---|
| B001-PDF-01-ZB-S10-3-2-C001 | Zone_B | 3.2. Analysis of the energy management method | 6 | 17 | According to the above simulation parameters, the MG integrating WSSs is tested. The results are as follows: |
| B001-PDF-03-ZB-S10-3-2-2-C001 | Zone_B | 3.2.2. Resourcefulness | 10 | 26 | Res (t): Rφ,ζ1 Res (t) = SPφ,ζ1(t) −SPφ,ζ1 ⟦PDF_GLYPH_U+0010⟧ 0 (t) = f Res(t): 0 (t) = F ⟦PDF_GLYPH_U+0010⟧ X Rζ1 Res(t |
| B001-PDF-05-ZB-S05-2-2-1-C002 | Zone_B | 2.2.1. Seismic fragility for pipelines of the WDS | 4 | 21 | A, B, and C are parameters for the standard repair rate function, with specific values referenced in Isoyama et al [30]. |

## Audit notes

| Doc ID | Zone | Issue | Heading / detail |
|---|---|---|---|
| B001-PDF-01 | Zone_C | empty_section_body_skipped | 3. Experimental results and discussion |
| B001-PDF-03 | Zone_B | empty_section_body_skipped | 2. Infrastructure Network Formalization |
| B001-PDF-03 | Zone_B | empty_section_body_skipped | 3. Infrastructure System Resilience Model |
| B001-PDF-03 | Zone_B | empty_section_body_skipped | 3.2. Three Features of Infrastructure System Resilience |
| B001-PDF-03 | Zone_B | empty_section_body_skipped | 4.2. First Repair Last Failures Strategy |
| B001-PDF-03 | Zone_D | empty_section_body_skipped | 5. Case Study |
| B001-PDF-03 | Zone_D | empty_section_body_skipped | 5.3. Test Case Disturbance—Flood Scenarios |
| B001-PDF-03 | Zone_D | empty_section_body_skipped | 6. Discussion |
| B001-PDF-03 | Zone_D | empty_section_body_skipped | 6.1. Hidden Impacts |
| B001-PDF-04 | Zone_C | empty_section_body_skipped | VI. IOR COMPUTATIONS |
| B001-PDF-04 | Zone_C | empty_section_body_skipped | VII. COMBINED CALCULATIONS |
| B001-PDF-04 | Zone_D | empty_section_body_skipped | VIII. APPLICATION EXAMPLE |
| B001-PDF-05 | Zone_C | empty_section_body_skipped | 2.3. Seismic performance analysis of individual system |

## formula_layout_risk - full systematic scan (not a sample)

Heuristic, signal-based flag computed for every evidence block (all zones), not just a manual sample. It marks candidates where PDF text extraction likely scrambled inline math/equation layout (subscripts, stacked symbols, multi-column formula runs). A flagged block is NOT auto-corrected; it is a routing signal to prioritize Step 5 gold-standard / agent-assisted review. Signals used: unmapped glyph markers, Greek letters/math unicode symbols, subscript-like tokens (e.g. Qu,t), equation numbering patterns (e.g. (12)), spaced math operators, and abnormally low English-stopword density for the block's length. Score threshold for formula_layout_risk=true is >= 2.0.

- Total evidence blocks scanned: `239`
- Flagged formula_layout_risk=true: `87`

| Evidence ID | Zone | Score | Signals | Text sample |
|---|---|---:|---|---|
| B001-PDF-02-ZB-S08-B-C004 | Zone_B | 12.0 | unmapped_glyph_marker(x17), greek_or_math_symbol(x61), subscript_like_token(x35), trailing_equation_number, math_operator_token(x12), low_stopword_ratio(0.05) | V ⟦PDF_GLYPH_U+0002⟧ M ⟦PDF_GLYPH_U+0002⟧ uγ ν,m qν Qu,t = u,t ∀t, ∀u, (25) ν=1 m=1 V ⟦PDF_GLYPH_U+0 |
| B001-PDF-02-ZB-S10-A-C002 | Zone_B | 11.5 | unmapped_glyph_marker(x5), greek_or_math_symbol(x13), subscript_like_token(x25), inline_equation_number(x6), math_operator_token(x7), low_stopword_ratio(0.10) | While the utilized energy ﬂexibility at each time is capped by the avail-able capacity at that time, |
| B001-PDF-02-ZB-S07-A-C002 | Zone_B | 11.0 | unmapped_glyph_marker(x4), greek_or_math_symbol(x46), subscript_like_token(x22), trailing_equation_number, math_operator_token(x7) | Any given point qk s ≤Qs,t ≤qk+1 s can be uniquely repre-sented by (17), as a linear combination of  |
| B001-PDF-02-ZB-S11-B-C001 | Zone_B | 11.0 | unmapped_glyph_marker(x9), greek_or_math_symbol(x14), subscript_like_token(x20), trailing_equation_number, math_operator_token(x7) | As shown in Fig. 1, the power system operator co-optimizes the ﬁnal decisions on WDS energy consumpt |
| B001-PDF-02-ZB-S08-B-C001 | Zone_B | 10.0 | unmapped_glyph_marker(x17), greek_or_math_symbol(x7), subscript_like_token(x32), inline_equation_number(x2), math_operator_token(x8) | Let function ⟦PDF_GLYPH_U+0006⟧ hu,t(Qu,t, ⟦PDF_GLYPH_U+0007⟧ u,t) = Hn+1,t −Hn,t shows the time-dep |
| B001-PDF-04-ZC-S41-G-C001 | Zone_C | 9.5 | unmapped_glyph_marker(x14), greek_or_math_symbol(x7), subscript_like_token(x2), inline_equation_number(x2), math_operator_token(x7), low_stopword_ratio(0.09) | Both the load supplied operational resilience values (overall and WDS pumps) are weighted at each no |
| B001-PDF-04-ZC-S42-H-C001 | Zone_C | 9.5 | unmapped_glyph_marker(x3), subscript_like_token(x6), trailing_equation_number, math_operator_token(x9), low_stopword_ratio(0.07) | The overall EPS IOR, REPS,TOT(t), is then calculated at each thermal limit, cooling water, demand su |
| B001-PDF-04-ZC-S35-A-C001 | Zone_C | 9.4 | unmapped_glyph_marker(x13), greek_or_math_symbol(x2), subscript_like_token(x6), trailing_equation_number, math_operator_token(x2), low_stopword_ratio(0.09) | The pressure IOR considering infrastructural robustness met-rics for connectivity and betweenness at |
| B001-PDF-04-ZC-S06-A-C002 | Zone_C | 9.1 | unmapped_glyph_marker(x4), greek_or_math_symbol(x4), subscript_like_token(x14), inline_equation_number(x2), math_operator_token(x8) | The pressure function is allocated a value between (0 and 1) based on its deviation from the safe li |
| B001-PDF-04-ZC-S45-B-C002 | Zone_C | 9.0 | unmapped_glyph_marker(x9), greek_or_math_symbol(x8), inline_equation_number(x7), math_operator_token(x13), low_stopword_ratio(0.10) | The performance loss is deﬁned as the total reduction in IOR value during the disruption phase MRAPI |
| B001-PDF-04-ZC-S06-A-C001 | Zone_C | 8.55 | unmapped_glyph_marker(x4), greek_or_math_symbol(x4), subscript_like_token(x13), inline_equation_number(x1), math_operator_token(x4) | Pressure bounds are an important performance assessment criterion for WDS operations. During emergen |
| B001-PDF-04-ZC-S37-C-C001 | Zone_C | 8.55 | unmapped_glyph_marker(x4), greek_or_math_symbol(x2), subscript_like_token(x8), inline_equation_number(x3), math_operator_token(x7) | Demand priority and demand adjustment metrics are consid-ered for computation of the demand satisfac |
| B001-PDF-02-ZB-S05-A-C002 | Zone_B | 8.5 | unmapped_glyph_marker(x4), greek_or_math_symbol(x19), trailing_equation_number, math_operator_token(x9) | 1) Water Conservation Constraint: The WDS delivers the water from reservoirs to the consumers throug |
| B001-PDF-04-ZC-S40-F-C001 | Zone_C | 8.25 | unmapped_glyph_marker(x20), greek_or_math_symbol(x4), subscript_like_token(x3), inline_equation_number(x1), math_operator_token(x3), low_stopword_ratio(0.07) | The IOR value for transmission line thermal limit resilience is calculated by weighting the operatio |
| B001-PDF-02-ZB-S08-B-C003 | Zone_B | 8.1 | unmapped_glyph_marker(x5), greek_or_math_symbol(x4), subscript_like_token(x14), inline_equation_number(x5) | The bivariate nonlinear functions ⟦PDF_GLYPH_U+0006⟧ hu,t(Qu,t, ⟦PDF_GLYPH_U+0007⟧ u,t) and PW u,t(Q |
| B001-PDF-02-ZB-S05-A-C004 | Zone_B | 8.0 | unmapped_glyph_marker(x18), greek_or_math_symbol(x27), inline_equation_number(x14), math_operator_token(x8) | The volumetric ﬂow rate decision variable of arcs, Qt, is bounded in (12), where the bound Q depends |
| B001-PDF-02-ZB-S08-B-C002 | Zone_B | 8.0 | unmapped_glyph_marker(x1), greek_or_math_symbol(x44), subscript_like_token(x11), inline_equation_number(x2), math_operator_token(x6) | The segments on the axes partition the bivariate function domain into several rectangles. Consider t |
| B001-PDF-04-ZC-S39-E-C001 | Zone_C | 7.75 | unmapped_glyph_marker(x9), greek_or_math_symbol(x5), inline_equation_number(x1), math_operator_token(x6), low_stopword_ratio(0.12) | Resilience for bus voltages in the IOR context is calculated by weighting the operation bus voltage  |
| B001-PDF-02-ZB-S05-A-C001 | Zone_B | 7.7 | unmapped_glyph_marker(x5), greek_or_math_symbol(x6), subscript_like_token(x2), inline_equation_number(x7), math_operator_token(x1) | The proposed WDS operation model is formulated here as a nonlinear optimization problem, where the o |
| B001-PDF-04-ZC-S18-C-C001 | Zone_C | 7.5 | unmapped_glyph_marker(x8), greek_or_math_symbol(x1), subscript_like_token(x5), inline_equation_number(x5), math_operator_token(x2) | Resilience for the upper and lower pressure bound function (Rn,tim P ) deﬁned in (3) is formulated u |
| B001-PDF-04-ZC-S22-G-C001 | Zone_C | 7.35 | unmapped_glyph_marker(x5), greek_or_math_symbol(x4), subscript_like_token(x1), inline_equation_number(x3), math_operator_token(x5) | The measure of performance for transmission line thermal limits is formulated using (11) and the the |
| B001-PDF-04-ZC-S24-I-C001 | Zone_C | 7.35 | unmapped_glyph_marker(x5), greek_or_math_symbol(x4), subscript_like_token(x1), inline_equation_number(x3), math_operator_token(x5) | The resilience measure of performance related to the supplied demand at time t is then formulated us |
| B001-PDF-04-ZC-S20-E-C001 | Zone_C | 7.25 | unmapped_glyph_marker(x8), greek_or_math_symbol(x1), subscript_like_token(x5), inline_equation_number(x3), math_operator_token(x2) | Resilience for demand satisfaction function (Rz,t Dem) deﬁned in (5) is formulated using (11). The r |
| B001-PDF-04-ZC-S44-A-C001 | Zone_C | 7.25 | unmapped_glyph_marker(x7), subscript_like_token(x6), inline_equation_number(x1), math_operator_token(x15) | For the two interdependent infrastructure systems, the cal-culation of the IOR terms compose what ar |
| B001-PDF-04-ZC-S10-E-C001 | Zone_C | 7.2 | greek_or_math_symbol(x8), subscript_like_token(x4), trailing_equation_number, math_operator_token(x4) | Power system bus voltage magnitudes are maintained within a small range of values during normal syst |
| B001-PDF-03-ZB-S10-3-2-2-C001 | Zone_B | 7.0 | unmapped_glyph_marker(x2), greek_or_math_symbol(x11), math_operator_token(x6), low_stopword_ratio(0.00) | Res (t): Rφ,ζ1 Res (t) = SPφ,ζ1(t) −SPφ,ζ1 ⟦PDF_GLYPH_U+0010⟧ 0 (t) = f Res(t): 0 (t) = F ⟦PDF_GLYPH |
| B001-PDF-03-ZB-S11-3-2-3-C001 | Zone_B | 7.0 | unmapped_glyph_marker(x2), greek_or_math_symbol(x40), inline_equation_number(x4), math_operator_token(x10) | Rob (tφ 1R): 1R) + eφ o (tφ 1R) Nφ + Eφ , (8) o (t) generates the maximum loss of a system φ o (t1R) |
| B001-PDF-02-ZB-S07-A-C001 | Zone_B | 6.85 | unmapped_glyph_marker(x1), greek_or_math_symbol(x4), subscript_like_token(x18), inline_equation_number(x1), math_operator_token(x5) | Let Ls,t(Qs,t) = Hn,t −Hn+1,t shows the time-dependent pressure head loss in pipe s connecting two n |
| B001-PDF-04-ZC-S21-F-C001 | Zone_C | 6.85 | unmapped_glyph_marker(x5), greek_or_math_symbol(x4), inline_equation_number(x3), math_operator_token(x5) | The resilience measure of performance for bus voltages is formulated using (11) and the bus voltage  |
| B001-PDF-04-ZC-S17-B-C001 | Zone_C | 6.75 | unmapped_glyph_marker(x3), subscript_like_token(x4), inline_equation_number(x1), math_operator_token(x9) | The overall system resilience at time t is then calculated as a normalized weighted sum of the volta |
| B001-PDF-04-ZC-S23-H-C001 | Zone_C | 6.65 | unmapped_glyph_marker(x5), greek_or_math_symbol(x3), subscript_like_token(x1), inline_equation_number(x3), math_operator_token(x4) | The measure of performance for the thermoelectric genera-tion’s cooling water supply is then formula |
| B001-PDF-04-ZC-S25-J-C001 | Zone_C | 6.65 | unmapped_glyph_marker(x5), greek_or_math_symbol(x3), subscript_like_token(x1), inline_equation_number(x3), math_operator_token(x4) | The resilience measure of performance related to the supplied demand of pump loads in the WDS at tim |
| B001-PDF-04-ZC-S36-B-C001 | Zone_C | 6.15 | unmapped_glyph_marker(x12), greek_or_math_symbol(x5), inline_equation_number(x1), math_operator_token(x3) | The functionality factor for pumps (αpump) is considered for computing the IOR for power consumption |
| B001-PDF-03-ZB-S04-2-2-C003 | Zone_B | 6.0 | unmapped_glyph_marker(x1), greek_or_math_symbol(x45), subscript_like_token(x1), inline_equation_number(x2), math_operator_token(x6) | This pattern is represented as: IDnn = eφ1φ2 (nφ2 i ,nφ2 IDne = n on the state of the path pφ2 IDNP  |
| B001-PDF-03-ZC-S12-3-3-C003 | Zone_C | 6.0 | greek_or_math_symbol(x76), inline_equation_number(x4), math_operator_token(x17), low_stopword_ratio(0.06) | Using the deﬁnition of the three features of resilience, the proactive absorptive capacity of indivi |
| B001-PDF-05-ZC-S09-2-3-2-C002 | Zone_C | 6.0 | greek_or_math_symbol(x10), subscript_like_token(x2), inline_equation_number(x8), math_operator_token(x7) | Eqs. (5) and (6) present the calculation principles for active power and reactive power; Eq. (7) des |
| B001-PDF-04-ZC-S32-F-C001 | Zone_C | 5.55 | unmapped_glyph_marker(x12), subscript_like_token(x4), inline_equation_number(x1), math_operator_token(x1) | Similar to the connectivity measure above but for a trans-mission line (edge) rather than a bus (nod |
| B001-PDF-03-ZC-S23-5-4-C003 | Zone_C | 5.5 | unmapped_glyph_marker(x4), greek_or_math_symbol(x17) | In this scenario, infrastructure elements located in the four bottom and four right cells, with coor |
| B001-PDF-04-ZC-S19-D-C001 | Zone_C | 5.3 | unmapped_glyph_marker(x8), greek_or_math_symbol(x1), inline_equation_number(x4), math_operator_token(x3) | Resilience for power availability function (Rpump,t Pow ) de-ﬁned in (4) is formulated using (11). T |
| B001-PDF-03-ZC-S12-3-3-C001 | Zone_C | 5.1 | unmapped_glyph_marker(x1), greek_or_math_symbol(x14), inline_equation_number(x5), math_operator_token(x2) | PA (T): Rap : 1RE −tφ 1O, (12) 2O −tφ 1O, (13) ⟦PDF_GLYPH_U+001B⟧ Rφ,ζ1 . (14) Rap Sustainability 20 |
| B001-PDF-05-ZC-S10-2-4-C003 | Zone_C | 5.0 | greek_or_math_symbol(x27), inline_equation_number(x4), math_operator_token(x8) | The left side of the equation represents the active electrical power consumed by the water pump, mea |
| B001-PDF-03-ZB-S04-2-2-C004 | Zone_B | 4.8 | unmapped_glyph_marker(x1), greek_or_math_symbol(x21), subscript_like_token(x1), inline_equation_number(x2), math_operator_token(x1) | IDEP is edge another im = i i i,j i , which is a set of nodes l or edge eφ2 lk × cφ1 i (4) i is the  |
| B001-PDF-04-ZC-S13-H-C003 | Zone_C | 4.75 | greek_or_math_symbol(x5), subscript_like_token(x2), inline_equation_number(x1), math_operator_token(x8) | The new LMF for the single-family or multifamily components of the load is given by the product of t |
| B001-PDF-04-ZC-S16-A-C001 | Zone_C | 4.75 | unmapped_glyph_marker(x3), inline_equation_number(x1), math_operator_token(x5) | The overall resilience for time t is a normalized (real value between 0 and 1) weighted sum of the p |
| B001-PDF-04-ZC-S31-E-C001 | Zone_C | 4.75 | unmapped_glyph_marker(x3), greek_or_math_symbol(x1), subscript_like_token(x1), inline_equation_number(x1), math_operator_token(x2) | The connectivity metric for a bus is determined by the impedance of the lines connected to it. This  |
| B001-PDF-05-ZB-S05-2-2-1-C001 | Zone_B | 4.5 | greek_or_math_symbol(x9), inline_equation_number(x2), math_operator_token(x5) | The failure probability of WDS components can be evaluated by seismic fragility models. According to |
| B001-PDF-03-ZB-S11-3-2-3-C003 | Zone_B | 4.4 | unmapped_glyph_marker(x1), greek_or_math_symbol(x10), math_operator_token(x3) | Rapidity refers to the capacity to meet priorities and achieve goals in a timely manner in order to  |
| B001-PDF-02-ZB-S05-A-C003 | Zone_B | 4.2 | unmapped_glyph_marker(x2), greek_or_math_symbol(x3), inline_equation_number(x7) | Constraint (5) sets the water volume stored in tanks at the start of scheduling horizon, where Vinit |
| B001-PDF-03-ZB-S13-4-C001 | Zone_B | 4.2 | greek_or_math_symbol(x36), inline_equation_number(x2), math_operator_token(x4) | R T R T ζ Rζ ζ SPζ R R Res(t)dt 0(t)dt t1O t1O 1×T + 1×T , (21) 1RE R T R T φ Rφ,ζ φ SPφ,ζ R R R R R |
| B001-PDF-03-ZC-S12-3-3-C005 | Zone_C | 4.2 | greek_or_math_symbol(x48), inline_equation_number(x2), math_operator_token(x4) | The reactive restorative capacity of individual infrastructure network subject to a disturbance ζ1 ( |
| B001-PDF-04-ZC-S28-B-C001 | Zone_C | 4.15 | unmapped_glyph_marker(x1), greek_or_math_symbol(x4), subscript_like_token(x2), inline_equation_number(x1), math_operator_token(x1) | The betweenness metric gives the robustness associated with the functionality of the links connected |
| B001-PDF-03-ZB-S11-3-2-3-C002 | Zone_B | 4.0 | greek_or_math_symbol(x32), math_operator_token(x8) | Resourcefulness is the capacity to develop and implement mitigation and response strategies to a spe |
| B001-PDF-04-ZC-S38-D-C001 | Zone_C | 4.0 | subscript_like_token(x2), trailing_equation_number, math_operator_token(x5) | The total system IOR is computed as a weighted sum aver-age of the infrastructural–operational resil |
| B001-PDF-03-ZB-S05-2-3-C002 | Zone_B | 3.75 | greek_or_math_symbol(x5), inline_equation_number(x1), math_operator_token(x6) | Then the adaptive capacity of an infrastructure type, shown in Figure 3 can be represented as: i = ( |
| B001-PDF-02-ZB-S04-II-C001 | Zone_B | 3.7 | greek_or_math_symbol(x2), subscript_like_token(x4), math_operator_token(x3) | In this section, we present the proposed model to optimize the operation of W-DSOs. The proposed WDS |
| B001-PDF-04-ZC-S33-G-C001 | Zone_C | 3.6 | unmapped_glyph_marker(x1), greek_or_math_symbol(x1), subscript_like_token(x1), inline_equation_number(x2), math_operator_token(x4) | The efﬁciency metric uses the electrical distance between generators and a load to determine how imp |
| B001-PDF-02-ZB-S10-A-C001 | Zone_B | 3.5 | subscript_like_token(x6), inline_equation_number(x8) | The proposed WDS energy ﬂexibility model is presented in (33)-(37). In (33), PW d,t is the total hou |
| B001-PDF-03-ZC-S26-5-4-3-C003 | Zone_C | 3.5 | greek_or_math_symbol(x7), subscript_like_token(x2) | In spite that the duration of disturbance event is assumed to be one day, the impacts of disturbance |
| B001-PDF-04-ZC-S07-B-C001 | Zone_C | 3.5 | greek_or_math_symbol(x1), subscript_like_token(x2), trailing_equation_number, math_operator_token(x2) | Animportant aspect of schedulingpumpoperations is toavoid electric power availability upper bound vi |
| B001-PDF-05-ZC-S10-2-4-C004 | Zone_C | 3.5 | greek_or_math_symbol(x6), inline_equation_number(x2), math_operator_token(x2) | Qe(t) denotes the normal water supply flow of the i th dependent water treatment plant (L/s); H*(t)  |
| B001-PDF-02-ZB-S09-IV-C001 | Zone_B | 3.4 | greek_or_math_symbol(x1), subscript_like_token(x8), inline_equation_number(x2) | The WDS operation model proposed in Section II would allow the W-DSOs to minimize the operation cost |
| B001-PDF-04-ZC-S11-F-C001 | Zone_C | 3.35 | unmapped_glyph_marker(x1), greek_or_math_symbol(x2), subscript_like_token(x2), inline_equation_number(x1), math_operator_token(x1) | Similar to the voltage magnitudes in the power system, the transmission lines are designed to be ope |
| B001-PDF-03-ZC-S12-3-3-C004 | Zone_C | 3.3 | greek_or_math_symbol(x30), inline_equation_number(x2), math_operator_token(x1) | t1O ≤T ≤tφ 1×T 1RE. (19) R T φ,ζ1 Res (t)dt t1O R R T ζ1 Res(t)dt φ,ζ1 0 (t)dt R t1O R φ 1×T + , t1O |
| B001-PDF-03-ZB-S04-2-2-C005 | Zone_B | 3.1 | greek_or_math_symbol(x16), math_operator_token(x2) | This pattern is represented as im or IDEP = eφ1 l is the state of node l of φ1 network, and pφ2 of p |
| B001-PDF-03-ZB-S09-3-2-1-C003 | Zone_B | 3.1 | greek_or_math_symbol(x16), math_operator_token(x2) | For individual infrastructure, the robustness 1R) = nφ o (tφ Rφ,ζ1 Rob (tφ where tφ 1R is the time w |
| B001-PDF-04-ZC-S12-G-C001 | Zone_C | 3.05 | unmapped_glyph_marker(x2), subscript_like_token(x1), inline_equation_number(x1), math_operator_token(x1) | Index Function Thermoelectric generation requires water for the cooling cy-cle in the process of con |
| B001-PDF-05-ZB-S06-2-2-2-C001 | Zone_B | 3.05 | greek_or_math_symbol(x7), inline_equation_number(x1), math_operator_token(x1) | The damage probability for components of the PS can be computed by seismic fragility models of power |
| B001-PDF-01-ZB-S07-2-3-C003 | Zone_B | 2.9 | greek_or_math_symbol(x1), inline_equation_number(x5), math_operator_token(x6) | Based on the above analysis, we use iterative methods to solve the sub-problems. The iterative facto |
| B001-PDF-03-ZC-S24-5-4-1-C002 | Zone_C | 2.7 | greek_or_math_symbol(x3), subscript_like_token(x2), inline_equation_number(x2) | For water supply network (see Figure 13b), the RS-OD and RS-HD result in the worst system performanc |
| B001-PDF-03-ZC-S23-5-4-C002 | Zone_C | 2.6 | unmapped_glyph_marker(x1), greek_or_math_symbol(x4) | Generally, ﬂoods strike geographically conﬁned areas. With the geographical location of the infrastr |
| B001-PDF-05-ZC-S15-3-4-C002 | Zone_C | 2.6 | greek_or_math_symbol(x5), math_operator_token(x2) | For the scenario with P(W\|E) =0.5, the seismic performance difference betweenα=0.3 and α=1.0 is with |
| B001-PDF-03-ZB-S05-2-3-C001 | Zone_B | 2.55 | greek_or_math_symbol(x5), inline_equation_number(x1), math_operator_token(x1) | ACφ ACφ i can be represented as: Sustainability 2019, 11, 6552 7 of 31 The consequences of infrastru |
| B001-PDF-01-ZB-S05-2-1-C003 | Zone_B | 2.5 | inline_equation_number(x12), math_operator_token(x5) | 3) Energy storage model The WT and reservoir can regulate the pipe flow by storing or Fig. 1. Struct |
| B001-PDF-01-ZB-S05-2-1-C004 | Zone_B | 2.5 | inline_equation_number(x16), math_operator_token(x10) | Linearized techniques are used to mathematically depict the power-output characteristic, as shown in |
| B001-PDF-01-ZB-S06-2-2-C003 | Zone_B | 2.5 | inline_equation_number(x13), math_operator_token(x10) | T J in in out out = = F min P p P p : ( · · ) d tj tj t t 1 1 (29) t j P u P s.t 0 ¯ tj in in GD (30 |
| B001-PDF-01-ZB-S06-2-2-C004 | Zone_B | 2.5 | inline_equation_number(x9), math_operator_token(x14) | The detailed model is presented as follows: + t M J j out 1 in j in out = F min P p P p : ( · · ) rd |
| B001-PDF-01-ZB-S07-2-3-C002 | Zone_B | 2.5 | inline_equation_number(x4), math_operator_token(x13) | These values are called X2* and passed to the second stage. In the second stage, with J = 30 of (40) |
| B001-PDF-03-ZB-S04-2-2-C006 | Zone_B | 2.4 | greek_or_math_symbol(x6) | The basic dependence patterns can cause cascading impacts throughout the multilayer network as time  |
| B001-PDF-01-ZB-S05-2-1-C002 | Zone_B | 2.3 | greek_or_math_symbol(x1), inline_equation_number(x8), math_operator_token(x3) | Note that the nodal correlation matrixes of the WSS in Fig. 2 can be presented as follows: Z I A t t |
| B001-PDF-03-ZB-S04-2-2-C001 | Zone_B | 2.25 | greek_or_math_symbol(x5), inline_equation_number(x1) | i is dependent on the state of nφ2 ij (1) Sustainability 2019, 11, 6552 5 of 31 consequently on infr |
| B001-PDF-03-ZB-S13-4-C002 | Zone_B | 2.1 | greek_or_math_symbol(x4), inline_equation_number(x2) | According to Equation (22), the infrastructure system resilience can be improved through the increas |
| B001-PDF-03-ZC-S24-5-4-1-C001 | Zone_C | 2.1 | greek_or_math_symbol(x4), subscript_like_token(x1) | Performance units of diﬀerent infrastructure systems are diﬀerent. System performance of single laye |
| B001-PDF-03-ZC-S24-5-4-1-C004 | Zone_C | 2.1 | greek_or_math_symbol(x4), subscript_like_token(x1) | The detailed analysis of results indicates that the rapidity should be considered for a more compreh |
| B001-PDF-04-ZC-S08-C-C001 | Zone_C | 2.05 | subscript_like_token(x3), inline_equation_number(x1), math_operator_token(x1) | The function for demand satisfaction is given by Dsat, z, t Dreq, z, t , which is an output from the |
| B001-PDF-05-ZC-S09-2-3-2-C003 | Zone_C | 2.05 | greek_or_math_symbol(x3), inline_equation_number(x1), math_operator_token(x2) | Under earthquake hazards, components of PSs typically experience direct damage, which further causes |
| B001-PDF-01-ZB-S07-2-3-C001 | Zone_B | 2.0 | inline_equation_number(x2), math_operator_token(x6) | The above dispatching model consists of linear objectives and constraints. Therefore, it can be conv |
| B001-PDF-03-ZB-S04-2-2-C002 | Zone_B | 2.0 | greek_or_math_symbol(x5) | The focus of the proposed resilience model is the direct impact of infrastructure malfunction, which |
