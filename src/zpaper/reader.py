"""
PDF text extraction and reading mode utilities.
Extracts structured text from PDFs for Claude to analyze.
"""
import re
import sys
from pathlib import Path
from typing import Optional

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None


def extract_full_text(pdf_path: str, max_chars: int = 80000) -> dict:
    """
    Extract full text from a PDF, returning structured sections.
    max_chars limits total text to avoid context overflow.
    """
    if fitz is None:
        return {"error": "pymupdf not installed", "text": "", "pages": 0}

    try:
        doc = fitz.open(pdf_path)
        pages = len(doc)
        all_text = []

        for i, page in enumerate(doc):
            text = page.get_text()
            # Clean up excessive whitespace while preserving paragraph breaks
            text = re.sub(r"\n{3,}", "\n\n", text)
            text = re.sub(r"[ \t]+", " ", text)
            all_text.append(f"[Page {i+1}]\n{text.strip()}")

        doc.close()
        full_text = "\n\n".join(all_text)

        truncated = False
        if len(full_text) > max_chars:
            full_text = full_text[:max_chars]
            # Don't cut mid-word
            full_text = full_text[:full_text.rfind("\n")]
            truncated = True

        return {
            "text": full_text,
            "pages": pages,
            "chars": len(full_text),
            "truncated": truncated,
        }
    except Exception as e:
        return {"error": str(e), "text": "", "pages": 0}


CHUNK_SIZE = 8000


def _slice_sections(text: str, positions: list, skip_refs: bool = True) -> list:
    """Given sorted (pos, title) pairs, slice text into section dicts.

    Each section dict contains the full text plus chunk metadata so callers
    can serve one chunk at a time and indicate to Claude whether more exists.
    """
    sections = []
    for i, (pos, title) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        if skip_refs and re.match(r"References|Bibliography", title, re.IGNORECASE):
            continue
        full_text = text[pos:end].strip()
        total_chunks = max(1, (len(full_text) + CHUNK_SIZE - 1) // CHUNK_SIZE)
        sections.append({
            "title": title,
            "text": full_text,
            "total_chunks": total_chunks,
        })
    return sections


def get_section_chunk(section: dict, chunk_idx: int) -> dict:
    """Return a single chunk from a section dict produced by _slice_sections.

    Returns a dict with:
      - text: the chunk text
      - chunk_idx: 0-based index of this chunk
      - total_chunks: total number of chunks in the section
      - has_more: True if more chunks follow
    """
    full_text = section["text"]
    total_chunks = section["total_chunks"]
    chunk_idx = max(0, min(chunk_idx, total_chunks - 1))
    start = chunk_idx * CHUNK_SIZE
    end = start + CHUNK_SIZE
    return {
        "text": full_text[start:end],
        "chunk_idx": chunk_idx,
        "total_chunks": total_chunks,
        "has_more": chunk_idx + 1 < total_chunks,
    }


def _detect_whitelist(text: str) -> list:
    """
    Strategy A — whitelist: match known academic section names.
    Returns sorted list of (pos, title) pairs.
    """
    section_patterns = [
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Abstract|ABSTRACT)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Introduction|INTRODUCTION)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Related Work|RELATED WORK|Background|BACKGROUND)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Method|METHOD|Methodology|METHODOLOGY|Approach|APPROACH|Model|MODEL)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Experiment|EXPERIMENT|Experiments|EXPERIMENTS|Evaluation|EVALUATION)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Results|RESULTS|Discussion|DISCUSSION)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Conclusion|CONCLUSION|Conclusions|CONCLUSIONS|Summary|SUMMARY)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Limitation|LIMITATION|Limitations|LIMITATIONS)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Ablation|ABLATION|Ablation Study|ABLATION STUDY)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>Future Work|FUTURE WORK)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(?P<title>References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*$",
    ]
    positions = []
    for pattern in section_patterns:
        for m in re.finditer(pattern, text):
            positions.append((m.start(), m.group("title").strip()))
    positions.sort(key=lambda x: x[0])
    return positions


def _detect_structural(text: str) -> list:
    """
    Strategy B — structural: detect lines that look like section headers
    without relying on a fixed word list.

    A line is treated as a header if it satisfies ALL of:
      - short (≤ 60 chars) and non-empty
      - does not end with sentence-terminating punctuation
      - no lowercase run longer than 3 chars in the first 10 chars
        (rules out normal prose that happens to start with a capital)
      - AND at least one of:
          * starts with a digit prefix  (e.g. "1.", "2 ", "3.1")
          * is entirely uppercase       (e.g. "INTRODUCTION")
          * is 1–4 words, each word capitalized, no stopwords mid-line
            (e.g. "Related Work", "Future Directions")
    """
    STOPWORDS = {"a", "an", "the", "of", "in", "on", "at", "to", "and", "or",
                 "for", "with", "by", "from", "is", "are", "was", "were"}

    positions = []
    lines = text.split("\n")
    line_offsets: list[int] = []
    offset = 0
    for line in lines:
        line_offsets.append(offset)
        offset += len(line) + 1

    for idx, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or len(stripped) > 60:
            continue
        if stripped[-1] in ".,:;?!":
            continue
        # Reject lines with a lowercase run in the first 10 chars (normal prose)
        if re.search(r"[a-z]{4,}", stripped[:10]):
            continue

        # Must contain at least one real word (≥3 alphabetic chars)
        real_words = [w for w in stripped.split() if re.match(r"[A-Za-z]{3,}", w)]
        if not real_words:
            continue

        has_number_prefix = bool(re.match(r"^\d+[\.\s]", stripped))
        is_all_caps = stripped.replace(" ", "").isupper() and len(stripped) > 2

        words = stripped.split()
        alpha_words = [w for w in words if w.isalpha()]
        is_title_words = (
            2 <= len(real_words) <= 5  # at least 2 real words to avoid single-token noise
            and len(alpha_words) >= 1
            and all(
                w[0].isupper() or w.lower() in STOPWORDS
                for w in words
                if w.isalpha()
            )
            and words[0][0].isupper()
        )

        if has_number_prefix or is_all_caps or is_title_words:
            title = re.sub(r"^\d+[\.\s]+", "", stripped).strip()
            # Skip if after stripping the number prefix there's nothing real left
            if title and re.search(r"[A-Za-z]{3,}", title):
                positions.append((line_offsets[idx], title))

    positions.sort(key=lambda x: x[0])
    return positions


def extract_sections(pdf_path: str) -> dict:
    """
    Extract text split into logical sections for deep read mode.
    Returns two candidate section lists (whitelist + structural) for the LLM
    to reconcile into the final structure.
    """
    result = extract_full_text(pdf_path, max_chars=100000)
    if result.get("error"):
        return result

    text = result["text"]
    meta = {"pages": result["pages"], "truncated": result["truncated"]}

    whitelist_pos = _detect_whitelist(text)
    structural_pos = _detect_structural(text)

    whitelist_sections = _slice_sections(text, whitelist_pos) if len(whitelist_pos) >= 2 else []
    structural_sections = _slice_sections(text, structural_pos) if len(structural_pos) >= 2 else []

    # `sections` keeps backward-compat: prefer whitelist, fall back to structural, then full text
    full_text_fallback = text.strip()
    fallback_chunks = max(1, (len(full_text_fallback) + CHUNK_SIZE - 1) // CHUNK_SIZE)
    primary = whitelist_sections or structural_sections or [
        {"title": "Full Text", "text": full_text_fallback, "total_chunks": fallback_chunks}
    ]

    return {
        "sections": primary,
        "sections_whitelist": whitelist_sections,
        "sections_structural": structural_sections,
        **meta,
    }


def get_paper_text_for_summary(pdf_path: str) -> str:
    """Return full paper text formatted for summarization prompt."""
    result = extract_full_text(pdf_path, max_chars=60000)
    if result.get("error"):
        return f"ERROR: {result['error']}"

    header = f"[{result['pages']} pages"
    if result["truncated"]:
        header += ", truncated to first ~60k chars"
    header += "]"

    return f"{header}\n\n{result['text']}"


def get_section_text(pdf_path: str, section_index: int) -> Optional[dict]:
    """Get text for a specific section by index."""
    result = extract_sections(pdf_path)
    sections = result.get("sections", [])
    if section_index < 0 or section_index >= len(sections):
        return None
    return sections[section_index]


def list_sections(pdf_path: str) -> list:
    """Return list of section titles."""
    result = extract_sections(pdf_path)
    return [s["title"] for s in result.get("sections", [])]


def _fuzzy_match_score(query_tokens: list[str], window_tokens: list[str]) -> float:
    """
    Compute what fraction of query tokens appear in the window (bag-of-words).
    Returns a score in [0, 1].
    """
    if not query_tokens:
        return 0.0
    window_bag = {}
    for t in window_tokens:
        window_bag[t] = window_bag.get(t, 0) + 1
    hits = 0
    for t in query_tokens:
        if window_bag.get(t, 0) > 0:
            hits += 1
            window_bag[t] -= 1
    return hits / len(query_tokens)


def search_text(pdf_path: str, query: str, context_lines: int = 8,
                fuzzy_threshold: float = 0.75) -> list[dict]:
    """
    Search for a keyword or phrase in the PDF text.
    First tries exact substring match; falls back to token-level fuzzy matching
    so that PDF line-break artifacts and minor OCR differences don't block hits.
    Each result includes the matching line(s) and surrounding context.
    """
    result = extract_full_text(pdf_path, max_chars=200000)
    if result.get("error"):
        return []

    lines = result["text"].split("\n")
    query_lower = query.lower()
    query_tokens = re.findall(r"[a-z0-9]+", query_lower)
    # Sliding window spans enough lines to contain a multi-line phrase
    window_lines = max(1, (len(query_tokens) // 6) + 2)

    seen_centers: list[int] = []
    matches: list[dict] = []

    def _add_match(center_idx: int, score: float) -> None:
        if any(abs(center_idx - c) < context_lines for c in seen_centers):
            return
        seen_centers.append(center_idx)
        start = max(0, center_idx - context_lines)
        end = min(len(lines), center_idx + context_lines + 1)
        matches.append({
            "line_number": center_idx + 1,
            "matched_line": lines[center_idx].strip(),
            "context": "\n".join(lines[start:end]),
            "score": round(score, 2),
        })

    # Pass 1: exact substring match (score = 1.0)
    for idx, line in enumerate(lines):
        if query_lower in line.lower():
            _add_match(idx, 1.0)

    # Pass 2: fuzzy token match over a sliding multi-line window
    if not matches:
        for idx in range(len(lines) - window_lines + 1):
            window_text = " ".join(lines[idx: idx + window_lines]).lower()
            window_tokens = re.findall(r"[a-z0-9]+", window_text)
            score = _fuzzy_match_score(query_tokens, window_tokens)
            if score >= fuzzy_threshold:
                center = idx + window_lines // 2
                _add_match(center, score)

    matches.sort(key=lambda m: -m["score"])
    return matches
