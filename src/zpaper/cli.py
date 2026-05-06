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


import re as _re


def _add_one(source: str, tags: list, download: bool) -> dict:
    """Import a single paper. Returns a status dict with keys: status, paper, source, error."""
    metadata = {}
    file_path = None

    # --- Case 1: arXiv ID or URL ---
    arxiv_id = None
    for pattern in [
        r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"(?:arxiv:|arXiv:)(\d{4}\.\d{4,5}(?:v\d+)?)",
        r"^(\d{4}\.\d{4,5}(?:v\d+)?)$",
    ]:
        m = _re.search(pattern, source, _re.IGNORECASE)
        if m:
            arxiv_id = m.group(1).split("v")[0]
            break

    if arxiv_id:
        print(f"  Fetching arXiv metadata for {arxiv_id}...")
        metadata = lib.fetch_arxiv_metadata(arxiv_id)
        if not metadata:
            return {"status": "error", "source": source,
                    "error": f"Could not fetch arXiv metadata for {arxiv_id}"}

        print(f"  Title: {metadata.get('title', 'Unknown')}")

        if download:
            print(f"  Downloading PDF...")
            pdf_dir = lib.get_pdf_dir()
            file_path = srch.download_arxiv_pdf(arxiv_id, pdf_dir, title=metadata.get("title"))
            if file_path:
                print(f"  PDF saved: {file_path}")
            else:
                print(f"  PDF download failed. Saving metadata only.")

    # --- Case 2: local file ---
    elif Path(source).expanduser().exists():
        file_path = str(Path(source).expanduser().resolve())
        print(f"  Extracting metadata from {Path(file_path).name}...")
        extracted = lib.extract_pdf_metadata(file_path)

        if extracted.get("arxiv_id"):
            print(f"  Detected arXiv ID: {extracted['arxiv_id']}, fetching full metadata...")
            arxiv_meta = lib.fetch_arxiv_metadata(extracted["arxiv_id"])
            if arxiv_meta:
                for k, v in extracted.items():
                    if k not in arxiv_meta or not arxiv_meta[k]:
                        arxiv_meta[k] = v
                metadata = arxiv_meta
            else:
                metadata = extracted
        else:
            metadata = extracted

        if extracted.get("missing_fields"):
            print(f"  Missing fields: {', '.join(extracted['missing_fields'])}")
            print(f"  Fix with: paper edit <id> title='...' authors='...'")

    else:
        return {"status": "error", "source": source,
                "error": f"Not a valid arXiv ID/URL or local file path: {source!r}"}

    result = lib.add_paper(file_path=file_path, metadata=metadata, tags=tags)
    result["source"] = source
    return result


def cmd_add(args):
    """Add one or more papers from arXiv IDs, URLs, or local PDF paths."""
    sources = args.sources
    if not sources:
        print("Usage: /paper add <arxiv_id|url|path> [arxiv_id|url|path ...]")
        return

    tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
    download = getattr(args, "download", True)

    # Single-source: keep original concise output style
    if len(sources) == 1:
        source = sources[0]
        result = _add_one(source, tags, download)
        if result["status"] == "error":
            print(f"Error: {result['error']}")
            print("Examples:")
            print("  paper add 2301.12345")
            print("  paper add https://arxiv.org/abs/2301.12345")
            print("  paper add /path/to/paper.pdf")
            return
        p = result["paper"]
        if result["status"] == "duplicate":
            print(f"\nAlready in library: [{p['id']}] {p.get('title', 'Untitled')}")
        else:
            print(f"\nAdded: [{p['id']}] {p.get('title', 'Untitled')}")
            if p.get("year"):
                print(f"Year: {p['year']} | Authors: {p.get('authors', 'Unknown')}")
        return

    # Batch mode: process each source and print a summary table
    print(f"Batch import: {len(sources)} source(s)\n")
    added, duplicates, errors = [], [], []

    for i, source in enumerate(sources, 1):
        print(f"[{i}/{len(sources)}] {source}")
        result = _add_one(source, tags, download)
        if result["status"] == "added":
            added.append(result["paper"])
            print(f"  ✓ Added: [{result['paper']['id']}]")
        elif result["status"] == "duplicate":
            duplicates.append(result["paper"])
            print(f"  = Already in library: [{result['paper']['id']}]")
        else:
            errors.append(result)
            print(f"  ✗ Error: {result['error']}")
        print()

    # Summary
    print("─" * 50)
    print(f"Done: {len(added)} added, {len(duplicates)} duplicate(s), {len(errors)} error(s)")
    if errors:
        print("\nFailed sources:")
        for e in errors:
            print(f"  ✗ {e['source']}: {e['error']}")


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
    limit = None if getattr(args, "all", False) else args.limit
    papers = lib.list_papers(limit=limit, status=status_filter)

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


EDITABLE_FIELDS = {"title", "authors", "year", "abstract", "keywords", "arxiv_id", "doi", "source_url", "tags"}


def cmd_edit(args):
    """Edit metadata fields of a paper."""
    paper = lib.get_paper(args.id)
    if not paper:
        results = lib.search_papers(args.id, limit=1)
        if results:
            paper = results[0]
        else:
            print(f"Paper not found: {args.id}")
            return

    pid = paper["id"]

    if not args.assignments:
        print(f"Usage: /paper edit <id> field=value [field=value ...]")
        print(f"Editable fields: {', '.join(sorted(EDITABLE_FIELDS))}")
        print(f"\nCurrent values for [{pid}] {paper.get('title', 'Untitled')}:")
        for f in sorted(EDITABLE_FIELDS):
            print(f"  {f}: {paper.get(f)!r}")
        return

    # Parse key=value assignments
    updates = {}
    for token in args.assignments:
        if "=" not in token:
            print(f"Skipping unrecognized token (expected key=value): {token!r}")
            continue
        key, _, value = token.partition("=")
        key = key.strip()
        if key not in EDITABLE_FIELDS:
            print(f"Unknown field: {key!r}. Editable fields: {', '.join(sorted(EDITABLE_FIELDS))}")
            continue
        if key == "year":
            try:
                value = int(value)
            except ValueError:
                print(f"year must be an integer, got: {value!r}")
                continue
        elif key == "tags":
            # Accept comma-separated list or empty string to clear
            tags = [t.strip() for t in value.split(",") if t.strip()]
            value = json.dumps(tags)
        updates[key] = value

    if not updates:
        print("No valid updates provided.")
        return

    # Print diff and apply
    print(f"Updating [{pid}] {paper.get('title', 'Untitled')}:\n")
    for k, v in updates.items():
        old = paper.get(k)
        if k == "tags":
            old_display = ", ".join(json.loads(old or "[]"))
            new_display = ", ".join(json.loads(v))
            print(f"  {k}: {old_display!r} → {new_display!r}")
        else:
            print(f"  {k}: {old!r} → {v!r}")

    lib.update_paper(pid, updates)
    print("\nUpdated.")


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
        section_idx = getattr(args, "section", None)
        if section_idx is None:
            # No --section given: output full text for the LLM to deep-read freely
            text = rdr.get_paper_text_for_summary(file_path)
            if text.startswith("ERROR"):
                print(f"Failed to extract PDF text: {text}")
                return
            print(f"## DEEP READ MODE — {paper.get('title', pid)}")
            print(f"Paper ID: {pid}")
            print(f"Authors: {paper.get('authors', 'Unknown')} ({paper.get('year', '?')})")
            print()
            print("--- PAPER TEXT START ---")
            print(text)
            print("--- PAPER TEXT END ---")
            print()
            print("INSTRUCTION_FOR_CLAUDE: Deep-read the full paper. Walk through it section by section in your own structure, explain each part clearly, highlight key concepts, and ask the user one focused question per section to check understanding. Offer to add notes at any point.")
            if paper.get("read_status") == "unread":
                lib.update_paper(pid, {"read_status": "reading"})
            return

        result = rdr.extract_sections(file_path)
        sections = result.get("sections", [])
        if not sections:
            print("Could not detect sections. Falling back to full text.")
            mode = "summary"
        else:
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

    result = rdr.extract_sections(file_path)
    wl = result.get("sections_whitelist", [])
    st = result.get("sections_structural", [])

    title = paper.get("title", args.id)
    print(f"Sections in '{title}':\n")

    print("--- STRATEGY A: Whitelist ---")
    if wl:
        for i, s in enumerate(wl):
            print(f"  [{i}] {s['title']}")
    else:
        print("  (no matches)")

    print("\n--- STRATEGY B: Structural ---")
    if st:
        for i, s in enumerate(st):
            print(f"  [{i}] {s['title']}")
    else:
        print("  (no matches)")

    print(
        "\nINSTRUCTION_FOR_CLAUDE: Two section detection strategies are shown above. "
        "Strategy A uses a keyword whitelist and is precise but may miss non-standard titles. "
        "Strategy B uses structural heuristics and is broader but may include false positives (e.g. figure captions, page headers). "
        "Merge and deduplicate them: keep entries that appear in both, prefer Strategy A titles when both match the same position, "
        "and include Strategy B entries only when they represent a clearly distinct section absent from A. "
        "Present the final merged section list to the user, then ask which section they want to start with."
    )


def cmd_explain(args):
    """Search for a keyword/phrase in a paper and output context for the LLM to explain."""
    paper = lib.get_paper(args.id)
    if not paper:
        print(f"Paper not found: {args.id}")
        return
    file_path = paper.get("file_path")
    if not file_path or not Path(file_path).exists():
        print(f"PDF not found for {args.id}")
        return

    query = " ".join(args.query)
    matches = rdr.search_text(file_path, query, context_lines=8)

    if not matches:
        print(f'No matches found for "{query}" in {paper.get("title", args.id)}.')
        return

    print(f'Found {len(matches)} match(es) for "{query}" in \'{paper.get("title", args.id)}\':\n')
    for i, m in enumerate(matches):
        print(f"--- MATCH {i+1} (line {m['line_number']}) ---")
        print(m["context"])
        print()

    print(f'INSTRUCTION_FOR_CLAUDE: The user wants to understand "{query}" from this paper. '
          "Each match above shows the sentence plus surrounding context. "
          "Explain what this means in plain language, using the context to resolve any ambiguity. "
          "If there are multiple matches, address each one. "
          "After explaining, ask if the user wants to add a note or continue reading.")


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
        # Cross-library note search — FTS first, LIKE fallback
        query = " ".join(args.search)
        conn = lib.connect()
        rows = []
        try:
            rows = conn.execute(
                """SELECT n.*, p.title as paper_title
                   FROM notes n
                   JOIN notes_fts f ON n.id = f.rowid
                   JOIN papers p ON n.paper_id = p.id
                   WHERE notes_fts MATCH ?
                   ORDER BY rank LIMIT 20""",
                (query,),
            ).fetchall()
        except Exception:
            pass
        if not rows:
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
            print(f"#{row['id']} [{row['created_at'][:10]}] {row.get('paper_title', row['paper_id'])}")
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
        print(f"  #{note['id']} {note['created_at'][:16]} {label}")
        print(f"  {note['content']}")
        print()


def cmd_note_delete(args):
    """Delete a note by its ID."""
    conn = lib.connect()
    row = conn.execute(
        "SELECT n.*, p.title as paper_title FROM notes n JOIN papers p ON n.paper_id = p.id WHERE n.id=?",
        (args.note_id,),
    ).fetchone()
    conn.close()
    if not row:
        print(f"Note #{args.note_id} not found.")
        return
    row = dict(row)
    print(f"Note #{args.note_id} (paper: {row.get('paper_title', row['paper_id'])})")
    print(f"  {row['content'][:200]}")
    confirm = input("Delete this note? (y/N): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return
    lib.delete_note(args.note_id)
    print(f"Note #{args.note_id} deleted.")


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


def cmd_compare(args):
    """
    Multi-paper comparison mode. Feeds metadata (and optionally full text) for
    each paper to Claude with a structured comparison prompt.
    """
    ids = args.ids
    if len(ids) < 2:
        print("Error: compare requires at least 2 paper IDs.")
        sys.exit(1)
    if len(ids) > 5:
        print(f"Warning: capped at 5 papers (ignoring {ids[5:]})")
        ids = ids[:5]

    papers = []
    for pid in ids:
        p = lib.get_paper(pid)
        if not p:
            print(f"Error: paper '{pid}' not found in library.")
            sys.exit(1)
        papers.append(p)

    n = len(papers)
    print(f"## COMPARE MODE — {n} papers")
    print(f"Mode: {args.mode}")

    if n == 2:
        df = gph._build_df(papers)
        score = gph.compute_similarity(papers[0], papers[1], df, n)
        reasons = gph._explain_similarity(papers[0], papers[1])
        print(f"Similarity score: {score:.2f}")
        if reasons:
            print(f"Shared signals: {' · '.join(reasons)}")

    print()

    for i, p in enumerate(papers, 1):
        pid = p["id"]
        print(f"--- PAPER {i} [{pid}] METADATA START ---")
        print(f"Title: {p.get('title', '(unknown)')}")
        print(f"Authors: {p.get('authors', '')}")
        print(f"Year: {p.get('year', '')}")
        print(f"Abstract: {p.get('abstract', '')}")
        print(f"Keywords: {p.get('keywords', '')}")
        print(f"Tags: {p.get('tags', '[]')}")
        notes = lib.list_notes(pid)
        if notes:
            print("Notes:")
            for nt in notes:
                print(f"  [{nt['note_type']}] {nt['content'][:200]}")
        print(f"--- PAPER {i} [{pid}] METADATA END ---")
        print()

        if args.mode == "full":
            fp = p.get("file_path")
            if fp and os.path.exists(fp):
                text = rdr.get_paper_text_for_summary(fp)
                print(f"--- PAPER {i} [{pid}] TEXT START ---")
                print(text)
                print(f"--- PAPER {i} [{pid}] TEXT END ---")
            else:
                print(f"[Paper {i}: PDF not available — using metadata only]")
            print()

    titles = [p.get("title", p["id"]) for p in papers]
    refs = " | ".join(f"[Paper {i+1}: {t[:40]}]" for i, t in enumerate(titles))
    print(
        f"INSTRUCTION_FOR_CLAUDE: You are given {n} research papers above ({refs}). "
        "Produce a structured comparative analysis with these sections:\n"
        "1. **Overview Table** — one row per paper: title, year, core contribution (1 sentence)\n"
        "2. **Background & Motivation** — what problem each addresses, and how they differ\n"
        "3. **Core Method** — key technical approach of each; compare similarities and differences\n"
        "4. **Key Results** — main findings per paper; complementary or contradictory?\n"
        "5. **Limitations & Open Questions** — what each paper leaves unsolved\n"
        "6. **Synthesis** — how these papers relate; which insight is most important; what to read next\n"
        f"Use inline references like [Paper 1] or [Paper 2]. Prioritize insight over exhaustive listing."
    )


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
    p_add = sub.add_parser("add", help="Import one or more papers (arXiv IDs, URLs, or local PDFs)")
    p_add.add_argument("sources", nargs="+", metavar="source",
                       help="arXiv ID, URL, or local PDF path (repeat for batch import)")
    p_add.add_argument("--tags", default="", help="Comma-separated tags (applied to all)")
    p_add.add_argument("--no-download", dest="download", action="store_false", help="Don't download PDFs")

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
    p_list.add_argument("--all", dest="all", action="store_true", help="Show all papers (no limit)")
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

    # edit
    p_edit = sub.add_parser("edit", help="Edit metadata fields of a paper")
    p_edit.add_argument("id", help="Paper ID")
    p_edit.add_argument("assignments", nargs="*", metavar="field=value",
                        help="Fields to update, e.g. title='New Title' authors='A, B' year=2024")

    # note-delete
    p_ndel = sub.add_parser("note-delete", help="Delete a note by its ID")
    p_ndel.add_argument("note_id", type=int, help="Note ID (shown in /paper notes <id>)")

    # config
    p_cfg = sub.add_parser("config", help="Show or update configuration")
    p_cfg.add_argument("--set-lib-dir", metavar="PATH", help="Set library directory")

    # read
    p_read = sub.add_parser("read", help="Read a paper (summary or deep mode)")
    p_read.add_argument("id", help="Paper ID or search query")
    p_read.add_argument("--mode", choices=["summary", "deep"], default="summary")
    p_read.add_argument("--section", type=int, default=None, help="Section index for deep mode")

    # sections
    p_sec = sub.add_parser("sections", help="List detected sections in a paper's PDF")
    p_sec.add_argument("id", help="Paper ID")

    # explain
    p_explain = sub.add_parser("explain", help="Find and explain a keyword or phrase in a paper")
    p_explain.add_argument("id", help="Paper ID")
    p_explain.add_argument("query", nargs="+", help="Keyword or phrase to look up")

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

    # compare
    p_compare = sub.add_parser("compare", help="Compare multiple papers side by side")
    p_compare.add_argument("ids", nargs="+", help="Paper IDs to compare (2–5)")
    p_compare.add_argument(
        "--mode",
        choices=["abstract", "full"],
        default="abstract",
        help="abstract=metadata only (default); full=include PDF text",
    )

    # help fallback
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help", "help"):
        print("""ScholarMind — literature management in Claude Code

Import & Organize:
  /paper add <id|url|path> [...]           Import one or more papers (batch supported)
  /paper list [--status unread] [--all]    List papers (default: last 20)
  /paper search <keywords>                 Search your local library
  /paper web-search <keywords>             Search arXiv
  /paper show <id>                         Show paper details
  /paper edit <id> field=value ...         Edit metadata (title, authors, year, tags, ...)
  /paper tag <id> <tag1,tag2>              Append tags
  /paper status <id> <unread|reading|read> Update read status
  /paper delete <id>                       Remove from library

Read & Annotate:
  /paper read <id>                         Summarize a paper
  /paper read <id> --mode deep             Section-by-section deep read
  /paper read <id> --mode deep --section N Jump to section N
  /paper sections <id>                     List detected sections
  /paper explain <id> <keyword or phrase>  Find and explain a term in the paper
  /paper note <id> <text>                  Add a note to a paper
  /paper notes <id>                        List notes for a paper (shows note IDs)
  /paper notes --search <keywords>         Search notes across all papers
  /paper note-delete <note_id>             Delete a note by ID
  /paper export <id> [-o file.md]          Export notes as Markdown

Discover & Synthesize:
  /paper related <id>                      Find related papers
  /paper graph [topic]                     Literature network overview
  /paper survey [topic]                    Generate a survey draft
  /paper compare <id1> <id2> [...]         Compare 2–5 papers side by side
  /paper compare <ids...> --mode full      Compare with full PDF text

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
        "edit": cmd_edit,
        "config": cmd_config,
        "read": cmd_read,
        "sections": cmd_sections,
        "explain": cmd_explain,
        "note": cmd_note,
        "notes": cmd_notes,
        "note-delete": cmd_note_delete,
        "export": cmd_export,
        "status": cmd_status,
        "related": cmd_related,
        "graph": cmd_graph,
        "survey": cmd_survey,
        "compare": cmd_compare,
    }

    fn = dispatch.get(args.cmd)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
