"""
Network search and PDF download: arXiv search and download.
"""
import re
import os
import time
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None


def search_arxiv(query: str, max_results: int = 10) -> list:
    """Search arXiv and return a list of paper metadata dicts."""
    if requests is None:
        return []

    url = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "max_results": max_results,
        "sortBy": "relevance",
        "sortOrder": "descending",
    }

    for attempt in range(3):
        try:
            resp = requests.get(url, params=params, timeout=20)
            if resp.status_code == 429:
                wait = 5 * (attempt + 1)
                time.sleep(wait)
                continue
            resp.raise_for_status()
            return _parse_arxiv_feed(resp.text)
        except Exception as e:
            return [{"error": str(e)}]
    return [{"error": "arXiv API rate limit exceeded, please retry in a moment"}]


def _parse_arxiv_feed(xml_text: str) -> list:
    entries = re.split(r"<entry>", xml_text)[1:]
    results = []

    for entry in entries:
        paper = {}

        id_m = re.search(r"<id>.*?/abs/([^<\s]+)</id>", entry)
        if id_m:
            paper["arxiv_id"] = id_m.group(1).split("v")[0]
            paper["source_url"] = f"https://arxiv.org/abs/{paper['arxiv_id']}"
            paper["pdf_url"] = f"https://arxiv.org/pdf/{paper['arxiv_id']}.pdf"

        title_m = re.search(r"<title>(.*?)</title>", entry, re.DOTALL)
        if title_m:
            paper["title"] = re.sub(r"\s+", " ", title_m.group(1).strip())

        authors = re.findall(r"<name>(.*?)</name>", entry)
        if authors:
            paper["authors"] = ", ".join(authors)

        summary_m = re.search(r"<summary>(.*?)</summary>", entry, re.DOTALL)
        if summary_m:
            abstract = re.sub(r"\s+", " ", summary_m.group(1).strip())
            paper["abstract"] = abstract[:500] + "..." if len(abstract) > 500 else abstract

        published_m = re.search(r"<published>(\d{4})", entry)
        if published_m:
            paper["year"] = int(published_m.group(1))

        cats = re.findall(r'<category term="([^"]+)"', entry)
        if cats:
            paper["keywords"] = ", ".join(cats[:5])

        if paper.get("arxiv_id"):
            results.append(paper)

    return results


def download_arxiv_pdf(arxiv_id: str, dest_dir: Path, title: Optional[str] = None) -> Optional[str]:
    """Download a PDF from arXiv. Returns local file path or None on failure."""
    if requests is None:
        return None

    clean_id = arxiv_id.split("v")[0].strip()
    pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"

    # Build a safe filename
    if title:
        safe = re.sub(r'[^\w\s-]', '', title)
        safe = re.sub(r'\s+', '_', safe.strip())[:80]
        filename = f"{safe}_{clean_id}.pdf"
    else:
        filename = f"{clean_id}.pdf"

    dest_path = dest_dir / filename

    if dest_path.exists():
        return str(dest_path)

    try:
        headers = {"User-Agent": "ScholarMind/1.0 (personal research tool)"}
        resp = requests.get(pdf_url, headers=headers, timeout=60, stream=True)
        resp.raise_for_status()

        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and "octet-stream" not in content_type:
            # arXiv sometimes returns HTML for missing papers
            return None

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        # Basic sanity check: PDF starts with %PDF
        with open(dest_path, "rb") as f:
            header = f.read(4)
        if header != b"%PDF":
            os.remove(dest_path)
            return None

        return str(dest_path)

    except Exception:
        if dest_path.exists():
            os.remove(dest_path)
        return None


def format_search_results(results: list, start_index: int = 1) -> str:
    """Format search results for display in Claude Code."""
    if not results:
        return "No results found."

    if results and "error" in results[0]:
        return f"Search error: {results[0]['error']}"

    lines = []
    for i, p in enumerate(results, start=start_index):
        arxiv_id = p.get("arxiv_id", "?")
        title = p.get("title", "Untitled")
        authors = p.get("authors", "Unknown")
        year = p.get("year", "?")
        abstract = p.get("abstract", "")

        # Show first two authors
        author_list = [a.strip() for a in authors.split(",")]
        if len(author_list) > 2:
            author_display = f"{author_list[0]}, {author_list[1]}, et al."
        else:
            author_display = authors

        lines.append(f"[{i}] **{title}**")
        lines.append(f"    {author_display} ({year}) · arXiv:{arxiv_id}")
        if abstract:
            lines.append(f"    {abstract[:200]}...")
        lines.append("")

    return "\n".join(lines)
