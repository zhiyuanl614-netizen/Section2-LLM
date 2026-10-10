# -*- coding: utf-8 -*-
"""
Step 1: Academic PDF Two-Column Layout Reconstruction, Section Tree Parser & Four-Zone Targeted Slicer
Target: Chapter 2 - LLM-Driven Text Data Mining for Frontier Research Direction Identification
"""

import os
import re
import json
import argparse
import html
import unicodedata
import pymupdf
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import docx
from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn, nsdecls

# Academic papers use Arabic-numbered, Roman-numbered (common in IEEE), and
# lettered subsection headings. Also recognize common unnumbered section titles.
HEADING_REGEX = re.compile(
    r'^(?:((?:[1-9]\d*(?:\.\d+)*)|(?:[IVXLCDM]{1,8})|(?:[A-Z]))[.)]?\s+(.{3,110})|'
    r'(Acknowledgments?|References|Appendix|Declaration of competing interest|'
    r'CRediT authorship contribution statement|Data availability|Introduction|'
    r'Methodology|Methods|Materials and methods|Results(?: and Discussion)?|'
    r'Discussion|Conclusions?|Case Studies?|Limitations|Future Work|'
    r'Bibliography|Funding|Conflict of Interest))$',
    re.IGNORECASE
)

BOILERPLATE_PATTERNS = [
    r'^Contents lists available at ScienceDirect$',
    r'^journal homepage:\s*www\.elsevier\.com',
    r'^Available online\s+\d+',
    r'^\*\s*Corresponding author',
    r'^E-mail address',
    r'^https?://doi\.org/',
    r'^\d{4}-\d{4}/©',
    r'^Received\s+\d+\s+[A-Za-z]+\s+\d{4}',
]

def clean_text_line(text):
    """Replace XML-invalid PDF control glyphs visibly and normalize whitespace."""
    # Preserve evidence of failed glyph mapping (often math/special symbols) without
    # emitting XML-invalid control characters into DOCX or other downstream artifacts.
    text = str(text or '')
    text = re.sub(
        r'[\x00-\x08\x0b\x0c\x0e-\x1f]',
        lambda m: f" ⟦PDF_GLYPH_U+{ord(m.group(0)):04X}⟧ ",
        text,
    )
    text = re.sub(r'\xad\s*', '', text)
    text = re.sub(r'-\s+(?=[a-z])', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

UNMAPPED_GLYPH_RE = re.compile(r"⟦PDF_GLYPH_U\+[0-9A-F]{4,6}⟧", re.IGNORECASE)

_TRAILING_HARD_HYPHEN_RE = re.compile(r'[A-Za-z]-$')


def detect_line_join_mode(raw_line_text):
    """Classify how this visual line should be re-joined with the next line.

    PDF line-wrap hyphenation uses two distinct characters that must be handled
    differently when physical lines are later concatenated into flowing prose:

    - U+00AD SOFT HYPHEN marks a discretionary break *inside a single word*
      (e.g. "hy\xad" + "draulic" -> "hydraulic"). It carries no meaning of its
      own and must be removed with no space and no literal hyphen inserted.
    - A plain ASCII '-' immediately preceded by a letter at the end of a line
      is the real character of a hyphenated compound word (e.g. "two-" +
      "stage" -> "two-stage") and must be kept, again with no inserted space.

    Returns 'merge' (drop break char, concatenate), 'hyphen' (keep trailing
    '-', concatenate), or 'space' (default: join with a single space).
    """
    stripped = (raw_line_text or '').rstrip()
    if stripped.endswith('\xad'):
        return 'merge'
    if _TRAILING_HARD_HYPHEN_RE.search(stripped):
        return 'hyphen'
    return 'space'


def join_line_texts(buf_items):
    """Re-join cleaned line texts honoring each line's join_mode with the next line."""
    if not buf_items:
        return ""
    out = buf_items[0]["text"]
    for i in range(1, len(buf_items)):
        prev_mode = buf_items[i - 1].get("join_mode", "space")
        cur_text = buf_items[i]["text"]
        if prev_mode in ("merge", "hyphen"):
            out += cur_text
        else:
            out += " " + cur_text
    return out


def count_words(text):
    """Count extracted words without treating glyph-warning markers as prose."""
    text = UNMAPPED_GLYPH_RE.sub(" ", text or "")
    return len(re.findall(r'\b\w+\b', text))


def publication_label(doc_record):
    """Return a transparent display label when PDF metadata is incomplete."""
    journal = doc_record.get("journal") or "期刊信息待核"
    year = doc_record.get("pub_year") or "年份待核"
    return f"{journal} ({year})"

def is_boilerplate(text, y0, y1, page_height, pno):
    """Identify header, footer, copyright, and page-number boilerplate."""
    if y0 < 48.0 or y1 > page_height - 42.0:
        return True
    for pat in BOILERPLATE_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            return True
    return False

def is_valid_section_heading(line_text, max_size, is_bold, is_italic):
    """Determine if a line is a true section/subsection heading."""
    line_clean = line_text.strip()
    if len(line_clean) > 115 or len(line_clean) < 4:
        return False
    # Must not end with a period, semicolon, or comma
    if line_clean.endswith('.') or line_clean.endswith(',') or line_clean.endswith(';'):
        return False
    m = HEADING_REGEX.match(line_clean)
    if not m:
        return False
    # Check font style or numbering structure
    sec_num = m.group(1)
    sec_title = m.group(2)
    unnumbered = m.group(3)
    if unnumbered:
        # Unnumbered headings are accepted only when typography or casing supports it.
        return is_bold or is_italic or line_clean.isupper()
    if sec_num:
        if not sec_title or not sec_title[0].isupper():
            return False
        if re.match(r'^\d+\)\s+', line_clean):
            return False  # numbered prose/list items are not section headings
        if sec_num.isdigit() and int(sec_num.split('.')[0]) > 20:
            return False  # filters equation/reference lines misread as headings
        # Single-letter headings require explicit punctuation and heading typography;
        # this avoids treating spaced labels such as "A B S T R A C T" as sections.
        if len(sec_num) == 1 and sec_num.isalpha():
            if not re.match(r'^[A-Za-z][.]\s+', line_clean):
                return False
            roman_single = sec_num.upper() in {"I", "V", "X", "L", "C", "D", "M"}
            if roman_single:
                if not (is_bold or is_italic or line_clean.isupper()):
                    return False
            elif not (is_bold or is_italic):
                return False
            if re.search(r'\b(?:19|20)\d{2}\b|crossref', sec_title, re.I):
                return False
        # Exclude common sentence-like false positives.
        if re.search(r'\b(is|are|was|were|can|will|should|must|has|have)\b', sec_title.lower()):
            return False
        return True
    return False

ABSTRACT_LABEL_RE = re.compile(
    r'^\s*(?:abstract|a\s*b\s*s\s*t\s*r\s*a\s*c\s*t)\s*(?:[-–—:]\s*)?(.*)$',
    re.IGNORECASE | re.DOTALL,
)
KEYWORD_LABEL_RE = re.compile(
    r'^\s*(?:keywords?|key\s+words?|index\s+terms?)\s*(?:[-–—:]\s*)?(.*)$',
    re.IGNORECASE | re.DOTALL,
)


def _page_text_blocks(page):
    return sorted(
        (b for b in page.get_text("blocks") if len(b) > 6 and b[6] == 0),
        key=lambda b: (b[1], b[0]),
    )


def extract_abstract_text(page):
    """Extract Abstract-labelled content rather than relying on fixed x/y coordinates."""
    blocks = _page_text_blocks(page)
    for label_block in blocks:
        raw = str(label_block[4]).strip()
        match = ABSTRACT_LABEL_RE.match(raw)
        if not match:
            continue
        content = clean_text_line(match.group(1))
        if len(content) >= 30:
            return content

        # Some publishers put ABSTRACT in its own block. Collect following
        # content only in that block's column, stopping at keywords/body text.
        x0, y0, y1 = label_block[0], label_block[1], label_block[3]
        same_column = []
        x_tolerance = max(42.0, page.rect.width * 0.10)
        for b in blocks:
            if b is label_block or b[1] < y1 - 2 or b[1] > y0 + 320:
                continue
            if abs(b[0] - x0) > x_tolerance:
                continue
            text = clean_text_line(b[4])
            if not text:
                continue
            if KEYWORD_LABEL_RE.match(text) or re.match(
                r'^(?:[IVXLCDM]+|[1-9]\d*(?:\.\d+)*)[.)]?\s+Introduction\b', text, re.I
            ):
                break
            same_column.append(text)
            if sum(len(x) for x in same_column) >= 4000:
                break
        return " ".join(same_column).strip()
    return ""


def extract_keyword_text(page):
    """Read Keywords/Index Terms from the first page when metadata omits them."""
    blocks = _page_text_blocks(page)
    for i, b in enumerate(blocks):
        raw = clean_text_line(b[4])
        match = KEYWORD_LABEL_RE.match(raw)
        if not match:
            continue
        value = clean_text_line(match.group(1))
        if value:
            return value
        for nxt in blocks[i + 1:]:
            if nxt[1] > b[1] + 120:
                break
            if abs(nxt[0] - b[0]) > max(45.0, page.rect.width * 0.12):
                continue
            candidate = clean_text_line(nxt[4])
            if candidate:
                return candidate
    return ""


def extract_front_page_title(page, filename_title):
    """Recover a visible title block when embedded PDF title metadata is absent."""
    blocks = _page_text_blocks(page)
    abstract_y = min(
        (b[1] for b in blocks if ABSTRACT_LABEL_RE.match(str(b[4]).strip())),
        default=float("inf"),
    )
    seed_words = {
        w for w in re.findall(r'[a-z0-9]+', unicodedata.normalize("NFKC", filename_title).lower())
        if len(w) > 2 and w not in {"the", "and", "for", "with", "from", "under", "based"}
    }
    best = None
    for b in blocks:
        if b[1] >= abstract_y:
            continue
        raw = clean_text_line(unicodedata.normalize("NFKC", str(b[4])))
        if len(raw) < 25 or len(raw) > 500:
            continue
        candidate = re.sub(r'^\s*article\s*[|:–—-]?\s*', '', raw, flags=re.IGNORECASE)
        words = set(re.findall(r'[a-z0-9]+', candidate.lower()))
        score = len(seed_words & words) / max(1, len(seed_words))
        if score >= 0.55 and (best is None or score > best[0]):
            best = (score, candidate)
    return best[1].strip() if best else ""


def extract_byline(page, title):
    """Use the comma-separated line between article title and abstract as a fallback."""
    blocks = _page_text_blocks(page)
    abstract_y = min(
        (b[1] for b in blocks if ABSTRACT_LABEL_RE.match(str(b[4]).strip())),
        default=float("inf"),
    )
    title_words = {
        w for w in re.findall(r'[a-z0-9]+', html.unescape(title).lower())
        if len(w) > 2 and w not in {"the", "and", "for", "with", "from", "under", "based"}
    }
    title_top = None
    for b in blocks:
        if b[1] >= abstract_y:
            continue
        words = set(re.findall(r'[a-z0-9]+', html.unescape(str(b[4])).lower()))
        overlap = len(title_words & words) / max(1, len(title_words))
        if overlap >= 0.30:
            title_top = min(title_top or b[1], b[1])
    if title_top is None:
        return ""

    excluded = (
        "department", "school of", "college of", "university", "laboratory",
        "institute", "center for", "centre for", "received:", "accepted:",
        "published:", "abstract", "keywords", "index terms", "corresponding author",
        "e-mail", "email", "http://", "https://", "article info",
    )
    for b in blocks:
        if b[1] <= title_top + 4 or b[1] >= abstract_y:
            continue
        text = clean_text_line(b[4])
        if len(text) < 8 or len(text) > 450 or "," not in text:
            continue
        if any(term in text.lower() for term in excluded):
            continue
        if re.fullmatch(r'[\W_\d]+', text):
            continue
        return text
    return ""


def normalize_author_line(text):
    """Remove IEEE membership rank tags while preserving the source byline separately."""
    text = clean_text_line(text)
    text = re.sub(
        r'\s*,?\s*(?:(?:student|senior|associate|life|honorary)\s+)?(?:member|fellow)\s*,?\s*IEEE\b',
        '', text, flags=re.IGNORECASE,
    )
    text = re.sub(r'\s*,\s*and\b', ' and', text, flags=re.IGNORECASE)
    text = re.sub(r'\s+,', ',', text)
    text = re.sub(r',\s*,+', ',', text)
    text = re.sub(r'\s+', ' ', text).strip(' ,;')
    return text


def parse_pdf_structure(pdf_path, doc_id):
    """
    Parse a two-column academic PDF into metadata, full hierarchical section tree,
    and Four-Zone Targeted Slices (Zone A, Zone B, Zone C, Zone D) + Stripped Noise stats.
    """
    doc = pymupdf.open(pdf_path)
    meta_raw = doc.metadata or {}
    total_pages = len(doc)
    unmapped_glyph_counts = {}

    # Prefer embedded PDF metadata; use visible front-matter text as a fallback.
    subj = clean_text_line(meta_raw.get("subject", ""))
    front_text = "\n".join(doc[i].get_text("text", sort=True) for i in range(min(3, total_pages)))
    subject_doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', subj)
    front_doi_match = re.search(r'10\.\d{4,9}/[-._;()/:A-Za-z0-9]+', front_text)
    doi_match = subject_doi_match or front_doi_match
    doi = doi_match.group(0).rstrip(".,;)") if doi_match else ""
    doi_source = "PDF subject metadata" if subject_doi_match else ("first-page/front matter" if front_doi_match else "not detected")

    publication_match = re.search(
        r'(?im)^\s*([A-Z][A-Za-z0-9& .’\-]{2,80}?)\s+((?:19|20)\d{2})\s*,\s*\d+',
        front_text,
    )
    year_match = re.search(r'\b((?:19|20)\d{2})\b', subj)
    pub_year = int(year_match.group(1)) if year_match else (int(publication_match.group(2)) if publication_match else None)
    year_source = "PDF subject metadata" if year_match else ("first-page publication header" if publication_match else "not detected")
    journal = re.split(r'[;,]', subj, maxsplit=1)[0].strip() if subj else ""
    journal_source = "PDF subject metadata" if journal else "not detected"
    if not journal and publication_match:
        journal = publication_match.group(1).strip()
        journal_source = "first-page publication header"

    filename_stem = os.path.splitext(os.path.basename(pdf_path))[0]
    filename_title = re.sub(r'^\d+[_\-\s]+', '', filename_stem).replace("_", " ")
    embedded_title = clean_text_line(html.unescape(meta_raw.get("title", "")))
    page1 = doc[0]
    visible_title = extract_front_page_title(page1, filename_title) if not embedded_title else ""
    metadata_title = embedded_title or visible_title or clean_text_line(filename_title)
    title_source = (
        "embedded PDF title metadata" if embedded_title
        else ("first-page visible title" if visible_title else "filename fallback")
    )
    journal_label = journal or "期刊信息待核"
    year_label = pub_year or "年份待核"

    abstract_text = extract_abstract_text(page1)
    embedded_keywords = clean_text_line(meta_raw.get("keywords", ""))
    keywords_text = (embedded_keywords or extract_keyword_text(page1)).strip(" ;,.\t")
    keywords_source = "embedded PDF keyword metadata" if embedded_keywords else ("first-page Keywords/Index Terms label" if keywords_text else "not detected")
    byline_raw = extract_byline(page1, metadata_title)
    author_metadata = clean_text_line(meta_raw.get("author", ""))
    byline_source_found = bool(byline_raw)
    if not byline_raw:
        byline_raw = author_metadata
    authors_line = normalize_author_line(byline_raw)
    authors_source = "first-page byline" if byline_source_found else ("embedded PDF author metadata" if author_metadata else "not detected")

    doi_year_match = re.search(r'\b((?:19|20)\d{2})\b', doi)
    doi_year_token = int(doi_year_match.group(1)) if doi_year_match else None
    metadata_warnings = []
    if pub_year and doi_year_token and pub_year != doi_year_token:
        metadata_warnings.append(
            f"Printed publication year {pub_year} differs from year token {doi_year_token} in DOI string; DOI token meaning not inferred."
        )

    # Now reconstruct reading-order lines across all pages (starting from 1. Introduction)
    ordered_items = []  # list of dicts: {page, text, is_heading, sec_num, sec_title}

    for pno in range(total_pages):
        page = doc[pno]
        pw, ph = page.rect.width, page.rect.height
        mid_x = pw / 2.0
        blocks = page.get_text("dict")["blocks"]

        left_col_blocks = []
        right_col_blocks = []
        spanning_blocks = []

        for b in blocks:
            if b.get("type") != 0:
                continue
            bx0, by0, bx1, by1 = b["bbox"]
            # Extract lines inside block
            block_lines = []
            for l in b["lines"]:
                raw_line = "".join(span["text"] for span in l["spans"])
                for span in l["spans"]:
                    for char in span["text"]:
                        code = ord(char)
                        if code < 32 and char not in "\t\n\r":
                            key = (pno + 1, span.get("font", "unknown"), code)
                            unmapped_glyph_counts[key] = unmapped_glyph_counts.get(key, 0) + 1
                ltxt = clean_text_line(raw_line)
                if not ltxt:
                    continue
                if is_boilerplate(ltxt, l["bbox"][1], l["bbox"][3], ph, pno):
                    continue
                max_sz = max((s["size"] for s in l["spans"]), default=0)
                is_bd = any("bold" in s["font"].lower() or "medi" in s["font"].lower() or (s["flags"] & 16) for s in l["spans"])
                is_it = any("ital" in s["font"].lower() or "obli" in s["font"].lower() or (s["flags"] & 2) for s in l["spans"])
                is_hd = is_valid_section_heading(ltxt, max_sz, is_bd, is_it)
                join_mode = detect_line_join_mode(raw_line) if not is_hd else "space"
                block_lines.append({
                    "page": pno + 1,
                    "y0": l["bbox"][1],
                    "x0": l["bbox"][0],
                    "text": ltxt,
                    "is_heading": is_hd,
                    "join_mode": join_mode
                })

            if not block_lines:
                continue

            if bx1 <= mid_x + 15:
                left_col_blocks.append((by0, block_lines))
            elif bx0 >= mid_x - 15:
                right_col_blocks.append((by0, block_lines))
            else:
                spanning_blocks.append((by0, block_lines))

        left_col_blocks.sort(key=lambda x: x[0])
        right_col_blocks.sort(key=lambda x: x[0])
        spanning_blocks.sort(key=lambda x: x[0])

        # Standard two-column academic order: left column top-to-bottom, right column top-to-bottom, then spanning captions
        for _, blines in left_col_blocks + right_col_blocks + spanning_blocks:
            ordered_items.extend(blines)

    # Exclude title/abstract/front matter using the first detected body heading,
    # rather than a fixed page-1 y-coordinate that can drop legitimate article text.
    first_body_heading = next(
        (i for i, item in enumerate(ordered_items) if item["is_heading"]),
        None,
    )
    if first_body_heading is not None:
        ordered_items = ordered_items[first_body_heading:]

    # Group lines into hierarchical sections
    sections = []
    cur_sec = {
        "sec_id": "0",
        "sec_title": "Preamble",
        "start_page": 1,
        "end_page": 1,
        "lines": []
    }

    for item in ordered_items:
        if item["is_heading"]:
            if cur_sec["lines"] or cur_sec["sec_id"] != "0":
                sections.append(cur_sec)
            m = HEADING_REGEX.match(item["text"])
            if m and m.group(1):
                s_id = m.group(1)
                s_title = m.group(2).strip()
            else:
                s_id = item["text"].strip()
                s_title = item["text"].strip()
            cur_sec = {
                "sec_id": s_id,
                "sec_title": s_title,
                "full_heading": item["text"],
                "start_page": item["page"],
                "end_page": item["page"],
                "lines": []
            }
        else:
            cur_sec["end_page"] = max(cur_sec["end_page"], item["page"])
            cur_sec["lines"].append(item)

    if cur_sec["lines"] or cur_sec["sec_id"] != "0":
        sections.append(cur_sec)

    # Consolidate text with page markers [Page X] per section
    for s in sections:
        chunks = []
        last_p = None
        cur_buf = []
        for ln in s["lines"]:
            if ln["page"] != last_p:
                if cur_buf:
                    chunks.append(f"[Page {last_p}] " + join_line_texts(cur_buf))
                    cur_buf = []
                last_p = ln["page"]
            cur_buf.append(ln)
        if cur_buf:
            chunks.append(f"[Page {last_p}] " + join_line_texts(cur_buf))
        s["full_text"] = "\n".join(chunks)
        s["word_count"] = count_words(s["full_text"])
        del s["lines"]

    # Map sections into broad evidence zones. Result/metric headings are checked
    # before case/discussion and methods so quantitative content is not swallowed
    # by the old Zone-B catch-all. Unclear subsections inherit their parent's zone.
    zone_a_parts = [
        f"[Document Metadata] Title: {metadata_title} | Authors: {authors_line or 'Author information pending verification'} | Journal: {journal_label} ({year_label}) | DOI: {doi or 'DOI pending verification'} | Keywords: {keywords_text or 'Keywords pending verification'}",
        f"[Page 1] [Abstract] {abstract_text or 'Abstract text not detected; inspect source PDF.'}"
    ]
    zone_b_parts = []
    zone_c_parts = []
    zone_d_parts = []
    stripped_parts = []
    unclassified_sections = []
    assigned_zone_by_id = {}
    current_major_zone = None
    roman_ids = {"i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv", "xvi", "xvii", "xviii", "xix", "xx"}
    roman_ids_upper = {x.upper() for x in roman_ids}
    major_title_names = {"introduction", "methods", "materials and methods", "methodology", "results", "discussion", "conclusion", "conclusions", "case study", "case studies"}

    for s in sections:
        raw_sid = str(s["sec_id"]).strip()
        sid = raw_sid.casefold()
        stitle = unicodedata.normalize("NFKC", s["sec_title"]).casefold()
        is_roman_major = (
            raw_sid.upper() in roman_ids_upper
            and (str(s["sec_title"]).strip().isupper() or stitle.strip() in major_title_names)
        )
        full_h = s.get("full_heading", s["sec_title"])
        txt = s["full_text"]
        wc = s["word_count"]
        zone = None
        zone_detail = ""
        intro_excerpt = None

        # References and non-analytic back matter.
        if any(k in stitle for k in [
            "reference", "acknowledgment", "declaration", "credit", "data availability",
            "appendix", "nomenclature"
        ]):
            zone, zone_detail = "S", "Stripped_Noise (References/Ack/Front Matter)"
            stripped_parts.append((full_h, wc, "References / acknowledgments / back matter / nomenclature"))
        elif stitle.startswith("related work") or any(k in stitle for k in [
            "literature review", "background on water-energy nexus"
        ]):
            zone, zone_detail = "S", "Stripped_Noise (Related Work Review)"
            stripped_parts.append((full_h, wc, "Related work / literature review"))

        # Zone A: the introduction's closing contribution/organization passage.
        elif stitle.strip() == "introduction" or sid == "1":
            zone = "A"
            zone_detail = "Zone A (Introduction / contribution)"
            words = txt.split()
            if len(words) > 220:
                keep_words = words[-220:]
                stripped_wc = max(0, count_words(txt) - count_words(intro_excerpt))
                intro_excerpt = " ".join(keep_words)
                zone_detail = "Zone A (closing Introduction excerpt)"
                stripped_parts.append((f"{full_h} (Early Background Review Part)", stripped_wc, "Introduction background review; only closing excerpt retained"))
        elif any(k in stitle for k in ["contribution", "paper organization", "paper structure", "research objective", "research aim"]):
            zone, zone_detail = "A", "Zone A (contribution / paper organization)"

        # Zone C: empirical/numerical results, metrics, performance, and evaluation.
        elif any(k in stitle for k in [
            "result", "metric", "index function", "or index", "ior", "ior computation", "computation", "calculation",
            "operational system resilience", "operational resilience", "correlation analysis",
            "evaluation", "sensitivity", "performance", "comparative", "comparison",
            "numerical", "quantification", "validation", "effectiveness", "pressure function",
            "availability function", "demand satisfaction function", "resilience function", "relative decrease", "steady-state",
            "energy consumption analysis", "power smoothing analysis", "economy analysis",
            "resilience assessment", "resilience evaluation", "influence of", "functional loss",
            "impact of"
        ]) or (
            "simulation" in stitle and any(k in stitle for k in ["result", "performance", "analysis", "case"])
        ) or (
            "analysis" in stitle and any(k in stitle for k in ["consumption", "power", "economy", "performance", "resilience", "comparative", "seismic"])
        ):
            zone, zone_detail = "C", "Zone C (metrics / results / evaluation)"

        # Zone B: formulations, coupling, models, operating strategies, and algorithms.
        elif any(k in stitle for k in [
            "methodology", "method", "topology", "formulation", "formalization", "linearization", "model",
            "optimization", "approach", "framework", "initial trigger", "functional failure",
            "coupled component", "cascading failure", "system interdepend", "water supply system",
            "power supply system", "federate", "federation", "algorithm", "constraint",
            "mechanism", "operation", "strategy", "representation", "dependence pattern",
            "resilience definition", "resilience model", "resilience feature", "robustness",
            "resourcefulness", "rapidity", "restoration", "repair", "definition"
        ]):
            zone, zone_detail = "B", "Zone B (model / coupling / method)"


        # Zone D: case setup, scenarios, discussion, limitations, conclusions, and impact context.
        elif any(k in stitle for k in [
            "case study", "case studies", "case description", "case setup", "test system",
            "test case", "scenario", "discussion", "conclusion", "limitation", "future work",
            "application example", "hidden impact", "chain impact", "cycle impact", "social impact", "human impact"
        ]):
            zone, zone_detail = "D", "Zone D (case / discussion / limitations)"

        # Resolve still-ambiguous children from their parent section before falling back.
        if zone is None:
            parent_zone = None
            if "." in sid:
                parts = sid.split(".")
                for depth in range(len(parts) - 1, 0, -1):
                    parent_id = ".".join(parts[:depth])
                    if parent_id in assigned_zone_by_id:
                        candidate = assigned_zone_by_id[parent_id]
                        if candidate in {"A", "B", "C", "D"}:
                            parent_zone = candidate
                            break
            elif len(raw_sid) == 1 and raw_sid.isalpha() and not is_roman_major:
                parent_zone = current_major_zone
            if parent_zone:
                zone = parent_zone
                zone_detail = f"Zone {zone} (inherited from parent; verify)"
            else:
                zone = "B"
                zone_detail = "Zone B fallback (manual review required)"
                unclassified_sections.append({"section": full_h, "pages": f"P{s['start_page']}-P{s['end_page']}"})
                zone_b_parts.append(f"### [UNCLASSIFIED - VERIFY] {full_h} (Pages {s['start_page']}-{s['end_page']})\n{txt}")

        if zone == "A":
            if intro_excerpt is not None:
                zone_a_parts.append(f"[{full_h} - Core Contribution & Organization Excerpt (Pages {s['start_page']}-{s['end_page']})]\n{intro_excerpt}")
            else:
                zone_a_parts.append(f"[{full_h} (Pages {s['start_page']}-{s['end_page']})]\n{txt}")
        elif zone == "B" and "fallback" not in zone_detail.lower():
            zone_b_parts.append(f"### {full_h} (Pages {s['start_page']}-{s['end_page']})\n{txt}")
        elif zone == "C":
            zone_c_parts.append(f"### {full_h} (Pages {s['start_page']}-{s['end_page']})\n{txt}")
        elif zone == "D":
            zone_d_parts.append(f"### {full_h} (Pages {s['start_page']}-{s['end_page']})\n{txt}")

        s["assigned_zone"] = zone_detail
        assigned_zone_by_id[sid] = zone
        if (raw_sid.isdigit() or is_roman_major) and zone in {"A", "B", "C", "D"}:
            current_major_zone = zone

    zone_a_str = "\n\n".join(zone_a_parts)
    zone_b_str = "\n\n".join(zone_b_parts)
    zone_c_str = "\n\n".join(zone_c_parts)
    zone_d_str = "\n\n".join(zone_d_parts)

    wc_a = count_words(zone_a_str)
    wc_b = count_words(zone_b_str)
    wc_c = count_words(zone_c_str)
    wc_d = count_words(zone_d_str)
    wc_kept = wc_a + wc_b + wc_c + wc_d
    wc_stripped = sum(x[1] for x in stripped_parts)
    wc_total = wc_kept + wc_stripped
    noise_reduction_pct = round(wc_stripped * 100.0 / wc_total, 2) if wc_total > 0 else 0.0

    return {
        "doc_id": doc_id,
        "file_name": os.path.basename(pdf_path),
        "title": metadata_title,
        "authors": authors_line,
        "author_byline_raw": byline_raw,
        "abstract": abstract_text,
        "metadata_sources": {
            "title": title_source,
            "authors": authors_source,
            "journal": journal_source,
            "pub_year": year_source,
            "doi": doi_source,
            "abstract": "first-page labeled block" if abstract_text else "not detected",
            "keywords": keywords_source
        },
        "metadata_warnings": metadata_warnings,
        "journal": journal,
        "pub_year": pub_year,
        "doi": doi,
        "keywords": keywords_text,
        "total_pages": total_pages,
        "unclassified_section_count": len(unclassified_sections),
        "unclassified_sections": unclassified_sections,
        "text_extraction_warnings": {
            "unmapped_glyph_count": sum(unmapped_glyph_counts.values()),
            "unmapped_glyphs": [
                {"page": page_no, "font": font, "codepoint": f"U+{code:04X}", "count": count}
                for (page_no, font, code), count in sorted(unmapped_glyph_counts.items())
            ]
        },
        "word_count_stats": {
            "raw_total_words": wc_total,
            "kept_targeted_words": wc_kept,
            "stripped_noise_words": wc_stripped,
            "noise_reduction_ratio_pct": noise_reduction_pct,
            "zone_a_words": wc_a,
            "zone_b_words": wc_b,
            "zone_c_words": wc_c,
            "zone_d_words": wc_d
        },
        "section_tree": [
            {
                "sec_id": s["sec_id"],
                "full_heading": s.get("full_heading", s["sec_title"]),
                "pages": f"P{s['start_page']}-P{s['end_page']}",
                "word_count": s["word_count"],
                "assigned_zone": s.get("assigned_zone", "")
            }
            for s in sections if s["sec_id"] != "0"
        ],
        "stripped_sections_detail": [
            {"heading": h, "word_count": w, "reason": r} for h, w, r in stripped_parts
        ],
        "targeted_zones": {
            "Zone_A_Meta_Abstract_Contribution": zone_a_str,
            "Zone_B_Coupling_And_Cascading_Model": zone_b_str,
            "Zone_C_Metrics_And_Simulation_Control": zone_c_str,
            "Zone_D_Case_Social_And_Limitations": zone_d_str
        }
    }

def generate_outputs(parsed_docs, out_dir):
    os.makedirs(out_dir, exist_ok=True)

    # 1. Save JSON Data Blocks
    json_path = os.path.join(out_dir, "step1_sliced_pdf_corpus.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(parsed_docs, f, ensure_ascii=False, indent=2)

    # 2. Save Markdown Preview of Targeted Slices
    md_path = os.path.join(out_dir, "step1_sliced_zones_preview.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# Step 1: 学术 PDF 章节结构树解析与四区靶向切片实验预览\n\n")
        for d in parsed_docs:
            st = d["word_count_stats"]
            f.write(f"## {d['doc_id']}: {d['title']}\n")
            f.write(f"- **源文件**: `{d['file_name']}` ({d['total_pages']} 页)\n")
            f.write(f"- **作者与期刊**: {d.get('authors') or '作者信息待核'} | *{publication_label(d)}* | DOI: `{d['doi'] or 'DOI待核'}`\n")
            f.write(f"- **靶向切片降噪统计**: 全文总词数 **{st['raw_total_words']}** 词 $\\rightarrow$ 靶向保留核心词数 **{st['kept_targeted_words']}** 词，自动剥离干扰噪声 **{st['stripped_noise_words']}** 词（**降噪率 {st['noise_reduction_ratio_pct']}%**）\n")
            glyph_warnings = d.get("text_extraction_warnings", {}).get("unmapped_glyphs", [])
            if glyph_warnings:
                warn_codes = ", ".join(f"{w['codepoint']}×{w['count']} ({w['font']}, p.{w['page']})" for w in glyph_warnings[:12])
                f.write(f"- **PDF字体映射提示**: {d['text_extraction_warnings']['unmapped_glyph_count']} 个未映射字符已用 `⟦PDF_GLYPH_U+XXXX⟧` 占位；示例：{warn_codes}。请对照 PDF 核查公式/特殊符号。\n")
            f.write("\n### 识别的章节结构树与四区映射关系\n")
            f.write("| 章节编号 | 章节完整标题 | 所在页码 | 词数 | 映射目标区域 |\n")
            f.write("| :--- | :--- | :---: | :---: | :--- |\n")
            for s in d["section_tree"]:
                f.write(f"| `{s['sec_id']}` | {s['full_heading']} | {s['pages']} | {s['word_count']} | {s['assigned_zone']} |\n")
            f.write("\n---\n\n")

    # 3. Generate Excel Inspection Report
    wb = openpyxl.Workbook()
    ws_ov = wb.active
    ws_ov.title = "1_四区靶向切片降噪总览"

    header_fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    zebra_fill = PatternFill(start_color="F9FAFC", end_color="F9FAFC", fill_type="solid")
    header_font = Font(name="微软雅黑", size=10, bold=True, color="FFFFFF")
    reg_font = Font(name="微软雅黑", size=9.5, color="262626")
    bold_font = Font(name="微软雅黑", size=9.5, bold=True, color="1F4E79")
    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
    )

    ov_headers = [
        "实验编号", "PDF文件名", "论文标题", "发表期刊与年份", "总页数",
        "全文总词数", "靶向保留词数", "剥离噪声词数", "词数降噪率(%)",
        "Zone A 词数\n(摘要与贡献)", "Zone B 词数\n(耦合与级联模型)",
        "Zone C 词数\n(指标与仿真分析)", "Zone D 词数\n(算例与局限性)"
    ]
    ws_ov.append(ov_headers)
    for c_idx in range(1, len(ov_headers) + 1):
        c = ws_ov.cell(row=1, column=c_idx)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for r_idx, d in enumerate(parsed_docs, start=2):
        st = d["word_count_stats"]
        source_file = d["file_name"]
        row_vals = [
            d["doc_id"], source_file, d["title"], publication_label(d), d["total_pages"],
            st["raw_total_words"], st["kept_targeted_words"], st["stripped_noise_words"], st["noise_reduction_ratio_pct"],
            st["zone_a_words"], st["zone_b_words"], st["zone_c_words"], st["zone_d_words"]
        ]
        ws_ov.append(row_vals)
        for c_idx in range(1, len(ov_headers) + 1):
            cell = ws_ov.cell(row=r_idx, column=c_idx)
            cell.font = bold_font if c_idx in [1, 2, 9] else reg_font
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="left" if c_idx in [3, 4] else "center", vertical="center", wrap_text=True)

    for c_idx, w in enumerate([12, 20, 48, 32, 10, 14, 14, 14, 16, 15, 16, 16, 15], start=1):
        ws_ov.column_dimensions[get_column_letter(c_idx)].width = w

    # Sheet 2: Detailed Section Tree Mapping
    ws_tree = wb.create_sheet(title="2_PDF章节结构树与四区映射明细")
    tree_headers = ["实验编号", "PDF文件名", "章节号", "识别出的完整章节标题", "PDF页码范围", "章节词数", "靶向分配区域 / 剥离原因"]
    ws_tree.append(tree_headers)
    for c_idx in range(1, len(tree_headers) + 1):
        c = ws_tree.cell(row=1, column=c_idx)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")

    row_cursor = 2
    for d in parsed_docs:
        source_file = d["file_name"]
        for s in d["section_tree"]:
            ws_tree.append([d["doc_id"], source_file, s["sec_id"], s["full_heading"], s["pages"], s["word_count"], s["assigned_zone"]])
            for c_idx in range(1, len(tree_headers) + 1):
                cell = ws_tree.cell(row=row_cursor, column=c_idx)
                cell.font = reg_font
                if "Stripped" in s["assigned_zone"]:
                    cell.font = Font(name="微软雅黑", size=9.5, italic=True, color="888888")
                elif row_cursor % 2 == 1:
                    cell.fill = zebra_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal="center" if c_idx in [1, 2, 3, 5, 6] else "left", vertical="center")
            row_cursor += 1

    for c_idx, w in enumerate([12, 14, 12, 48, 14, 12, 38], start=1):
        ws_tree.column_dimensions[get_column_letter(c_idx)].width = w

    excel_path = os.path.join(out_dir, "Step1_PDF章节树解析与四区靶向切片实验报告.xlsx")
    wb.save(excel_path)

    # 4. Generate Word Inspection Report (.docx) for rich preview
    doc = Document()
    for section in doc.sections:
        section.page_width = Cm(21.0)
        section.page_height = Cm(29.7)
        section.top_margin = Cm(2.3)
        section.bottom_margin = Cm(2.3)
        section.left_margin = Cm(2.4)
        section.right_margin = Cm(2.4)

    p_t = doc.add_paragraph()
    p_t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_t = p_t.add_run("第2章 Step 1 实验报告：学术 PDF 章节结构树解析与四区靶向切片核验")
    r_t.font.name = "Times New Roman"
    r_t._element.rPr.rFonts.set(qn('w:eastAsia'), "微软雅黑")
    r_t.font.size = Pt(15.5)
    r_t.bold = True
    r_t.font.color.rgb = RGBColor(20, 54, 93)

    p_sub = doc.add_paragraph()
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p_sub.paragraph_format.space_after = Pt(10)
    r_sub = p_sub.add_run(f"实验对象：当前输入语料中的 {len(parsed_docs)} 篇全文 PDF")
    r_sub.font.name = "Times New Roman"
    r_sub._element.rPr.rFonts.set(qn('w:eastAsia'), "微软雅黑")
    r_sub.font.size = Pt(10.5)
    r_sub.bold = True
    r_sub.font.color.rgb = RGBColor(89, 89, 89)

    # Add summary table in Word
    t_sum = doc.add_table(rows=len(parsed_docs) + 1, cols=7)
    t_sum.alignment = WD_TABLE_ALIGNMENT.CENTER
    sum_headers = ["样本编号与文件名", "期刊与年份", "页数", "全文总词数", "靶向保留词数", "剥离干扰词数", "词数降噪率"]
    for i, h in enumerate(sum_headers):
        c = t_sum.rows[0].cells[i]
        tcPr = c._tc.get_or_add_tcPr()
        tcPr.append(parse_xml(f'<w:shd {nsdecls("w")} w:fill="1F4E79"/>'))
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(h)
        r.font.name = "Times New Roman"
        r._element.rPr.rFonts.set(qn('w:eastAsia'), "微软雅黑")
        r.font.size = Pt(9.5)
        r.bold = True
        r.font.color.rgb = RGBColor(255, 255, 255)

    for idx, d in enumerate(parsed_docs, start=1):
        st = d["word_count_stats"]
        source_file = f"{d['doc_id']} | {d['file_name']}"
        vals = [
            source_file, publication_label(d), str(d["total_pages"]),
            f"{st['raw_total_words']:,}", f"{st['kept_targeted_words']:,}",
            f"{st['stripped_noise_words']:,}", f"{st['noise_reduction_ratio_pct']}%"
        ]
        for c_i, v in enumerate(vals):
            cell = t_sum.rows[idx].cells[c_i]
            p = cell.paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            r = p.add_run(v)
            r.font.name = "Times New Roman"
            r._element.rPr.rFonts.set(qn('w:eastAsia'), "宋体")
            r.font.size = Pt(9.5)
            if c_i in [0, 6]:
                r.bold = True

    # Add per-document detailed section breakdown and Zone excerpts
    for d in parsed_docs:
        st = d["word_count_stats"]
        p_h = doc.add_paragraph()
        p_h.paragraph_format.space_before = Pt(14)
        p_h.paragraph_format.space_after = Pt(6)
        r_h = p_h.add_run(f"■ {d['doc_id']}：{d['title']} ({publication_label(d)})")
        r_h.font.name = "Times New Roman"
        r_h._element.rPr.rFonts.set(qn('w:eastAsia'), "微软雅黑")
        r_h.font.size = Pt(12)
        r_h.bold = True
        r_h.font.color.rgb = RGBColor(31, 78, 121)

        p_info = doc.add_paragraph()
        p_info.paragraph_format.space_after = Pt(4)
        r_info = p_info.add_run(
            f"• 四区词数分布：Zone A (摘要与核心贡献) = {st['zone_a_words']} 词 | "
            f"Zone B (耦合与级联机理) = {st['zone_b_words']} 词 | "
            f"Zone C (指标与仿真结果) = {st['zone_c_words']} 词 | "
            f"Zone D (算例背景、讨论与局限) = {st['zone_d_words']} 词。\n"
            f"• 自动剥离噪声项：" + "；".join(f"{x['heading']} ({x['word_count']}词)" for x in d["stripped_sections_detail"])
        )
        r_info.font.name = "Times New Roman"
        r_info._element.rPr.rFonts.set(qn('w:eastAsia'), "宋体")
        r_info.font.size = Pt(9.5)

        # Show key excerpts from Zone A, B, C, D to prove accurate two-column reconstruction & page anchoring
        zones_preview = [
            ("Zone A 切片采样（元数据、摘要与导言末段核心贡献）", d["targeted_zones"]["Zone_A_Meta_Abstract_Contribution"][:650] + " ..."),
            ("Zone B 切片采样（水-电耦合机理与级联模型章节，带页码锚点）", d["targeted_zones"]["Zone_B_Coupling_And_Cascading_Model"][:750] + " ..."),
            ("Zone C 切片采样（级联功能损失指标与仿真结果分析章节）", d["targeted_zones"]["Zone_C_Metrics_And_Simulation_Control"][:650] + " ..."),
            ("Zone D 切片采样（算例描述、讨论与文末局限性展望章节）", d["targeted_zones"]["Zone_D_Case_Social_And_Limitations"][-850:])
        ]
        for z_title, z_sample in zones_preview:
            p_z = doc.add_paragraph()
            p_z.paragraph_format.space_before = Pt(4)
            p_z.paragraph_format.space_after = Pt(2)
            rz1 = p_z.add_run(f"【{z_title}】：\n")
            rz1.font.name = "Times New Roman"
            rz1._element.rPr.rFonts.set(qn('w:eastAsia'), "微软雅黑")
            rz1.font.size = Pt(9.5)
            rz1.bold = True
            rz1.font.color.rgb = RGBColor(47, 85, 151)

            rz2 = p_z.add_run(z_sample.replace("\n", " "))
            rz2.font.name = "Times New Roman"
            rz2._element.rPr.rFonts.set(qn('w:eastAsia'), "宋体")
            rz2.font.size = Pt(9.0)
            rz2.font.color.rgb = RGBColor(64, 64, 64)

    docx_path = os.path.join(out_dir, "Step1_PDF章节树解析与四区靶向切片实验报告.docx")
    doc.save(docx_path)
    print("Saved Step 1 outputs to:", out_dir)

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_dir = os.path.dirname(script_dir)
    default_input_dir = os.path.join(project_dir, "01_文献库")
    default_out_dir = os.path.join(script_dir, "01_Zones")

    parser = argparse.ArgumentParser(
        description="Parse and clean academic PDFs, build a section tree, and create Zone A–D targeted slices."
    )
    parser.add_argument("--input-dir", default=default_input_dir, help="Directory containing source PDF files")
    parser.add_argument("--out-dir", default=default_out_dir, help="Directory for Step 1 outputs")
    parser.add_argument("--batch-id", default="B001", help="Batch identifier used in stable document IDs")
    parser.add_argument("--files", nargs="*", help="Optional PDF filenames in the intended processing order")
    args = parser.parse_args()

    if not os.path.isdir(args.input_dir):
        raise SystemExit(f"Input directory does not exist: {args.input_dir}")
    if args.files:
        pdf_files = args.files
        invalid = [f for f in pdf_files if not f.lower().endswith(".pdf") or not os.path.isfile(os.path.join(args.input_dir, f))]
        if invalid:
            raise SystemExit(f"Missing or invalid PDF filename(s): {invalid}")
    else:
        pdf_files = sorted(
            (f for f in os.listdir(args.input_dir) if f.lower().endswith(".pdf")),
            key=str.casefold
        )
    if not pdf_files:
        raise SystemExit(f"No PDF files found in input directory: {args.input_dir}")

    parsed_docs = []
    for idx, fname in enumerate(pdf_files, start=1):
        fpath = os.path.join(args.input_dir, fname)
        doc_id = f"{args.batch_id}-PDF-{idx:02d}"
        res = parse_pdf_structure(fpath, doc_id)
        res["batch_id"] = args.batch_id
        res["batch_position"] = idx
        res["source_pdf_path"] = os.path.relpath(fpath, project_dir)
        parsed_docs.append(res)
        st = res["word_count_stats"]
        print(f"[{doc_id}] {fname[:45]}... | Pages: {res['total_pages']} | Raw: {st['raw_total_words']}w -> Kept: {st['kept_targeted_words']}w (Stripped: {st['stripped_noise_words']}w, -{st['noise_reduction_ratio_pct']}%)")

    generate_outputs(parsed_docs, args.out_dir)

if __name__ == "__main__":
    main()
