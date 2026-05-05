"""
Core library: SQLite operations and PDF metadata extraction.
"""
import sqlite3
import os
import re
import json
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

try:
    import fitz  # pymupdf
except ImportError:
    fitz = None

try:
    import requests
except ImportError:
    requests = None

DEFAULT_LIB_DIR = Path.home() / ".scholarmind"
DB_NAME = "library.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS papers (
    id          TEXT PRIMARY KEY,
    title       TEXT,
    authors     TEXT,
    year        INTEGER,
    abstract    TEXT,
    keywords    TEXT,
    doi         TEXT,
    arxiv_id    TEXT,
    file_path   TEXT,
    source_url  TEXT,
    tags        TEXT DEFAULT '[]',
    import_date TEXT,
    read_status TEXT DEFAULT 'unread'
);

CREATE VIRTUAL TABLE IF NOT EXISTS papers_fts USING fts5(
    id UNINDEXED,
    title,
    authors,
    abstract,
    keywords,
    content='papers',
    content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS papers_ai AFTER INSERT ON papers BEGIN
    INSERT INTO papers_fts(rowid, id, title, authors, abstract, keywords)
    VALUES (new.rowid, new.id, new.title, new.authors, new.abstract, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS papers_au AFTER UPDATE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, id, title, authors, abstract, keywords)
    VALUES ('delete', old.rowid, old.id, old.title, old.authors, old.abstract, old.keywords);
    INSERT INTO papers_fts(rowid, id, title, authors, abstract, keywords)
    VALUES (new.rowid, new.id, new.title, new.authors, new.abstract, new.keywords);
END;

CREATE TRIGGER IF NOT EXISTS papers_ad AFTER DELETE ON papers BEGIN
    INSERT INTO papers_fts(papers_fts, rowid, id, title, authors, abstract, keywords)
    VALUES ('delete', old.rowid, old.id, old.title, old.authors, old.abstract, old.keywords);
END;

CREATE TABLE IF NOT EXISTS notes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    paper_id    TEXT NOT NULL,
    content     TEXT NOT NULL,
    note_type   TEXT DEFAULT 'manual',
    created_at  TEXT,
    FOREIGN KEY (paper_id) REFERENCES papers(id)
);

CREATE TABLE IF NOT EXISTS config (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_lib_dir() -> Path:
    conn = _get_config_conn()
    row = conn.execute("SELECT value FROM config WHERE key='lib_dir'").fetchone()
    conn.close()
    if row:
        return Path(row[0])
    return DEFAULT_LIB_DIR


def set_lib_dir(path: str):
    p = Path(path).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    conn = _get_config_conn()
    conn.execute("INSERT OR REPLACE INTO config(key, value) VALUES('lib_dir', ?)", (str(p),))
    conn.commit()
    conn.close()


def _get_config_conn():
    config_db = DEFAULT_LIB_DIR / "config.db"
    DEFAULT_LIB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(config_db)
    conn.execute("CREATE TABLE IF NOT EXISTS config (key TEXT PRIMARY KEY, value TEXT)")
    conn.commit()
    return conn


def get_db_path() -> Path:
    return get_lib_dir() / DB_NAME


def get_pdf_dir() -> Path:
    d = get_lib_dir() / "pdfs"
    d.mkdir(parents=True, exist_ok=True)
    return d


def connect() -> sqlite3.Connection:
    db = get_db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def _paper_id(file_path: Optional[str] = None, arxiv_id: Optional[str] = None, title: Optional[str] = None) -> str:
    if arxiv_id:
        return f"arxiv:{arxiv_id}"
    if file_path:
        h = hashlib.md5(Path(file_path).read_bytes()).hexdigest()[:12]
        return f"local:{h}"
    if title:
        h = hashlib.md5(title.encode()).hexdigest()[:12]
        return f"manual:{h}"
    return f"unknown:{hashlib.md5(os.urandom(8)).hexdigest()[:12]}"


def extract_pdf_metadata(pdf_path: str) -> dict:
    """Extract metadata from a PDF file using pymupdf."""
    result = {
        "title": None,
        "authors": None,
        "year": None,
        "abstract": None,
        "keywords": None,
        "arxiv_id": None,
        "missing_fields": [],
    }

    if fitz is None:
        result["missing_fields"] = ["title", "authors", "year", "abstract", "keywords"]
        result["error"] = "pymupdf not installed"
        return result

    try:
        doc = fitz.open(pdf_path)
        meta = doc.metadata

        # Title from PDF metadata
        if meta.get("title", "").strip():
            result["title"] = meta["title"].strip()

        # Authors
        if meta.get("author", "").strip():
            result["authors"] = meta["author"].strip()

        # Try to parse year from date string like "D:20231015..."
        date_str = meta.get("creationDate", "") or meta.get("modDate", "")
        m = re.search(r"D:(\d{4})", date_str)
        if m:
            result["year"] = int(m.group(1))

        # Fall back to parsing first 2 pages of text
        if not result["title"] or not result["authors"]:
            first_pages_text = ""
            for i in range(min(2, len(doc))):
                first_pages_text += doc[i].get_text()

            # Detect arXiv ID in text
            arxiv_match = re.search(r"arXiv:(\d{4}\.\d{4,5}(?:v\d+)?)", first_pages_text, re.IGNORECASE)
            if not arxiv_match:
                arxiv_match = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})", first_pages_text, re.IGNORECASE)
            if arxiv_match:
                result["arxiv_id"] = arxiv_match.group(1).split("v")[0]

            # Try to extract abstract from text
            if not result["abstract"]:
                abs_match = re.search(
                    r"(?:Abstract|ABSTRACT)[.\s—–-]*\n?(.*?)(?:\n(?:1\s+)?Introduction|\n(?:1\s+)?INTRODUCTION|\Z)",
                    first_pages_text,
                    re.DOTALL | re.IGNORECASE,
                )
                if abs_match:
                    abstract = abs_match.group(1).strip()
                    abstract = re.sub(r"\s+", " ", abstract)
                    if 50 < len(abstract) < 3000:
                        result["abstract"] = abstract

            # If still no title, use first non-empty line as heuristic
            if not result["title"]:
                lines = [l.strip() for l in first_pages_text.split("\n") if l.strip()]
                if lines:
                    # skip lines that look like page headers/numbers
                    for line in lines[:10]:
                        if len(line) > 10 and not re.match(r"^\d+$", line):
                            result["title"] = line
                            break

        doc.close()

    except Exception as e:
        result["error"] = str(e)

    # Collect missing fields
    for field in ["title", "authors", "year", "abstract", "keywords"]:
        if not result.get(field):
            result["missing_fields"].append(field)

    return result


def fetch_arxiv_metadata(arxiv_id: str) -> dict:
    """Fetch metadata from arXiv API for a given arXiv ID."""
    if requests is None:
        return {}

    clean_id = arxiv_id.split("v")[0].strip()
    url = f"https://export.arxiv.org/api/query?id_list={clean_id}&max_results=1"
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        text = resp.text

        result = {}

        title_m = re.search(r"<title>(.*?)</title>", text, re.DOTALL)
        if title_m:
            t = title_m.group(1).strip()
            # skip the feed title
            if "arXiv" not in t:
                result["title"] = re.sub(r"\s+", " ", t)

        # All titles in order; first is feed title, second is paper title
        all_titles = re.findall(r"<title>(.*?)</title>", text, re.DOTALL)
        if len(all_titles) >= 2:
            result["title"] = re.sub(r"\s+", " ", all_titles[1].strip())

        authors = re.findall(r"<name>(.*?)</name>", text)
        if authors:
            result["authors"] = ", ".join(authors)

        summary_m = re.search(r"<summary>(.*?)</summary>", text, re.DOTALL)
        if summary_m:
            result["abstract"] = re.sub(r"\s+", " ", summary_m.group(1).strip())

        published_m = re.search(r"<published>(\d{4})", text)
        if published_m:
            result["year"] = int(published_m.group(1))

        # Extract categories as keywords
        cats = re.findall(r'<category term="([^"]+)"', text)
        if cats:
            result["keywords"] = ", ".join(cats)

        result["arxiv_id"] = clean_id
        result["source_url"] = f"https://arxiv.org/abs/{clean_id}"

        return result
    except Exception:
        return {}


def add_paper(
    file_path: Optional[str] = None,
    metadata: Optional[dict] = None,
    tags: Optional[list] = None,
) -> dict:
    """Add a paper to the library. Returns the paper record."""
    if metadata is None:
        metadata = {}

    arxiv_id = metadata.get("arxiv_id")
    pid = _paper_id(file_path=file_path, arxiv_id=arxiv_id, title=metadata.get("title"))

    conn = connect()
    existing = conn.execute("SELECT * FROM papers WHERE id=?", (pid,)).fetchone()
    if existing:
        conn.close()
        return {"status": "duplicate", "paper": dict(existing)}

    record = {
        "id": pid,
        "title": metadata.get("title"),
        "authors": metadata.get("authors"),
        "year": metadata.get("year"),
        "abstract": metadata.get("abstract"),
        "keywords": metadata.get("keywords"),
        "doi": metadata.get("doi"),
        "arxiv_id": arxiv_id,
        "file_path": str(Path(file_path).resolve()) if file_path else None,
        "source_url": metadata.get("source_url"),
        "tags": json.dumps(tags or []),
        "import_date": datetime.now().isoformat(),
        "read_status": "unread",
    }

    conn.execute(
        """INSERT INTO papers
           (id, title, authors, year, abstract, keywords, doi, arxiv_id, file_path, source_url, tags, import_date, read_status)
           VALUES (:id, :title, :authors, :year, :abstract, :keywords, :doi, :arxiv_id, :file_path, :source_url, :tags, :import_date, :read_status)""",
        record,
    )
    conn.commit()
    conn.close()

    return {"status": "added", "paper": record}


def search_papers(query: str, limit: int = 10) -> list:
    """Full-text search across title, authors, abstract, keywords."""
    conn = connect()

    # FTS search
    try:
        rows = conn.execute(
            """SELECT p.* FROM papers p
               JOIN papers_fts f ON p.rowid = f.rowid
               WHERE papers_fts MATCH ?
               ORDER BY rank LIMIT ?""",
            (query, limit),
        ).fetchall()
    except Exception:
        rows = []

    # Fallback: LIKE search on title and abstract
    if not rows:
        like = f"%{query}%"
        rows = conn.execute(
            """SELECT * FROM papers
               WHERE title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR keywords LIKE ?
               ORDER BY import_date DESC LIMIT ?""",
            (like, like, like, like, limit),
        ).fetchall()

    conn.close()
    return [dict(r) for r in rows]


def list_papers(limit: int = 20, status: Optional[str] = None) -> list:
    conn = connect()
    if status:
        rows = conn.execute(
            "SELECT * FROM papers WHERE read_status=? ORDER BY import_date DESC LIMIT ?",
            (status, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM papers ORDER BY import_date DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_paper(paper_id: str) -> Optional[dict]:
    conn = connect()
    row = conn.execute("SELECT * FROM papers WHERE id=?", (paper_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_paper(paper_id: str, fields: dict):
    conn = connect()
    set_clause = ", ".join(f"{k}=?" for k in fields)
    values = list(fields.values()) + [paper_id]
    conn.execute(f"UPDATE papers SET {set_clause} WHERE id=?", values)
    conn.commit()
    conn.close()


def delete_paper(paper_id: str) -> bool:
    conn = connect()
    cur = conn.execute("DELETE FROM papers WHERE id=?", (paper_id,))
    conn.execute("DELETE FROM notes WHERE paper_id=?", (paper_id,))
    conn.commit()
    conn.close()
    return cur.rowcount > 0


def add_note(paper_id: str, content: str, note_type: str = "manual") -> dict:
    conn = connect()
    cur = conn.execute(
        "INSERT INTO notes (paper_id, content, note_type, created_at) VALUES (?, ?, ?, ?)",
        (paper_id, content, note_type, datetime.now().isoformat()),
    )
    conn.commit()
    note_id = cur.lastrowid
    conn.close()
    return {"id": note_id, "paper_id": paper_id, "content": content}


def list_notes(paper_id: str) -> list:
    conn = connect()
    rows = conn.execute(
        "SELECT * FROM notes WHERE paper_id=? ORDER BY created_at", (paper_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def export_notes_markdown(paper_id: str) -> str:
    paper = get_paper(paper_id)
    if not paper:
        return f"Paper {paper_id} not found."

    notes = list_notes(paper_id)
    lines = [
        f"# Notes: {paper.get('title') or paper_id}",
        f"",
        f"**Authors**: {paper.get('authors') or 'Unknown'}",
        f"**Year**: {paper.get('year') or 'Unknown'}",
        f"**ID**: {paper_id}",
        f"",
        f"---",
        f"",
    ]
    if not notes:
        lines.append("_No notes yet._")
    else:
        for note in notes:
            lines.append(f"## [{note['note_type']}] {note['created_at'][:16]}")
            lines.append("")
            lines.append(note["content"])
            lines.append("")

    return "\n".join(lines)
