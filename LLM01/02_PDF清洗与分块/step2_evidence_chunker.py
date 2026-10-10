#!/usr/bin/env python3
"""Create traceable, sentence-grouped evidence blocks from Step 1 Zone slices.

Offsets are exact Unicode-code-point positions in the selected Step 1 zone string,
not byte offsets or raw PDF glyph offsets. The raw zone excerpt is retained to
make each normalized retrieval text auditable.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any
import unicodedata

ROOT = Path(__file__).resolve().parent
DEFAULT_INPUT = ROOT / "01_Zones" / "step1_sliced_pdf_corpus.json"
DEFAULT_SOURCE_MANIFEST = ROOT / "01_Zones" / "run_manifest.json"
DEFAULT_OUTPUT = ROOT / "02_Chunks"

ZONE_MAP = {
    "Zone_A_Meta_Abstract_Contribution": "Zone_A",
    "Zone_B_Coupling_And_Cascading_Model": "Zone_B",
    "Zone_C_Metrics_And_Simulation_Control": "Zone_C",
    "Zone_D_Case_Social_And_Limitations": "Zone_D",
}
ZONE_SHORT = {"Zone_A": "ZA", "Zone_B": "ZB", "Zone_C": "ZC", "Zone_D": "ZD"}
PAGE_TAG_RE = re.compile(r"\[Page\s+(\d+)\]\s*", re.IGNORECASE)
UNMAPPED_GLYPH_RE = re.compile(r"⟦PDF_GLYPH_U\+[0-9A-F]{4,6}⟧", re.IGNORECASE)
WORD_RE = re.compile(r"\b[\w]+(?:[’'\-][\w]+)*\b", re.UNICODE)
ZONE_A_HEADER_RE = re.compile(
    r"^\[(?P<title>.+?)\s+\(Pages\s+(?P<start>\d+)\s*-\s*(?P<end>\d+)\)\]\s*$",
    re.MULTILINE,
)
SECTION_HEADER_RE = re.compile(
    r"^###\s+(?P<title>.+?)\s+\(Pages\s+(?P<start>\d+)\s*-\s*(?P<end>\d+)\)\s*$",
    re.MULTILINE,
)

# --- formula_layout_risk heuristic -----------------------------------------
# PDF text extraction linearizes 2-D equation layout (stacked fractions,
# subscripts/superscripts, multi-column symbol runs) into a single text
# stream, which can silently scramble token order inside Zone B/C evidence
# blocks that contain inline math. This signal does not "fix" such blocks;
# it only flags them so they are prioritized in Step 5 gold-standard review
# instead of being silently trusted as ordinary prose.
_GREEK_MATH_RE = re.compile(
    "[\u0370-\u03ff\u2200-\u22ff\u2070-\u209f\u00b2\u00b3\u00b9\u2212\u00d7\u00f7\u2248\u2260\u2264\u2265\u00b1\u221e\u2202\u2207\u221a]"
)
# Requires a bare comma glued directly between short alphanumeric runs with no
# surrounding space (e.g. "Qu,t", "Hn+1,t", "SPf,z1") -- a strong, specific
# signature of inline math subscript notation. A plain ASCII hyphen is
# deliberately excluded here because it over-matches ordinary hyphenated
# English compounds ("two-stage", "real-time", "con-text") that have nothing
# to do with equations.
_SUBSCRIPT_TOKEN_RE = re.compile(r"\b[A-Za-z\u0370-\u03ff]{1,4}\d*(?:[+\-]\d+)?,[A-Za-z0-9]{1,4}\b")
_EQ_NUMBER_RE = re.compile(r"\(\s*\d{1,3}\s*\)\s*[\.,]?\s*$")
_INLINE_EQ_NUMBER_RE = re.compile(r"\(\s*\d{1,3}\s*\)")
_GLYPH_MARKER_RE = UNMAPPED_GLYPH_RE
_MATH_OPERATOR_SPACED_RE = re.compile(r"(?:(?<=\s)[=+\u2212](?=\s)|(?<=\s)[=+\u2212](?=[A-Za-z0-9(]))")
_STOPWORDS = {
    "the", "and", "of", "is", "are", "in", "to", "a", "that", "for", "with",
    "this", "as", "by", "on", "be", "was", "were", "it", "which", "an",
    "from", "at", "or", "can", "its",
}


def compute_formula_layout_risk(text: str) -> dict[str, Any]:
    """Score how likely a block's text contains PDF-mangled inline math/equations.

    Heuristic, signal-based, and conservative: it flags candidates for human/
    agent review in Step 5; it does not infer or repair the "correct" formula.
    """
    signals: list[str] = []
    score = 0.0

    words = WORD_RE.findall(text)
    n_words = max(1, len(words))

    glyph_hits = len(_GLYPH_MARKER_RE.findall(text))
    if glyph_hits:
        signals.append(f"unmapped_glyph_marker(x{glyph_hits})")
        score += min(3.0, 1.0 * glyph_hits)

    greek_math_hits = len(_GREEK_MATH_RE.findall(text))
    if greek_math_hits:
        signals.append(f"greek_or_math_symbol(x{greek_math_hits})")
        score += min(2.5, 0.4 * greek_math_hits)

    subscript_tokens = _SUBSCRIPT_TOKEN_RE.findall(text)
    if subscript_tokens:
        signals.append(f"subscript_like_token(x{len(subscript_tokens)})")
        score += min(2.5, 0.5 * len(subscript_tokens))

    # A short "(1)/(2)/(3)..." enumerated list (e.g. a contributions list) looks
    # identical to inline equation-number references, so this signal alone is
    # kept weak; it only matters combined with other math signals above.
    inline_eq_numbers = len(_INLINE_EQ_NUMBER_RE.findall(text))
    if _EQ_NUMBER_RE.search(text):
        signals.append("trailing_equation_number")
        score += 1.5
    elif inline_eq_numbers:
        signals.append(f"inline_equation_number(x{inline_eq_numbers})")
        score += min(1.0, 0.25 * inline_eq_numbers)

    operator_hits = len(_MATH_OPERATOR_SPACED_RE.findall(text))
    if operator_hits:
        signals.append(f"math_operator_token(x{operator_hits})")
        score += min(1.5, 0.3 * operator_hits)

    stopword_hits = sum(1 for w in words if w.lower() in _STOPWORDS)
    stopword_ratio = stopword_hits / n_words
    if n_words >= 8 and stopword_ratio < 0.12:
        signals.append(f"low_stopword_ratio({stopword_ratio:.2f})")
        score += 1.0

    risk = score >= 2.0
    return {
        "formula_layout_risk": risk,
        "formula_layout_risk_score": round(score, 2),
        "formula_layout_risk_signals": signals,
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def canonical_heading(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = re.sub(r"\s+", " ", text).strip()
    return text.rstrip(" .")


def word_spans(text: str) -> list[tuple[int, int]]:
    markers = [m.span() for m in UNMAPPED_GLYPH_RE.finditer(text or "")]
    spans = []
    for match in WORD_RE.finditer(text or ""):
        if any(match.start() < marker_end and marker_start < match.end() for marker_start, marker_end in markers):
            continue
        spans.append(match.span())
    return spans


def count_words(text: str) -> int:
    return len(word_spans(text))


def markdown_escape_cell(text: Any) -> str:
    return str(text).replace("|", r"\|").replace("\n", " ")


def parse_page_range(value: str) -> tuple[int | None, int | None]:
    match = re.fullmatch(r"P?(\d+)\s*-\s*P?(\d+)", str(value or "").strip(), re.IGNORECASE)
    if not match:
        return None, None
    return int(match.group(1)), int(match.group(2))


def page_list(start: int | None, end: int | None) -> list[int]:
    if start is None or end is None or end < start or end - start > 100:
        return []
    return list(range(start, end + 1))


def normalize_body_with_offsets(
    body: str,
    zone_body_start: int,
    fallback_pages: list[int],
) -> tuple[str, list[int], list[int], list[tuple[int, ...]], str]:
    """Remove injected [Page n] tags and collapse layout whitespace, retaining offsets."""
    page_tags = list(PAGE_TAG_RE.finditer(body))
    raw_chars: list[str] = []
    raw_starts: list[int] = []
    raw_ends: list[int] = []
    raw_pages: list[tuple[int, ...]] = []

    def add_segment(segment: str, local_start: int, pages: tuple[int, ...]) -> None:
        for index, char in enumerate(segment, start=local_start):
            raw_chars.append(char)
            raw_starts.append(zone_body_start + index)
            raw_ends.append(zone_body_start + index + 1)
            raw_pages.append(pages)

    cursor = 0
    active_page: int | None = None
    for tag in page_tags:
        if tag.start() > cursor:
            page_tuple = (active_page,) if active_page is not None else tuple(fallback_pages)
            add_segment(body[cursor:tag.start()], cursor, page_tuple)
        new_page = int(tag.group(1))
        marker_pages = {new_page}
        # Treat the removed page tag as a word boundary while retaining its exact raw span.
        raw_chars.append(" ")
        raw_starts.append(zone_body_start + tag.start())
        raw_ends.append(zone_body_start + tag.end())
        raw_pages.append(tuple(sorted(marker_pages)))
        active_page = new_page
        cursor = tag.end()
    if cursor < len(body):
        page_tuple = (active_page,) if active_page is not None else tuple(fallback_pages)
        add_segment(body[cursor:], cursor, page_tuple)

    output_chars: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    pages_for_char: list[tuple[int, ...]] = []
    i = 0
    while i < len(raw_chars):
        if raw_chars[i].isspace():
            j = i + 1
            seen_pages = set(raw_pages[i])
            while j < len(raw_chars) and raw_chars[j].isspace():
                seen_pages.update(raw_pages[j])
                j += 1
            if output_chars and output_chars[-1] != " ":
                output_chars.append(" ")
                starts.append(raw_starts[i])
                ends.append(raw_ends[j - 1])
                pages_for_char.append(tuple(sorted(seen_pages)))
            elif output_chars and output_chars[-1] == " ":
                ends[-1] = raw_ends[j - 1]
                pages_for_char[-1] = tuple(sorted(set(pages_for_char[-1]) | seen_pages))
            i = j
            continue
        output_chars.append(raw_chars[i])
        starts.append(raw_starts[i])
        ends.append(raw_ends[i])
        pages_for_char.append(raw_pages[i])
        i += 1

    left = 0
    right = len(output_chars)
    while left < right and output_chars[left].isspace():
        left += 1
    while right > left and output_chars[right - 1].isspace():
        right -= 1
    normalized = "".join(output_chars[left:right])
    return normalized, starts[left:right], ends[left:right], pages_for_char[left:right], (
        "page_markers" if page_tags else "section_range_only"
    )


def _is_abbreviation(text: str, punctuation_index: int) -> bool:
    if text[punctuation_index] != ".":
        return False
    prefix = text[max(0, punctuation_index - 30):punctuation_index + 1].lower()
    abbreviations = (
        "e.g.", "i.e.", "fig.", "eq.", "equ.", "ref.", "refs.", "no.", "vol.",
        "vs.", "approx.", "et al.", "dr.", "mr.", "mrs.", "prof.", "inc.",
        "dept.", "p.", "pp.", "cf.", "ca.", "sec.", "secs.", "u.s.", "w.r.t.",
    )
    if any(prefix.endswith(abbr) for abbr in abbreviations):
        return True
    before = text[:punctuation_index + 1]
    last = re.search(r"(?:^|\s)([A-Z])\.$", before)
    return bool(last)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Approximate sentence boundaries, protecting common scientific abbreviations."""
    if not text:
        return []
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    while i < len(text):
        if text[i] not in ".!?":
            i += 1
            continue
        punctuation_end = i + 1
        while punctuation_end < len(text) and text[punctuation_end] in '"”’)]}':
            punctuation_end += 1
        if punctuation_end >= len(text) or not text[punctuation_end].isspace():
            i = punctuation_end
            continue
        next_char = punctuation_end
        while next_char < len(text) and text[next_char].isspace():
            next_char += 1
        if next_char >= len(text):
            break
        if text[i] == "." and _is_abbreviation(text, i):
            i = punctuation_end
            continue
        if not (text[next_char].isupper() or text[next_char].isdigit() or text[next_char] in "⟦"):
            i = punctuation_end
            continue
        end = punctuation_end
        if text[start:end].strip():
            spans.append((start, end))
        start = next_char
        i = next_char
    if text[start:].strip():
        spans.append((start, len(text)))
    if not spans and text.strip():
        spans = [(0, len(text))]
    return spans


def split_oversized_span(text: str, start: int, end: int, max_words: int) -> list[tuple[int, int, str]]:
    """Split an unusually long sentence at clause punctuation, then word boundaries."""
    if len(word_spans(text[start:end])) <= max_words:
        return [(start, end, "sentence")]

    spans: list[tuple[int, int, str]] = []
    cursor = start
    while cursor < end:
        relative_words = word_spans(text[cursor:end])
        if len(relative_words) <= max_words:
            spans.append((cursor, end, "clause_or_sentence"))
            break
        hard_cut = cursor + relative_words[max_words - 1][1]
        lower_bound = cursor + relative_words[max(0, max_words // 2 - 1)][1]
        candidates = [m.end() for m in re.finditer(r"[,;:]\s+", text[lower_bound:hard_cut])]
        if candidates:
            cut = lower_bound + candidates[-1]
            reason = "clause_limit"
        else:
            cut = hard_cut
            reason = "word_limit"
        if cut <= cursor:
            cut = hard_cut
            reason = "word_limit"
        spans.append((cursor, cut, reason))
        cursor = cut
        while cursor < end and text[cursor].isspace():
            cursor += 1
    return spans


def build_chunks_for_unit(
    unit: dict[str, Any],
    zone_text: str,
    target_words: int,
    max_words: int,
) -> list[dict[str, Any]]:
    normalized, char_starts, char_ends, char_pages, page_precision = normalize_body_with_offsets(
        unit["body"], unit["body_start"], unit["fallback_pages"]
    )
    page_precision = unit.get("page_precision_override", page_precision)
    if not normalized:
        return []

    sentences = sentence_spans(normalized)
    atomic: list[tuple[int, int, str]] = []
    for start, end in sentences:
        atomic.extend(split_oversized_span(normalized, start, end, max_words))

    groups: list[tuple[int, int, str, int]] = []
    group_start: int | None = None
    group_end: int | None = None
    group_words = 0
    group_reason = "sentence_group"
    for start, end, reason in atomic:
        text_piece = normalized[start:end].strip()
        piece_words = count_words(text_piece)
        if not piece_words:
            continue
        # Start a new evidence unit at the soft target when possible; never exceed
        # max_words unless the splitter cannot form a safe non-empty range.
        if group_start is not None and (
            group_words >= target_words or group_words + piece_words > max_words
        ):
            groups.append((group_start, group_end or group_start, group_reason, group_words))
            group_start, group_end, group_words = None, None, 0
            group_reason = "sentence_group"
        if group_start is None:
            group_start = start
            group_end = end
            group_words = piece_words
            group_reason = reason if reason != "sentence" else "sentence_group"
        else:
            group_end = end
            group_words += piece_words
            if reason != "sentence":
                group_reason = reason
        # Emit any hard-split atom that itself reaches the hard limit.
        if group_words >= max_words and group_start is not None:
            groups.append((group_start, group_end or group_start, group_reason, group_words))
            group_start, group_end, group_words = None, None, 0
            group_reason = "sentence_group"
    if group_start is not None:
        groups.append((group_start, group_end or group_start, group_reason, group_words))

    # Avoid tiny trailing fragments when they can be joined without exceeding the hard cap.
    while len(groups) > 1 and groups[-1][3] < 40 and groups[-2][3] + groups[-1][3] <= max_words:
        previous = groups[-2]
        trailing = groups[-1]
        groups[-2] = (previous[0], trailing[1], "merged_short_tail", previous[3] + trailing[3])
        groups.pop()

    records: list[dict[str, Any]] = []
    for chunk_index, (start, end, split_reason, _group_word_count) in enumerate(groups, start=1):
        text = normalized[start:end].strip()
        # Adjust normalized start/end to exclude any spaces trimmed from the span.
        leading = len(normalized[start:end]) - len(normalized[start:end].lstrip())
        trailing = len(normalized[start:end]) - len(normalized[start:end].rstrip())
        char_i = start + leading
        char_j = end - trailing
        if char_j <= char_i:
            continue
        zone_char_start = char_starts[char_i]
        zone_char_end = char_ends[char_j - 1]
        source_excerpt = zone_text[zone_char_start:zone_char_end]
        page_set = set()
        for page_tuple in char_pages[char_i:char_j]:
            page_set.update(page_tuple)
        pages = sorted(p for p in page_set if p is not None)
        if not pages:
            pages = list(unit["fallback_pages"])
        risk_info = compute_formula_layout_risk(text)
        records.append({
            "chunk_index": chunk_index,
            "text": text,
            "source_excerpt": source_excerpt,
            "char_start": zone_char_start,
            "char_end": zone_char_end,
            "offset_basis": "zero-based, end-exclusive Unicode code-point offsets into the exact Step 1 targeted_zones[zone_text_key] string; not raw-PDF offsets",
            "page_numbers": pages,
            "page_precision": page_precision,
            "word_count": count_words(text),
            "char_count": len(text),
            "text_sha256": sha256_text(text),
            "split_reason": split_reason,
            "sentence_count_estimate": max(1, len(sentence_spans(text))),
            "contains_unmapped_glyph_marker": "⟦PDF_GLYPH_U+" in text,
            "unmapped_glyph_marker_count": len(UNMAPPED_GLYPH_RE.findall(text)),
            "formula_layout_risk": risk_info["formula_layout_risk"],
            "formula_layout_risk_score": risk_info["formula_layout_risk_score"],
            "formula_layout_risk_signals": risk_info["formula_layout_risk_signals"],
        })
    return records


def find_section_record(
    title: str,
    page_start: int,
    page_end: int,
    zone: str,
    section_candidates: dict[tuple[str, int | None, int | None, str], list[tuple[int, dict[str, Any]]]],
    used_indices: set[int],
) -> tuple[int | None, dict[str, Any] | None, str]:
    key = (canonical_heading(title), page_start, page_end, zone)
    for index, section in section_candidates.get(key, []):
        if index not in used_indices:
            used_indices.add(index)
            return index, section, "exact_heading_zone_pages"
    # Unique-title fallback only: no fuzzy guess when duplicates remain.
    candidates = []
    for candidate_key, records in section_candidates.items():
        if candidate_key[0] == canonical_heading(title) and candidate_key[3] == zone:
            candidates.extend((i, sec) for i, sec in records if i not in used_indices)
    if len(candidates) == 1:
        index, section = candidates[0]
        used_indices.add(index)
        return index, section, "unique_heading_zone_page_mismatch"
    return None, None, "unmatched_heading"


def parse_units(doc: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates: dict[tuple[str, int | None, int | None, str], list[tuple[int, dict[str, Any]]]] = defaultdict(list)
    for section_index, section in enumerate(doc.get("section_tree", []), start=1):
        start_page, end_page = parse_page_range(section.get("pages", ""))
        assigned = section.get("assigned_zone", "")
        zone = next((z for z in ("Zone_A", "Zone_B", "Zone_C", "Zone_D") if assigned.startswith(z.replace("_", " "))), None)
        # Step 1 labels use "Zone A", not "Zone_A".
        if zone is None:
            zone = next((f"Zone_{letter}" for letter in "ABCD" if assigned.startswith(f"Zone {letter}")), None)
        if zone:
            candidates[(canonical_heading(section.get("full_heading", "")), start_page, end_page, zone)].append((section_index, section))

    units: list[dict[str, Any]] = []
    audit: list[dict[str, Any]] = []
    for zone_key, zone in ZONE_MAP.items():
        zone_text = doc.get("targeted_zones", {}).get(zone_key, "")
        if not zone_text:
            audit.append({"doc_id": doc["doc_id"], "zone": zone, "issue": "missing_zone_text"})
            continue
        pattern = ZONE_A_HEADER_RE if zone == "Zone_A" else SECTION_HEADER_RE
        matches = list(pattern.finditer(zone_text))
        used: set[int] = set()

        if zone == "Zone_A":
            abstract = doc.get("abstract", "")
            if abstract:
                abstract_start = zone_text.find(abstract)
                if abstract_start >= 0:
                    units.append({
                        "zone": zone,
                        "zone_key": zone_key,
                        "zone_text": zone_text,
                        "title": "Abstract",
                        "section_id": "ABSTRACT",
                        "section_index": 0,
                        "section_pages": [1, 1],
                        "fallback_pages": [1],
                        "content_type": "abstract",
                        "body": abstract,
                        "body_start": abstract_start,
                        "section_assigned_zone": "Zone A (abstract)",
                    "section_match_quality": "top_level_abstract_field",
                    "page_precision_override": "explicit_page_1",
                })
                else:
                    audit.append({"doc_id": doc["doc_id"], "zone": zone, "issue": "abstract_not_found_in_zone_string"})

        for match_index, match in enumerate(matches):
            body_start = match.end()
            body_end = matches[match_index + 1].start() if match_index + 1 < len(matches) else len(zone_text)
            body = zone_text[body_start:body_end]
            title = match.group("title").strip()
            if zone == "Zone_A":
                title = re.sub(r"\s+-\s+Core Contribution & Organization Excerpt\s*$", "", title, flags=re.IGNORECASE)
                title = re.sub(r"\s+-\s+Core Contribution and Organization Excerpt\s*$", "", title, flags=re.IGNORECASE)
            page_start = int(match.group("start"))
            page_end = int(match.group("end"))
            section_index, section, match_quality = find_section_record(
                title, page_start, page_end, zone, candidates, used
            )
            if section:
                sec_page_start, sec_page_end = parse_page_range(section.get("pages", ""))
                fallback_pages = page_list(sec_page_start, sec_page_end)
                section_id = section.get("sec_id")
                section_title = section.get("full_heading", title)
                assigned_zone = section.get("assigned_zone", "")
            else:
                fallback_pages = page_list(page_start, page_end)
                section_id = None
                section_title = title
                assigned_zone = ""
                audit.append({
                    "doc_id": doc["doc_id"], "zone": zone, "section_heading": title,
                    "section_pages": [page_start, page_end], "issue": "unmatched_heading",
                })
            if not body.strip():
                audit.append({
                    "doc_id": doc["doc_id"], "zone": zone, "section_id": section_id,
                    "section_heading": section_title, "issue": "empty_section_body_skipped",
                })
                continue
            content_type = "intro_excerpt" if "Core Contribution" in match.group("title") else "section_text"
            units.append({
                "zone": zone,
                "zone_key": zone_key,
                "zone_text": zone_text,
                "title": section_title,
                "section_id": section_id,
                "section_index": section_index,
                "section_pages": [page_start, page_end],
                "fallback_pages": fallback_pages,
                "content_type": content_type,
                "body": body,
                "body_start": body_start,
                "section_assigned_zone": assigned_zone,
                "section_match_quality": match_quality,
            })

    return units, audit


def build_evidence_blocks(
    documents: list[dict[str, Any]],
    source_manifest: dict[str, Any],
    input_sha: str,
    target_words: int,
    max_words: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    source_hashes = {x.get("file_name"): x.get("sha256") for x in source_manifest.get("input_files", [])}
    all_records: list[dict[str, Any]] = []
    all_audit: list[dict[str, Any]] = []

    for doc in documents:
        units, audit = parse_units(doc)
        all_audit.extend(audit)
        zone_hashes = {key: sha256_text(value) for key, value in doc.get("targeted_zones", {}).items()}
        records_by_unit: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
        for unit in units:
            chunks = build_chunks_for_unit(unit, unit["zone_text"], target_words, max_words)
            records_by_unit.append((unit, chunks))

        global_sequence = 0
        for unit, chunks in records_by_unit:
            for chunk in chunks:
                global_sequence += 1
                if unit["section_index"] == 0:
                    section_slug = "ABSTRACT"
                elif unit["section_index"] is None:
                    section_slug = f"UNMATCHED-{global_sequence:03d}"
                else:
                    section_slug = re.sub(r"[^A-Za-z0-9]+", "-", str(unit["section_id"] or "UNMATCHED")).strip("-").upper() or "UNMATCHED"
                    section_slug = f"S{unit['section_index']:02d}-{section_slug}"
                chunk["evidence_id"] = (
                    f"{doc['doc_id']}-{ZONE_SHORT[unit['zone']]}-{section_slug}-C{chunk['chunk_index']:03d}"
                )
                pages = chunk["page_numbers"]
                page_start = min(pages) if pages else None
                page_end = max(pages) if pages else None
                chunk.update({
                    "doc_id": doc["doc_id"],
                    "batch_id": doc.get("batch_id", ""),
                    "batch_position": doc.get("batch_position"),
                    "document_title": doc.get("title", ""),
                    "authors": doc.get("authors", ""),
                    "journal": doc.get("journal", ""),
                    "pub_year": doc.get("pub_year"),
                    "doi": doc.get("doi", ""),
                    "source_pdf": doc.get("source_pdf_path", ""),
                    "source_pdf_sha256": source_hashes.get(doc.get("file_name")),
                    "zone": unit["zone"],
                    "zone_text_key": unit["zone_key"],
                    "zone_text_sha256": zone_hashes.get(unit["zone_key"]),
                    "section_id": unit["section_id"],
                    "section_index": unit["section_index"],
                    "section_title": unit["title"],
                    "retrieval_text": f"{unit['title']}\n{chunk['text']}",
                    "retrieval_text_sha256": sha256_text(f"{unit['title']}\n{chunk['text']}"),
                    "section_assigned_zone": unit["section_assigned_zone"],
                    "section_match_quality": unit["section_match_quality"],
                    "section_pages": unit["section_pages"],
                    "page": page_start if page_start == page_end else None,
                    "page_start": page_start,
                    "page_end": page_end,
                    "content_type": unit["content_type"],
                    "source_step1_json_sha256": input_sha,
                    "document_sequence": global_sequence,
                })
                all_records.append(chunk)
    return all_records, all_audit


def verify_records(
    records: list[dict[str, Any]],
    documents_by_id: dict[str, dict[str, Any]],
    max_words: int,
    expected_source_hashes: dict[str, str],
    input_sha: str,
) -> dict[str, Any]:
    seen_ids: set[str] = set()
    duplicate_ids: list[str] = []
    offset_mismatches: list[str] = []
    text_mismatches: list[str] = []
    over_max: list[dict[str, Any]] = []
    empty_text: list[str] = []
    invalid_bounds: list[str] = []
    page_bounds_errors: list[str] = []
    page_metadata_errors: list[str] = []
    text_hash_errors: list[str] = []
    zone_text_hash_errors: list[str] = []
    step1_input_hash_errors: list[str] = []
    stored_count_errors: list[str] = []
    unmatched_sections: list[str] = []
    source_hash_errors: list[str] = []
    retrieval_text_errors: list[str] = []
    ranges_by_unit: dict[tuple[str, str, int | None], list[tuple[int, int, str]]] = defaultdict(list)
    for record in records:
        eid = record["evidence_id"]
        if eid in seen_ids:
            duplicate_ids.append(eid)
        seen_ids.add(eid)
        if not record["text"].strip():
            empty_text.append(eid)
        if record["word_count"] > max_words:
            over_max.append({"evidence_id": eid, "word_count": record["word_count"]})
        doc = documents_by_id[record["doc_id"]]
        zone_text = doc["targeted_zones"][record["zone_text_key"]]
        if record.get("word_count") != count_words(record["text"]) or record.get("char_count") != len(record["text"]):
            stored_count_errors.append(eid)
        if record.get("zone_text_sha256") != sha256_text(zone_text):
            zone_text_hash_errors.append(eid)
        if record.get("source_step1_json_sha256") != input_sha:
            step1_input_hash_errors.append(eid)
        # NOTE: this cross-check only has meaning when a Step 1 run_manifest.json
        # with a populated "input_files" list was actually supplied/found. If the
        # manifest is missing, unreadable, or empty (e.g. it wasn't copied/extracted
        # alongside this script on some other machine), there is nothing to check
        # against -- treat that as "skip", not "fail", so a missing optional audit
        # file doesn't block otherwise-correct chunking. A manifest that IS present
        # but disagrees with the computed hash is still treated as a real failure.
        if expected_source_hashes:
            expected_pdf_hash = expected_source_hashes.get(doc.get("file_name", ""))
            if not expected_pdf_hash or record.get("source_pdf_sha256") != expected_pdf_hash:
                source_hash_errors.append(eid)
        pages = record.get("page_numbers", [])
        if pages:
            page_start, page_end = min(pages), max(pages)
            expected_page = page_start if page_start == page_end else None
            if record.get("page_start") != page_start or record.get("page_end") != page_end or record.get("page") != expected_page:
                page_metadata_errors.append(eid)
        elif record.get("page_start") is not None or record.get("page_end") is not None or record.get("page") is not None:
            page_metadata_errors.append(eid)
        start, end = record["char_start"], record["char_end"]
        if not (0 <= start < end <= len(zone_text)):
            invalid_bounds.append(eid)
        ranges_by_unit[(record["doc_id"], record["zone"], record.get("section_index"))].append((start, end, eid))
        if any(page < 1 or page > doc.get("total_pages", 0) for page in record.get("page_numbers", [])):
            page_bounds_errors.append(eid)
        if record.get("text_sha256") != sha256_text(record["text"]):
            text_hash_errors.append(eid)
        expected_retrieval_text = f"{record.get('section_title','')}\n{record['text']}"
        if record.get("retrieval_text") != expected_retrieval_text or record.get("retrieval_text_sha256") != sha256_text(expected_retrieval_text):
            retrieval_text_errors.append(eid)
        if record.get("section_match_quality") == "unmatched_heading" or record.get("section_id") is None:
            unmatched_sections.append(eid)
        if expected_source_hashes and not record.get("source_pdf_sha256"):
            source_hash_errors.append(eid)
        excerpt = zone_text[start:end]
        if excerpt != record["source_excerpt"]:
            offset_mismatches.append(eid)
        normalized_excerpt = PAGE_TAG_RE.sub(" ", excerpt)
        normalized_excerpt = re.sub(r"\s+", " ", normalized_excerpt).strip()
        if normalized_excerpt != record["text"]:
            text_mismatches.append(eid)
    overlapping_ranges: list[tuple[str, str]] = []
    for ranges in ranges_by_unit.values():
        ordered = sorted(ranges)
        for previous, current in zip(ordered, ordered[1:]):
            if current[0] < previous[1]:
                overlapping_ranges.append((previous[2], current[2]))
    return {
        "record_count": len(records),
        "unique_evidence_ids": len(seen_ids),
        "duplicate_evidence_ids": duplicate_ids,
        "empty_text_evidence_ids": empty_text,
        "offset_mismatches": offset_mismatches,
        "source_excerpt_text_mismatches": text_mismatches,
        "chunks_over_max_words": over_max,
        "invalid_offset_bounds": invalid_bounds,
        "overlapping_offset_ranges": overlapping_ranges,
        "page_bounds_errors": page_bounds_errors,
        "page_metadata_errors": page_metadata_errors,
        "text_hash_errors": text_hash_errors,
        "zone_text_hash_errors": zone_text_hash_errors,
        "step1_input_hash_errors": step1_input_hash_errors,
        "stored_count_errors": stored_count_errors,
        "retrieval_text_errors": retrieval_text_errors,
        "unmatched_section_ids": unmatched_sections,
        "source_pdf_hash_errors": source_hash_errors,
        "offset_checks_passed": not offset_mismatches,
        "offset_bounds_check_passed": not invalid_bounds,
        "nonoverlap_check_passed": not overlapping_ranges,
        "source_excerpt_text_checks_passed": not text_mismatches,
        "stable_id_check_passed": not duplicate_ids,
        "nonempty_text_check_passed": not empty_text,
        "max_word_limit_check_passed": not over_max,
        "page_bounds_check_passed": not page_bounds_errors,
        "page_metadata_check_passed": not page_metadata_errors,
        "text_hash_check_passed": not text_hash_errors,
        "zone_text_hash_check_passed": not zone_text_hash_errors,
        "step1_input_hash_check_passed": not step1_input_hash_errors,
        "stored_count_check_passed": not stored_count_errors,
        "retrieval_text_check_passed": not retrieval_text_errors,
        "section_match_check_passed": not unmatched_sections,
        "source_pdf_hash_check_passed": not source_hash_errors,
    }


def make_qa_report(
    records: list[dict[str, Any]],
    docs: list[dict[str, Any]],
    audit: list[dict[str, Any]],
    qa: dict[str, Any],
    target_words: int,
    max_words: int,
) -> str:
    by_doc_zone: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_doc_zone[(record["doc_id"], record["zone"])].append(record)
    lines = [
        "# Fine-grained evidence block QA",
        "",
        "- Chunker version: `0.1.0`",
        f"- Config: target `{target_words}` words; maximum `{max_words}` words; overlap `0`.",
        "- Boundary method: sentence-grouped within each section; unusually long sentences are split at clause punctuation, then at a word boundary if required.",
        "- Offset basis: `char_start`/`char_end` are zero-based, end-exclusive Unicode-code-point indices into the exact Step 1 zone string, not raw PDF bytes or glyph positions. `source_excerpt` preserves the raw zone substring including inserted page tags for exact offset checking.",
        "- `text` excludes inserted `[Page n]` tags and collapses layout whitespace; section/page metadata are preserved separately. No symbols were guessed or repaired.",
        "",
        "## Per-document counts",
        "",
        "| Doc ID | Evidence blocks | Zone A | Zone B | Zone C | Zone D | Unmapped glyph markers in blocks |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for doc in docs:
        doc_records = [r for r in records if r["doc_id"] == doc["doc_id"]]
        zones = [len(by_doc_zone.get((doc["doc_id"], f"Zone_{letter}"), [])) for letter in "ABCD"]
        marker_count = sum(r["unmapped_glyph_marker_count"] for r in doc_records)
        lines.append(f"| {doc['doc_id']} | {len(doc_records)} | {zones[0]} | {zones[1]} | {zones[2]} | {zones[3]} | {marker_count} |")
    lines += [
        "",
        "## QA checks",
        "",
        f"- Unique evidence IDs: `{qa['unique_evidence_ids'] == qa['record_count']}`",
        f"- Offsets resolve to stored source excerpts: `{qa['offset_checks_passed']}`",
        f"- Offsets are in bounds and non-overlapping within each source section: `{qa['offset_bounds_check_passed'] and qa['nonoverlap_check_passed']}`",
        f"- Normalized source excerpt matches evidence `text`: `{qa['source_excerpt_text_checks_passed']}`",
        f"- Page bounds/ranges and source PDF, Step 1 input, and Zone hashes are valid: `{qa['page_bounds_check_passed'] and qa['page_metadata_check_passed'] and qa['source_pdf_hash_check_passed'] and qa['step1_input_hash_check_passed'] and qa['zone_text_hash_check_passed']}`",
        f"- Evidence/retrieval-text hashes and section-heading matches are valid: `{qa['text_hash_check_passed'] and qa['retrieval_text_check_passed'] and qa['section_match_check_passed']}`",
        f"- Stored word and character counts match the evidence text: `{qa['stored_count_check_passed']}`",
        "- `retrieval_text` prepends the section heading to evidence `text`; source offsets address only the evidence substring, not the added heading.",
        "- The 240-word cap applies to evidence `text`; `retrieval_text` additionally includes the section heading.",
        f"- No empty chunks: `{qa['nonempty_text_check_passed']}`",
        f"- All chunks are within the configured maximum: `{qa['max_word_limit_check_passed']}`",
        f"- Short chunks (<40 words): `{qa.get('short_chunk_count', 0)}`; these are retained source units, not padded with guessed text.",
        f"- Heading/body audit notes: `{len(audit)}` total; empty parent/heading-only sections are logged as skipped, not fabricated.",
        "- `text_sha256` and `retrieval_text_sha256` are recorded for each corresponding text field.",
        "",
        "## Limitations and manual review",
        "",
        "1. Step 1 did not retain paragraph bounding boxes or raw-PDF character offsets. These blocks are traceable to exact Step 1 zone strings, section headings, and extracted page tags/ranges; they are not raw-PDF character offsets.",
        "2. PDF line breaks were reflowed to spaces. OCR/text extraction errors already present in the Zone input remain unchanged. `⟦PDF_GLYPH_U+XXXX⟧` markers are preserved and are not recovered symbols.",
        "3. Chunk sizes are word-based because no target embedding tokenizer has been selected. Treat this as a versioned preprocessing default; tune it during retrieval pilot before indexing.",
        "4. Zone A metadata labels are not evidence blocks; the abstract and retained contribution/intro text are included. Empty headings are omitted.",
    ]
    short_records = [record for record in records if record["word_count"] < 40]
    if short_records:
        lines += ["", "## Short-block review (<40 words)", "", "| Evidence ID | Zone | Section | Pages | Words | Text sample |", "|---|---|---|---|---:|---|"]
        for record in short_records:
            sample = markdown_escape_cell(record["text"][:120])
            pages = ",".join(map(str, record["page_numbers"]))
            lines.append(f"| {record['evidence_id']} | {record['zone']} | {markdown_escape_cell(record['section_title'])} | {pages} | {record['word_count']} | {sample} |")
    if audit:
        lines += ["", "## Audit notes", "", "| Doc ID | Zone | Issue | Heading / detail |", "|---|---|---|---|"]
        for item in audit[:300]:
            detail = item.get("section_heading") or item.get("section_id") or item.get("zone", "")
            lines.append(f"| {item.get('doc_id','')} | {item.get('zone','')} | {item.get('issue','')} | {markdown_escape_cell(detail)} |")
        if len(audit) > 300:
            lines.append(f"\nOnly the first 300 of {len(audit)} audit entries are displayed; see `chunking_manifest.json` for total count.")

    risk_records = [r for r in records if r.get("formula_layout_risk")]
    lines += [
        "",
        "## formula_layout_risk - full systematic scan (not a sample)",
        "",
        "Heuristic, signal-based flag computed for every evidence block (all zones), not just a manual sample. "
        "It marks candidates where PDF text extraction likely scrambled inline math/equation layout "
        "(subscripts, stacked symbols, multi-column formula runs). A flagged block is NOT auto-corrected; "
        "it is a routing signal to prioritize Step 5 gold-standard / agent-assisted review. Signals used: "
        "unmapped glyph markers, Greek letters/math unicode symbols, subscript-like tokens (e.g. Qu,t), "
        "equation numbering patterns (e.g. (12)), spaced math operators, and abnormally low English-stopword "
        "density for the block's length. Score threshold for formula_layout_risk=true is >= 2.0.",
        "",
        f"- Total evidence blocks scanned: `{len(records)}`",
        f"- Flagged formula_layout_risk=true: `{len(risk_records)}`",
        "",
    ]
    if risk_records:
        lines += ["| Evidence ID | Zone | Score | Signals | Text sample |", "|---|---|---:|---|---|"]
        for r in sorted(risk_records, key=lambda x: -x["formula_layout_risk_score"]):
            sample = markdown_escape_cell(r["text"][:100])
            signals = ", ".join(r["formula_layout_risk_signals"])
            lines.append(f"| {r['evidence_id']} | {r['zone']} | {r['formula_layout_risk_score']} | {signals} | {sample} |")
    return "\n".join(lines) + "\n"


def generate(input_path: Path, source_manifest_path: Path, output_dir: Path, target_words: int, max_words: int) -> None:
    if target_words < 1 or max_words < target_words:
        raise ValueError("Require 1 <= target_words <= max_words")
    input_bytes = input_path.read_bytes()
    input_sha = sha256_bytes(input_bytes)
    documents = json.loads(input_bytes.decode("utf-8"))
    if not isinstance(documents, list):
        raise ValueError("Step 1 input must be a JSON array of document records")
    if source_manifest_path.exists():
        source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))
        if not source_manifest.get("input_files"):
            print(
                f"WARNING: {source_manifest_path} exists but has no 'input_files' entries; "
                "the optional source-PDF-hash audit check will be skipped for this run "
                "(does not affect evidence block text/offsets/sections correctness)."
            )
    else:
        source_manifest = {}
        print(
            f"WARNING: Step 1 run manifest not found at {source_manifest_path}; "
            "the optional source-PDF-hash audit check will be skipped for this run "
            "(does not affect evidence block text/offsets/sections correctness). "
            "Pass --source-manifest to point at a valid run_manifest.json if you have one."
        )
    output_dir.mkdir(parents=True, exist_ok=True)

    records, audit = build_evidence_blocks(documents, source_manifest, input_sha, target_words, max_words)
    documents_by_id = {doc["doc_id"]: doc for doc in documents}
    expected_source_hashes = {
        item.get("file_name", ""): item.get("sha256", "")
        for item in source_manifest.get("input_files", [])
    }
    qa = verify_records(records, documents_by_id, max_words, expected_source_hashes, input_sha)
    qa["short_chunk_count"] = sum(record["word_count"] < 40 for record in records)
    qa["short_chunk_ids"] = [record["evidence_id"] for record in records if record["word_count"] < 40]

    jsonl_path = output_dir / "evidence_blocks.jsonl"
    with jsonl_path.open("w", encoding="utf-8", newline="\n") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    per_doc_zone: dict[str, Counter[str]] = defaultdict(Counter)
    per_doc_words: dict[str, list[int]] = defaultdict(list)
    for doc in documents:
        per_doc_zone[doc["doc_id"]] = Counter({f"Zone_{letter}": 0 for letter in "ABCD"})
    for record in records:
        per_doc_zone[record["doc_id"]][record["zone"]] += 1
        per_doc_words[record["doc_id"]].append(record["word_count"])

    manifest = {
        "workflow": "Step 2 fine-grained evidence-block chunking from Zone A-D slices",
        "chunker_version": "0.1.0",
        "generated_at_local_date": datetime.now().astimezone().date().isoformat(),
        "batch_id": documents[0].get("batch_id") if documents else None,
        "document_count": len(documents),
        "script": {
            "path": Path(__file__).name,
            "sha256": sha256_bytes(Path(__file__).read_bytes()),
        },
        "input": {
            "path": str(input_path.relative_to(ROOT)) if input_path.is_relative_to(ROOT) else str(input_path),
            "sha256": input_sha,
            "zone_run_manifest_path": str(source_manifest_path.relative_to(ROOT)) if source_manifest_path.is_relative_to(ROOT) else str(source_manifest_path),
            "zone_run_manifest_sha256": sha256_bytes(source_manifest_path.read_bytes()) if source_manifest_path.exists() else None,
        },
        "configuration": {
            "target_words": target_words,
            "maximum_words": max_words,
            "overlap_words": 0,
            "unit_of_chunking": "sentence groups inside one section and one Zone",
            "sentence_splitter": "rule-based punctuation splitter with common scientific abbreviation exceptions",
            "word_count_method": "Unicode word regex; PDF_GLYPH markers excluded from word counts",
            "page_marker_policy": "remove injected [Page n] from text; retain page_numbers from markers; fall back to section page range when tags are absent",
            "offset_basis": "zero-based, end-exclusive Unicode code-point indices into the exact Step 1 targeted_zones[zone_text_key] string; source_excerpt stores the addressed substring",
            "retrieval_text_policy": "section_title + newline + text; heading is for retrieval only and is not part of the evidence span or word cap",
            "no_symbol_reconstruction": True,
        },
        "outputs": {
            "evidence_blocks_file": jsonl_path.name,
            "evidence_blocks_count": len(records),
            "evidence_blocks_sha256": sha256_bytes(jsonl_path.read_bytes()),
            "qa_report_file": "chunk_qa.md",
        },
        "qa": {
            **qa,
            "audit_note_count": len(audit),
            "per_document_zone_counts": {doc_id: dict(counts) for doc_id, counts in per_doc_zone.items()},
            "per_document_word_count_range": {
                doc_id: {"min": min(words), "max": max(words), "mean": round(sum(words) / len(words), 2)}
                for doc_id, words in per_doc_words.items() if words
            },
        },
        "per_document": [
            {
                "doc_id": doc["doc_id"],
                "file_name": doc["file_name"],
                "source_pdf": doc.get("source_pdf_path", ""),
                "source_pdf_sha256": next((x.get("sha256") for x in source_manifest.get("input_files", []) if x.get("file_name") == doc.get("file_name")), None),
                "section_count": len(doc.get("section_tree", [])),
                "zone_text_sha256": {key: sha256_text(value) for key, value in doc.get("targeted_zones", {}).items()},
            }
            for doc in documents
        ],
        "not_executed": ["embedding/vectorization", "BM25 indexing", "RAG retrieval", "LLM extraction/critic", "human evaluation"],
    }
    qa_report = make_qa_report(records, documents, audit, qa, target_words, max_words)
    qa_report_path = output_dir / "chunk_qa.md"
    qa_report_path.write_text(qa_report, encoding="utf-8")
    manifest["outputs"].update({
        "evidence_blocks_size_bytes": jsonl_path.stat().st_size,
        "qa_report_sha256": sha256_bytes(qa_report_path.read_bytes()),
        "qa_report_size_bytes": qa_report_path.stat().st_size,
    })
    manifest_path = output_dir / "chunking_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Chunked {len(documents)} documents into {len(records)} evidence blocks.")
    print(
        "QA: "
        f"offsets={qa['offset_checks_passed'] and qa['offset_bounds_check_passed'] and qa['nonoverlap_check_passed']}, "
        f"text={qa['source_excerpt_text_checks_passed']}, retrieval_text={qa['retrieval_text_check_passed']}, "
        f"hashes={qa['text_hash_check_passed'] and qa['zone_text_hash_check_passed'] and qa['source_pdf_hash_check_passed']}, "
        f"sections={qa['section_match_check_passed']}, ids={qa['stable_id_check_passed']}, "
        f"max_words={qa['max_word_limit_check_passed']}"
    )
    print(f"Saved chunk outputs to: {output_dir}")
    required_checks = (
        "offset_checks_passed", "offset_bounds_check_passed", "nonoverlap_check_passed",
        "source_excerpt_text_checks_passed", "stable_id_check_passed", "nonempty_text_check_passed",
        "max_word_limit_check_passed", "page_bounds_check_passed", "page_metadata_check_passed",
        "text_hash_check_passed", "zone_text_hash_check_passed", "step1_input_hash_check_passed",
        "stored_count_check_passed", "retrieval_text_check_passed", "section_match_check_passed",
        "source_pdf_hash_check_passed",
    )
    if any(not qa[key] for key in required_checks):
        raise RuntimeError("Chunk QA assertions failed; inspect chunk_qa.md and chunking_manifest.json")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Step 1 JSON with Zone A-D slices")
    parser.add_argument("--source-manifest", type=Path, default=DEFAULT_SOURCE_MANIFEST, help="Step 1 run manifest for PDF hashes")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="Flat output directory for evidence blocks")
    parser.add_argument("--target-words", type=int, default=180, help="Soft target words per evidence block")
    parser.add_argument("--max-words", type=int, default=240, help="Hard maximum words per evidence block")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    try:
        generate(args.input.resolve(), args.source_manifest.resolve(), args.output_dir.resolve(), args.target_words, args.max_words)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
