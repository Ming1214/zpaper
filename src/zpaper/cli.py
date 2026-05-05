#!/usr/bin/env python3
"""
zpaper CLI — entry point for the /paper Claude Code skill.
Usage: python3 -m zpaper.cli <subcommand> [args...]
"""
import sys
import os
import json
import argparse
from pathlib import Path
from typing import Optional

from zpaper import library as lib
from zpaper import search as srch
from zpaper import reader as rdr
from zpaper import graph as gph


def cmd_add(args):
    """Add a paper from a local path or arXiv ID / URL."""
    source = args.source

    if not source:
        print("Usage: /paper add <path/to/file.pdf | arxiv_id | arxiv_url>")
        return

    metadata = {}
    file_path = None

    # --- Case 1: arXiv ID or URL ---
    arxiv_id = None
    arxiv_match = None

    # Match patterns: 2301.12345, arxiv:2301.12345, https://arxiv.org/abs/2301.12345
    for pattern in [
        r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"(?:arxiv:|arXiv:)(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"^(\d{4}\.\d{4,5}(?:v\d+)?)$",
    ]:
        m = __import__("re").search(pattern, source, __import__("re").IGNORECASE)
        if m:
            arxiv_id = m.group(1).split("v")[0]
            break

    if arxiv_id:
        print(f"Fetching metadata from arXiv for {arxiv_id}...")
        metadata = lib.fetch_arxiv_metadata(arxiv_id)
        if not metadata:
            print(f"Could not fetch arXiv metadata for {arxiv_id}. Check the ID and your internet connection.")
            return

        print(f"Title: {metadata.get('title', 'Unknown')}")
        print(f"Authors: {metadata.get('authors', 'Unknown')}")
        print(f"Year: {metadata.get('year', 'Unknown')}")

        download = args.download if hasattr(args, "download") else True
        if download:
            print("Downloading PDF...")
            pdf_dir = lib.get_pdf_dir()
            file_path = srch.download_arxiv_pdf(arxiv_id, pdf_dir, title=metadata.get("title"))
            if file_path:
                print(f"PDF saved: {file_path}")
            else:
                print("PDF download failed (may be access-restricted). Saving metadata only.")

    # --- Case 2: local file ---
    elif Path(source).expanduser().exists():
        file_path = str(Path(source).expanduser().resolve())
        print(f"Extracting metadata from {file_path}...")
        extracted = lib.extract_pdf_metadata(file_path)

        if extracted.get("arxiv_id"):
            print(f"Detected arXiv ID: {extracted['arxiv_id']}, fetching full metadata...")
            arxiv_meta = lib.fetch_arxiv_metadata(extracted["arxiv_id"])
            if arxiv_meta:
                # Prefer arXiv metadata, fill gaps with extracted
                for k, v in extracted.items():
                    if k not in arxiv_meta or not arxiv_meta[k]:
                        arxiv_meta[k] = v
                metadata = arxiv_meta
            else:
                metadata = extracted
        else:
            metadata = extracted

        if extracted.get("missing_fields"):
            print(f"\nCould not auto-extract: {', '.join(extracted['missing_fields'])}")
            print("You can fill them in with: /paper edit <id> title='...' authors='...'")

    else:
        print(f"Not a valid arXiv ID/URL or local file path: {source}")
        print("Examples:")
        print("  /paper add 2301.12345")
        print("  /paper add https://arxiv.org/abs/2301.12345")
        print("  /paper add /path/to/paper.pdf")
        return

    # Parse tags
    tags = args.tags.split(",") if getattr(args, "tags", None) else []
    tags = [t.strip() for t in tags if t.strip()]

    result = lib.add_paper(file_path=file_path, metadata=metadata, tags=tags)

    if result["status"] == "duplicate":
        p = result["paper"]
        print(f"\nAlready in library: [{p['id']}] {p.get('title', 'Untitled')}")
    else:
        p = result["paper"]
        print(f"\nAdded: [{p['id']}] {p.get('title', 'Untitled')}")
        if p.get("year"):
            print(f"Year: {p['year']} | Authors: {p.get('authors', 'Unknown')}")


def cmd_search(args):
    """Search the local library."""
    query = " ".join(args.query)
    if not query:
        print("Usage: /paper search <keywords>")
        return

    results = lib.search_papers(query, limit=args.limit)
    if not results:
        print(f"No results for '{query}' in your library.")
        print("Tip: use /paper web-search to search the internet.")
        return

    print(f"Found {len(results)} paper(s) for '{query}':\n")
    for p in results:
        status_icon = {"unread": "○", "reading": "◑", "read": "●"}.get(p.get("read_status", ""), "○")
        print(f"{status_icon} [{p['id']}] {p.get('title', 'Untitled')}")
        authors = p.get("authors", "")
        if authors:
            author_list = [a.strip() for a in authors.split(",")]
            if len(author_list) > 2:
                authors = f"{author_list[0]}, {author_list[1]}, et al."
        print(f"   {authors} ({p.get('year', '?')})")
        if p.get("tags") and p["tags"] != "[]":
            tags = json.loads(p["tags"])
            if tags:
                print(f"   Tags: {', '.join(tags)}")
        print()


def cmd_web_search(args):
    """Search arXiv for papers."""
    query = " ".join(args.query)
    if not query:
        print("Usage: /paper web-search <keywords>")
        return

    print(f"Searching arXiv for '{query}'...\n")
    results = srch.search_arxiv(query, max_results=args.limit)

    if not results or (len(results) == 1 and "error" in results[0]):
        print("Search failed or no results. Check your internet connection.")
        return

    print(srch.format_search_results(results))
    print(f"To import a paper: /paper add <arxiv_id>")
    print(f"Example: /paper add {results[0].get('arxiv_id', '2301.12345')}")


def cmd_list(args):
    """List papers in the library."""
    status_filter = args.status if hasattr(args, "status") else None
    papers = lib.list_papers(limit=args.limit, status=status_filter)

    if not papers:
        print("Your library is empty. Add a paper with: /paper add <arxiv_id or path>")
        return

    status_label = f" ({status_filter})" if status_filter else ""
    print(f"Library{status_label} — {len(papers)} paper(s):\n")

    for p in papers:
        status_icon = {"unread": "○", "reading": "◑", "read": "●"}.get(p.get("read_status", ""), "○")
        title = p.get("title") or "Untitled"
        year = p.get("year") or "?"
        pid = p["id"]
        authors = p.get("authors", "")
        if authors:
            author_list = [a.strip() for a in authors.split(",")]
            if len(author_list) > 2:
                authors = f"{author_list[0]}, et al."
            elif author_list:
                authors = author_list[0]
        print(f"{status_icon} [{pid}] {title} ({year})")
        if authors:
            print(f"   {authors}")
        import_date = p.get("import_date", "")[:10]
        if import_date:
            print(f"   Imported: {import_date}")
        print()


def cmd_show(args):
    """Show details of a specific paper."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return

    print(f"Title:   {paper.get('title', 'Unknown')}")
    print(f"Authors: {paper.get('authors', 'Unknown')}")
    print(f"Year:    {paper.get('year', 'Unknown')}")
    print(f"ID:      {paper['id']}")
    if paper.get("arxiv_id"):
        print(f"arXiv:   {paper['arxiv_id']}")
    if paper.get("doi"):
        print(f"DOI:     {paper['doi']}")
    if paper.get("file_path"):
        exists = "✓" if Path(paper["file_path"]).exists() else "✗ (file missing)"
        print(f"File:    {paper['file_path']} {exists}")
    if paper.get("source_url"):
        print(f"URL:     {paper['source_url']}")
    if paper.get("tags") and paper["tags"] != "[]":
        tags = json.loads(paper["tags"])
        if tags:
            print(f"Tags:    {', '.join(tags)}")
    print(f"Status:  {paper.get('read_status', 'unread')}")
    print()
    if paper.get("abstract"):
        print(f"Abstract:\n{paper['abstract']}")
    print()

    notes = lib.list_notes(paper["id"])
    if notes:
        print(f"Notes ({len(notes)}):")
        for note in notes[-3:]:
            print(f"  [{note['created_at'][:10]}] {note['content'][:100]}...")


def cmd_delete(args):
    """Remove a paper from the library (does not delete the PDF)."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return

    title = paper.get("title", "Untitled")
    confirm = input(f"Remove '{title}' from library? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    lib.delete_paper(args.id)
    print(f"Removed: {title}")
    print("(Original PDF file was not deleted.)")


def cmd_tag(args):
    """Add tags to a paper."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return

    existing = json.loads(paper.get("tags", "[]"))
    new_tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    merged = list(dict.fromkeys(existing + new_tags))  # deduplicate, preserve order
    lib.update_paper(args.id, {"tags": json.dumps(merged)})
    print(f"Tags updated: {', '.join(merged)}")


def _resolve_paper_id(id_or_query: str) -> Optional[str]:
    """Resolve a paper ID or search query to a concrete paper ID."""
    # Direct ID match
    paper = lib.get_paper(id_or_query)
    if paper:
        return id_or_query
    # Try as search
    results = lib.search_papers(id_or_query, limit=1)
    if results:
        return results[0]["id"]
    return None


def cmd_read(args):
    """
    Prepare a paper for reading. Extracts text and outputs it so Claude
    can perform summarization or section-by-section analysis.
    Mode: 'summary' (default) or 'deep'.
    """
    paper = lib.get_paper(args.id)
    if not paper:
        # Try search fallback
        results = lib.search_papers(args.id, limit=1)
        if results:
            paper = results[0]
        else:
            print(f"Paper not found: {args.id}")
            print("Tip: run /paper list to see available papers.")
            return

    pid = paper["id"]
    file_path = paper.get("file_path")

    if not file_path or not Path(file_path).exists():
        print(f"PDF file not found for {pid}.")
        print(f"Title: {paper.get('title', 'Unknown')}")
        if paper.get("source_url"):
            print(f"You can download it from: {paper['source_url']}")
        print("Then add it with: /paper add <path>")
        return

    mode = getattr(args, "mode", "summary")

    if mode == "deep":
        result = rdr.extract_sections(file_path)
        sections = result.get("sections", [])
        if not sections:
            print("Could not detect sections. Falling back to full text.")
            mode = "summary"
        else:
            section_idx = getattr(args, "section", 0)
            if section_idx >= len(sections):
                print(f"Section {section_idx} not found. Paper has {len(sections)} sections:")
                for i, s in enumerate(sections):
                    print(f"  [{i}] {s['title']}")
                return

            sec = sections[section_idx]
            print(f"## DEEP READ MODE — {paper.get('title', pid)}")
            print(f"## Section [{section_idx}/{len(sections)-1}]: {sec['title']}")
            if result.get("truncated"):
                print("(Note: PDF was truncated due to length)")
            print()
            print("--- SECTION TEXT START ---")
            print(sec["text"])
            print("--- SECTION TEXT END ---")
            print()
            print(f"TOTAL SECTIONS: {len(sections)}")
            print("SECTION LIST: " + " | ".join(f"[{i}] {s['title']}" for i, s in enumerate(sections)))
            print()
            print("INSTRUCTION_FOR_CLAUDE: Analyze this section. Then ask the user one focused question to check understanding. Offer to move to the next section when ready.")
            # Mark as reading
            if paper.get("read_status") == "unread":
                lib.update_paper(pid, {"read_status": "reading"})
            return

    # Summary mode (default)
    text = rdr.get_paper_text_for_summary(file_path)
    if text.startswith("ERROR"):
        print(f"Failed to extract PDF text: {text}")
        return

    print(f"## SUMMARY MODE — {paper.get('title', pid)}")
    print(f"Paper ID: {pid}")
    print(f"Authors: {paper.get('authors', 'Unknown')} ({paper.get('year', '?')})")
    print()
    print("--- PAPER TEXT START ---")
    print(text)
    print("--- PAPER TEXT END ---")
    print()
    print("INSTRUCTION_FOR_CLAUDE: Generate a structured summary with these sections: **Background & Motivation** | **Core Method** | **Key Results** | **Limitations** | **Relation to Prior Work**. After the summary, ask if the user wants to save it as a note or enter deep read mode.")

    # Mark as reading
    if paper.get("read_status") == "unread":
        lib.update_paper(pid, {"read_status": "reading"})


def cmd_sections(args):
    """List the detected sections of a paper's PDF."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return
    file_path = paper.get("file_path")
    if not file_path or not Path(file_path).exists():
        print(f"PDF not found for {args.id}")
        return
    sections = rdr.list_sections(file_path)
    if not sections:
        print("No sections detected.")
        return
    print(f"Sections in '{paper.get('title', args.id)}':")
    for i, title in enumerate(sections):
        print(f"  [{i}] {title}")


def cmd_note(args):
    """Add a note to a paper."""
    paper = lib.get_paper(args.id)
    if not paper:
        results = lib.search_papers(args.id, limit=1)
        if results:
            paper = results[0]
        else:
            print(f"Paper not found: {args.id}")
            return

    pid = paper["id"]
    content = " ".join(args.content)
    if not content.strip():
        print("Note content cannot be empty.")
        return

    note_type = getattr(args, "type", "manual")
    note = lib.add_note(pid, content, note_type=note_type)
    print(f"Note saved (id={note['id']}) for: {paper.get('title', pid)}")


def cmd_notes(args):
    """List or search notes."""
    if getattr(args, "search", None):
        # Cross-library note search
        query = " ".join(args.search)
        conn = lib.connect()
        like = f"%{query}%"
        rows = conn.execute(
            """SELECT n.*, p.title as paper_title
               FROM notes n JOIN papers p ON n.paper_id = p.id
               WHERE n.content LIKE ?
               ORDER BY n.created_at DESC LIMIT 20""",
            (like,),
        ).fetchall()
        conn.close()
        if not rows:
            print(f"No notes matching '{query}'.")
            return
        print(f"Notes matching '{query}':\n")
        for row in rows:
            row = dict(row)
            print(f"[{row['created_at'][:10]}] {row.get('paper_title', row['paper_id'])}")
            print(f"  {row['content'][:200]}")
            print(f"  (paper: {row['paper_id']})")
            print()
        return

    # List notes for a specific paper
    if not getattr(args, "id", None):
        print("Usage: /paper notes <paper_id>  OR  /paper notes --search <keywords>")
        return

    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return

    notes = lib.list_notes(args.id)
    if not notes:
        print(f"No notes for: {paper.get('title', args.id)}")
        return

    print(f"Notes for '{paper.get('title', args.id)}' ({len(notes)} total):\n")
    for note in notes:
        label = f"[{note['note_type']}]" if note["note_type"] != "manual" else ""
        print(f"  {note['created_at'][:16]} {label}")
        print(f"  {note['content']}")
        print()


def cmd_export(args):
    """Export notes for a paper as Markdown."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return

    md = lib.export_notes_markdown(args.id)

    if getattr(args, "output", None):
        out_path = Path(args.output).expanduser()
        out_path.write_text(md, encoding="utf-8")
        print(f"Notes exported to: {out_path}")
    else:
        print(md)


def cmd_status(args):
    """Update the read status of a paper."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return
    valid = ["unread", "reading", "read"]
    if args.status not in valid:
        print(f"Invalid status. Choose from: {', '.join(valid)}")
        return
    lib.update_paper(args.id, {"read_status": args.status})
    icon = {"unread": "○", "reading": "◑", "read": "●"}[args.status]
    print(f"{icon} Status updated: {paper.get('title', args.id)} → {args.status}")


def cmd_related(args):
    """Find papers related to a given paper."""
    paper = lib.get_paper(args.id)
    if not paper:
        results = lib.search_papers(args.id, limit=1)
        if results:
            paper = results[0]
        else:
            print(f"Paper not found: {args.id}")
            return

    pid = paper["id"]
    title = paper.get("title", pid)
    top_k = getattr(args, "limit", 5)

    related = gph.find_related(pid, top_k=top_k)

    if not related:
        conn = lib.connect()
        count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        conn.close()
        if count < 2:
            print("Need at least 2 papers in your library to find relations.")
            print("Add more papers with: /paper add <arxiv_id>")
        else:
            print(f"No related papers found for '{title}'.")
            print("Tip: add keywords/tags to papers to improve matching.")
        return

    print(f"Papers related to '{title}':\n")
    for i, r in enumerate(related, 1):
        p = r["paper"]
        score = r["score"]
        reasons = r["reasons"]
        year = p.get("year") or "?"
        authors = p.get("authors") or ""
        if authors:
            author_list = [a.strip() for a in authors.split(",")]
            authors = author_list[0] + (", et al." if len(author_list) > 1 else "")

        print(f"[{i}] [{p['id']}] {p.get('title', 'Untitled')} ({year})")
        print(f"     {authors}")
        if reasons:
            print(f"     Because: {' · '.join(reasons)}")
        print()


def cmd_graph(args):
    """
    Output a topic-clustered view of the library for Claude to analyze.
    Optionally filter by topic.
    """
    topic = " ".join(args.topic) if getattr(args, "topic", None) else None

    if topic:
        clusters = gph.topic_cluster(topic, top_k=20)
        if not clusters:
            print(f"No papers found for topic '{topic}'.")
            print("Try broader keywords, or check your library with /paper list")
            return
        papers = [c["paper"] for c in clusters]
        print(f"## GRAPH MODE — Topic: '{topic}' ({len(papers)} papers)\n")
    else:
        conn = lib.connect()
        papers = [dict(r) for r in conn.execute(
            "SELECT * FROM papers ORDER BY year ASC"
        ).fetchall()]
        conn.close()
        if not papers:
            print("Your library is empty.")
            return
        print(f"## GRAPH MODE — Full library ({len(papers)} papers)\n")

    # Print timeline
    by_year = {}
    for p in papers:
        y = str(p.get("year") or "Unknown")
        by_year.setdefault(y, []).append(p)

    print("### Timeline")
    for year in sorted(by_year):
        for p in by_year[year]:
            tags = json.loads(p.get("tags") or "[]")
            tag_str = f"  [{', '.join(tags)}]" if tags else ""
            print(f"  {year}: {p.get('title', p['id'])}{tag_str}")
    print()

    # Print connection hints
    print("### Connections (auto-detected)")
    shown = set()
    for p in papers[:10]:
        related = gph.find_related(p["id"], top_k=2)
        for r in related:
            pair = tuple(sorted([p["id"], r["paper"]["id"]]))
            if pair in shown:
                continue
            shown.add(pair)
            reasons = " · ".join(r["reasons"][:2])
            print(f"  {p.get('title', p['id'])!r}")
            print(f"    ↔ {r['paper'].get('title', r['paper']['id'])!r}")
            print(f"    ({reasons})")
    print()

    print("INSTRUCTION_FOR_CLAUDE: Analyze the literature network above. Describe: (1) the main research threads, (2) key connections between papers, (3) any notable gaps or clusters. If a topic was specified, focus on how the papers address that topic from different angles.")


def cmd_survey(args):
    """
    Prepare a survey draft. Gathers relevant papers and their metadata,
    then passes to Claude for synthesis.
    """
    topic = " ".join(args.topic) if getattr(args, "topic", None) else None

    conn = lib.connect()
    total = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    conn.close()

    if total == 0:
        print("Your library is empty. Add papers first with: /paper add <arxiv_id>")
        return

    summary = gph.build_graph_summary(topic=topic)

    if topic:
        print(f"## SURVEY MODE — '{topic}'\n")
    else:
        print(f"## SURVEY MODE — Full library survey\n")

    # Also include notes for relevant papers
    if topic:
        clusters = gph.topic_cluster(topic, top_k=15)
        relevant_ids = [c["paper"]["id"] for c in clusters]
    else:
        conn = lib.connect()
        relevant_ids = [r[0] for r in conn.execute("SELECT id FROM papers").fetchall()]
        conn.close()

    notes_section = []
    for pid in relevant_ids:
        notes = lib.list_notes(pid)
        if notes:
            paper = lib.get_paper(pid)
            ptitle = paper.get("title", pid) if paper else pid
            notes_section.append(f"\n[Notes for '{ptitle}']")
            for note in notes:
                notes_section.append(f"  - {note['content'][:300]}")

    print("--- LIBRARY DATA START ---")
    print(summary)
    if notes_section:
        print("\n### YOUR READING NOTES")
        print("\n".join(notes_section))
    print("--- LIBRARY DATA END ---")
    print()

    if topic:
        instruction = (
            f"INSTRUCTION_FOR_CLAUDE: Write a survey draft about '{topic}' based on the papers above. "
            "Structure it as: "
            "(1) **Introduction** — scope and motivation of this survey; "
            "(2) **Timeline & Evolution** — how the field developed chronologically; "
            "(3) **Main Approaches** — categorize papers by methodology or approach; "
            "(4) **Comparison & Analysis** — key differences, trade-offs, and open problems; "
            "(5) **Conclusion & Future Directions** — where the field is headed. "
            "Use inline citations like (Author et al., Year) or [paper_id]. "
            "Incorporate the user's reading notes where relevant. "
            "After the draft, ask: 'Want me to expand any section, or save this as a note?'"
        )
    else:
        instruction = (
            "INSTRUCTION_FOR_CLAUDE: Provide an overview of the entire library above. "
            "Identify: (1) main research themes, (2) key papers in each theme, "
            "(3) connections across themes, (4) potential gaps. "
            "Keep it structured and concise. "
            "After the overview, ask: 'Want a focused survey on a specific topic?'"
        )
    print(instruction)


def cmd_config(args):
    """Configure ScholarMind settings."""
    if args.set_lib_dir:
        lib.set_lib_dir(args.set_lib_dir)
        print(f"Library directory set to: {args.set_lib_dir}")
    else:
        print(f"Library directory: {lib.get_lib_dir()}")
        print(f"Database: {lib.get_db_path()}")
        print(f"PDF storage: {lib.get_pdf_dir()}")
        conn = lib.connect()
        count = conn.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
        conn.close()
        print(f"Papers in library: {count}")


def main():
    parser = argparse.ArgumentParser(
        prog="paper",
        description="ScholarMind — literature management in Claude Code",
    )
    sub = parser.add_subparsers(dest="cmd")

    # add
    p_add = sub.add_parser("add", help="Import a paper (arXiv ID, URL, or local PDF)")
    p_add.add_argument("source", help="arXiv ID, URL, or local PDF path")
    p_add.add_argument("--tags", default="", help="Comma-separated tags")
    p_add.add_argument("--no-download", dest="download", action="store_false", help="Don't download PDF")

    # search (local library)
    p_search = sub.add_parser("search", help="Search your local library")
    p_search.add_argument("query", nargs="+", help="Search keywords")
    p_search.add_argument("--limit", type=int, default=10)

    # web-search
    p_web = sub.add_parser("web-search", help="Search arXiv for papers")
    p_web.add_argument("query", nargs="+", help="Search keywords")
    p_web.add_argument("--limit", type=int, default=8)

    # list
    p_list = sub.add_parser("list", help="List papers in the library")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--status", choices=["unread", "reading", "read"], help="Filter by read status")

    # show
    p_show = sub.add_parser("show", help="Show details of a paper")
    p_show.add_argument("id", help="Paper ID")

    # delete
    p_del = sub.add_parser("delete", help="Remove a paper from the library")
    p_del.add_argument("id", help="Paper ID")

    # tag
    p_tag = sub.add_parser("tag", help="Add tags to a paper")
    p_tag.add_argument("id", help="Paper ID")
    p_tag.add_argument("tags", help="Comma-separated tags to add")

    # config
    p_cfg = sub.add_parser("config", help="Show or update configuration")
    p_cfg.add_argument("--set-lib-dir", metavar="PATH", help="Set library directory")

    # read
    p_read = sub.add_parser("read", help="Read a paper (summary or deep mode)")
    p_read.add_argument("id", help="Paper ID or search query")
    p_read.add_argument("--mode", choices=["summary", "deep"], default="summary")
    p_read.add_argument("--section", type=int, default=0, help="Section index for deep mode")

    # sections
    p_sec = sub.add_parser("sections", help="List detected sections in a paper's PDF")
    p_sec.add_argument("id", help="Paper ID")

    # note
    p_note = sub.add_parser("note", help="Add a note to a paper")
    p_note.add_argument("id", help="Paper ID")
    p_note.add_argument("content", nargs="+", help="Note text")
    p_note.add_argument("--type", default="manual", help="Note type (manual, summary, insight)")

    # notes
    p_notes = sub.add_parser("notes", help="List or search notes")
    p_notes.add_argument("id", nargs="?", help="Paper ID (omit to use --search)")
    p_notes.add_argument("--search", nargs="+", help="Search notes across all papers")

    # export
    p_export = sub.add_parser("export", help="Export notes as Markdown")
    p_export.add_argument("id", help="Paper ID")
    p_export.add_argument("--output", "-o", metavar="FILE", help="Output file path")

    # status
    p_status = sub.add_parser("status", help="Update read status of a paper")
    p_status.add_argument("id", help="Paper ID")
    p_status.add_argument("status", choices=["unread", "reading", "read"])

    # related
    p_related = sub.add_parser("related", help="Find papers related to a given paper")
    p_related.add_argument("id", help="Paper ID or title keywords")
    p_related.add_argument("--limit", type=int, default=5)

    # graph
    p_graph = sub.add_parser("graph", help="Visualize the literature network (optionally by topic)")
    p_graph.add_argument("topic", nargs="*", help="Optional topic to filter by")

    # survey
    p_survey = sub.add_parser("survey", help="Generate a survey draft from your library")
    p_survey.add_argument("topic", nargs="*", help="Topic/keywords to focus the survey")

    # help fallback
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("""ScholarMind — literature management in Claude Code

Import & Organize:
  /paper add <arxiv_id|url|path>           Import a paper
  /paper list [--status unread]            List papers
  /paper search <keywords>                 Search your local library
  /paper web-search <keywords>             Search arXiv
  /paper show <id>                         Show paper details
  /paper tag <id> <tag1,tag2>              Add tags
  /paper status <id> <unread|reading|read> Update read status
  /paper delete <id>                       Remove from library

Read & Annotate:
  /paper read <id>                         Summarize a paper
  /paper read <id> --mode deep             Section-by-section deep read
  /paper read <id> --mode deep --section N Jump to section N
  /paper sections <id>                     List detected sections
  /paper note <id> <text>                  Add a note to a paper
  /paper notes <id>                        List notes for a paper
  /paper notes --search <keywords>         Search notes across all papers
  /paper export <id> [-o file.md]          Export notes as Markdown

Discover & Synthesize:
  /paper related <id>                      Find related papers
  /paper graph [topic]                     Literature network overview
  /paper survey [topic]                    Generate a survey draft

Config:
  /paper config                            Show library settings
  /paper config --set-lib-dir <path>       Change library directory
""")
        return

    args = parser.parse_args()

    dispatch = {
        "add": cmd_add,
        "search": cmd_search,
        "web-search": cmd_web_search,
        "list": cmd_list,
        "show": cmd_show,
        "delete": cmd_delete,
        "tag": cmd_tag,
        "config": cmd_config,
        "read": cmd_read,
        "sections": cmd_sections,
        "note": cmd_note,
        "notes": cmd_notes,
        "export": cmd_export,
        "status": cmd_status,
        "related": cmd_related,
        "graph": cmd_graph,
        "survey": cmd_survey,
    }

    fn = dispatch.get(args.cmd)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
