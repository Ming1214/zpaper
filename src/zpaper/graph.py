"""
Literature relation graph: compute and query paper-to-paper relationships.
Uses keyword overlap, tag overlap, and year proximity — no external embeddings needed.
"""
import re
import json
import math
from typing import Optional
from zpaper import library as lib


# ---------- Tokenization ----------

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "with", "and",
    "or", "but", "is", "are", "was", "were", "be", "been", "being", "have",
    "has", "had", "do", "does", "did", "will", "would", "could", "should",
    "may", "might", "from", "by", "as", "it", "its", "this", "that", "we",
    "our", "their", "they", "using", "based", "via", "show", "shows",
    "propose", "proposed", "present", "presented", "paper", "work", "model",
    "method", "approach", "task", "result", "results", "performance",
    "training", "trained", "learning", "learned", "new", "novel",
}


def _tokenize(text: str) -> set:
    if not text:
        return set()
    tokens = re.findall(r"[a-z]{3,}", text.lower())
    return {t for t in tokens if t not in _STOPWORDS}


def _tf_idf_like_score(tokens_a: set, tokens_b: set, corpus_size: int, df: dict) -> float:
    """
    Simple TF-IDF-like overlap score between two token sets.
    Rare terms (low df) contribute more to the score.
    """
    if not tokens_a or not tokens_b:
        return 0.0
    shared = tokens_a & tokens_b
    if not shared:
        return 0.0
    score = 0.0
    for t in shared:
        idf = math.log((corpus_size + 1) / (df.get(t, 0) + 1))
        score += idf
    # Normalize by the smaller set size so short abstracts aren't penalized
    return score / math.sqrt(min(len(tokens_a), len(tokens_b)))


# ---------- Core similarity ----------

def compute_similarity(paper_a: dict, paper_b: dict, df: dict, corpus_size: int) -> float:
    """Return a similarity score [0, ∞) between two papers. Higher = more related."""
    if paper_a["id"] == paper_b["id"]:
        return 0.0

    score = 0.0

    # 1. Keyword field overlap (explicit, high weight)
    kw_a = _tokenize(paper_a.get("keywords") or "")
    kw_b = _tokenize(paper_b.get("keywords") or "")
    if kw_a and kw_b:
        shared_kw = kw_a & kw_b
        if shared_kw:
            score += len(shared_kw) * 3.0

    # 2. Abstract TF-IDF overlap
    abs_a = _tokenize(paper_a.get("abstract") or "")
    abs_b = _tokenize(paper_b.get("abstract") or "")
    score += _tf_idf_like_score(abs_a, abs_b, corpus_size, df) * 2.0

    # 3. Title token overlap
    title_a = _tokenize(paper_a.get("title") or "")
    title_b = _tokenize(paper_b.get("title") or "")
    score += _tf_idf_like_score(title_a, title_b, corpus_size, df) * 1.5

    # 4. Tag overlap (user-defined, very high signal)
    tags_a = set(json.loads(paper_a.get("tags") or "[]"))
    tags_b = set(json.loads(paper_b.get("tags") or "[]"))
    if tags_a and tags_b:
        score += len(tags_a & tags_b) * 4.0

    return score


def _build_df(papers: list) -> dict:
    """Build document frequency dict from all papers' text fields."""
    df = {}
    for p in papers:
        tokens = (
            _tokenize(p.get("abstract") or "")
            | _tokenize(p.get("title") or "")
            | _tokenize(p.get("keywords") or "")
        )
        for t in tokens:
            df[t] = df.get(t, 0) + 1
    return df


# ---------- Public API ----------

def find_related(paper_id: str, top_k: int = 5) -> list:
    """
    Return top_k most related papers to paper_id.
    Each result: {"paper": {...}, "score": float, "reasons": [...]}
    """
    conn = lib.connect()
    all_papers = [dict(r) for r in conn.execute("SELECT * FROM papers").fetchall()]
    conn.close()

    target = next((p for p in all_papers if p["id"] == paper_id), None)
    if target is None:
        return []

    if len(all_papers) < 2:
        return []

    df = _build_df(all_papers)
    corpus_size = len(all_papers)

    scored = []
    for p in all_papers:
        if p["id"] == paper_id:
            continue
        s = compute_similarity(target, p, df, corpus_size)
        if s > 0:
            reasons = _explain_similarity(target, p)
            scored.append({"paper": p, "score": s, "reasons": reasons})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _explain_similarity(a: dict, b: dict) -> list:
    """Return human-readable reasons for similarity."""
    reasons = []

    kw_a = _tokenize(a.get("keywords") or "")
    kw_b = _tokenize(b.get("keywords") or "")
    shared_kw = kw_a & kw_b
    if shared_kw:
        sample = sorted(shared_kw)[:4]
        reasons.append(f"Shared keywords: {', '.join(sample)}")

    tags_a = set(json.loads(a.get("tags") or "[]"))
    tags_b = set(json.loads(b.get("tags") or "[]"))
    shared_tags = tags_a & tags_b
    if shared_tags:
        reasons.append(f"Shared tags: {', '.join(sorted(shared_tags))}")

    title_a = _tokenize(a.get("title") or "")
    title_b = _tokenize(b.get("title") or "")
    shared_title = title_a & title_b
    if shared_title:
        sample = sorted(shared_title)[:3]
        reasons.append(f"Title overlap: {', '.join(sample)}")

    if not reasons:
        abs_a = _tokenize(a.get("abstract") or "")
        abs_b = _tokenize(b.get("abstract") or "")
        shared_abs = abs_a & abs_b
        if shared_abs:
            sample = sorted(shared_abs)[:4]
            reasons.append(f"Abstract overlap: {', '.join(sample)}")

    return reasons


def topic_cluster(query: str, top_k: int = 10) -> list:
    """
    Return papers most relevant to a free-text topic query.
    Scores each paper against the query tokens.
    """
    conn = lib.connect()
    all_papers = [dict(r) for r in conn.execute("SELECT * FROM papers").fetchall()]
    conn.close()

    if not all_papers:
        return []

    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    df = _build_df(all_papers)
    corpus_size = len(all_papers)

    scored = []
    query_lower = query.lower()
    for p in all_papers:
        score = 0.0

        # Title token overlap (high weight)
        title_tokens = _tokenize(p.get("title") or "")
        score += _tf_idf_like_score(query_tokens, title_tokens, corpus_size, df) * 3.0

        # Direct substring match in title (catches "transformer" inside "Transformers")
        title_lower = (p.get("title") or "").lower()
        for qt in query_lower.split():
            if len(qt) >= 4 and qt in title_lower:
                score += 4.0

        # Abstract overlap
        abs_tokens = _tokenize(p.get("abstract") or "")
        score += _tf_idf_like_score(query_tokens, abs_tokens, corpus_size, df) * 1.5

        # Keyword field
        kw_tokens = _tokenize(p.get("keywords") or "")
        score += _tf_idf_like_score(query_tokens, kw_tokens, corpus_size, df) * 2.0

        # Tag match
        tags = set(json.loads(p.get("tags") or "[]"))
        for tag in tags:
            if tag.lower() in query_lower or query_lower in tag.lower():
                score += 3.0

        if score > 0:
            scored.append({"paper": p, "score": score})

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def build_graph_summary(topic: Optional[str] = None) -> str:
    """
    Return a text description of the library graph for a given topic,
    suitable for passing to Claude for survey generation.
    """
    conn = lib.connect()
    all_papers = [dict(r) for r in conn.execute(
        "SELECT * FROM papers ORDER BY year ASC, import_date ASC"
    ).fetchall()]
    conn.close()

    if not all_papers:
        return "Library is empty."

    if topic:
        clusters = topic_cluster(topic, top_k=20)
        relevant = [c["paper"] for c in clusters]
        if not relevant:
            # fall back to all papers
            relevant = all_papers
        header = f"Papers related to topic: '{topic}' ({len(relevant)} found)\n"
    else:
        relevant = all_papers
        header = f"All papers in library ({len(relevant)} total)\n"

    df = _build_df(relevant)
    corpus_size = len(relevant)

    lines = [header, "=" * 60]

    for p in relevant:
        pid = p["id"]
        title = p.get("title") or "Untitled"
        authors = p.get("authors") or "Unknown"
        year = p.get("year") or "?"
        abstract = (p.get("abstract") or "")[:300]
        keywords = p.get("keywords") or ""
        tags = json.loads(p.get("tags") or "[]")

        lines.append(f"\n[{pid}] {title} ({year})")
        lines.append(f"Authors: {authors}")
        if keywords:
            lines.append(f"Keywords: {keywords}")
        if tags:
            lines.append(f"Tags: {', '.join(tags)}")
        if abstract:
            lines.append(f"Abstract: {abstract}{'...' if len(p.get('abstract','')) > 300 else ''}")

    # Add connection hints
    lines.append("\n" + "=" * 60)
    lines.append("CONNECTION HINTS (auto-detected):")
    if len(relevant) >= 2:
        for i, p in enumerate(relevant[:8]):
            related = find_related(p["id"], top_k=2)
            if related:
                top = related[0]
                r_title = top["paper"].get("title", top["paper"]["id"])
                reasons = "; ".join(top["reasons"][:2])
                lines.append(f"  {p.get('title','?')!r} ↔ {r_title!r} ({reasons})")
    else:
        lines.append("  (Need at least 2 papers to show connections)")

    return "\n".join(lines)
