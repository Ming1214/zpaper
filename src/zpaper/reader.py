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


def extract_sections(pdf_path: str) -> dict:
    """
    Extract text split into logical sections (Introduction, Method, etc.)
    for use in deep read mode.
    """
    result = extract_full_text(pdf_path, max_chars=100000)
    if result.get("error"):
        return result

    text = result["text"]

    # Common section header patterns in academic papers
    section_patterns = [
        r"(?m)^(?:\d+\.?\s+)?(Abstract|ABSTRACT)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Introduction|INTRODUCTION)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Related Work|RELATED WORK|Background|BACKGROUND)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Method|METHOD|Methodology|METHODOLOGY|Approach|APPROACH|Model|MODEL)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Experiment|EXPERIMENT|Experiments|EXPERIMENTS|Evaluation|EVALUATION)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Results|RESULTS|Discussion|DISCUSSION)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Conclusion|CONCLUSION|Conclusions|CONCLUSIONS)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(Limitation|LIMITATION|Limitations|LIMITATIONS)\s*$",
        r"(?m)^(?:\d+\.?\s+)?(References|REFERENCES|Bibliography|BIBLIOGRAPHY)\s*$",
    ]

    # Find all section positions
    positions = []
    for pattern in section_patterns:
        for m in re.finditer(pattern, text):
            positions.append((m.start(), m.group(0).strip()))

    positions.sort(key=lambda x: x[0])

    if len(positions) < 2:
        # Can't detect sections — return as single chunk
        return {
            "sections": [{"title": "Full Text", "text": text}],
            "pages": result["pages"],
            "truncated": result["truncated"],
        }

    # Slice text by section boundaries
    sections = []
    for i, (pos, title) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        section_text = text[pos:end].strip()
        # Skip references section (usually just citation list)
        if re.match(r"References|Bibliography", title, re.IGNORECASE):
            continue
        sections.append({"title": title, "text": section_text[:8000]})

    return {
        "sections": sections,
        "pages": result["pages"],
        "truncated": result["truncated"],
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
