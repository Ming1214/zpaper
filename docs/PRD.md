# PRD: zpaper — Claude Code Literature Management & Reading Assistant

**Version**: 1.0
**Date**: 2026-05-05

---

## Problem Statement

Individual researchers working in Claude Code lack structured tools for managing academic literature. PDFs accumulate in scattered folders, connections between papers must be tracked manually, and reading notes have no permanent home. Existing tools like Mendeley and Zotero rely on GUI interactions that break the flow of deep work. The cost of not solving this: knowledge from read papers is not retained or connected, and writing reviews or surveys requires painful reconstruction of information already encountered.

---

## Goals

1. **Zero import friction**: Add a paper via one arXiv ID — metadata fetched and PDF downloaded automatically. 90% of metadata fields extracted without manual entry.
2. **Queryable library in under 5 minutes**: Full-text search across titles, abstracts, keywords, and personal notes without navigating a file system.
3. **Structured reading output**: Summary and deep-read modes produce structured Markdown output that the user can reuse in writing. Target: 60%+ of generated summaries saved as notes.
4. **Notes with provenance**: Every note is bound to a paper and timestamped. Notes are searchable across the entire library.
5. **Zero GUI dependency**: All features accessible through Claude Code natural language or `/paper` commands.

---

## Non-Goals

- **No multi-user collaboration**: Single-user tool; no sharing, permissions, or sync.
- **No cloud storage**: Data stays local. No account system.
- **No GUI client**: No desktop or web UI. Claude Code is the interface.
- **No citation formatter**: Does not produce APA/MLA/Chicago formatted citations (stores raw metadata; formatting is out of scope).
- **No PDF annotation sync**: Notes live in the system's own database, not embedded in PDF files. No sync with PDF annotation apps.

---

## User Stories

### Import & Organize
- As a researcher, I want to say "add arXiv:2301.12345" and have the paper's metadata and PDF stored automatically, so I don't manually copy-paste titles and authors.
- As a researcher, I want to search arXiv from inside Claude Code and import papers directly, so I never need to switch to a browser mid-session.
- As a researcher, when metadata extraction fails, I want to see exactly which fields are missing so I can fill them in, rather than having a silent incomplete record.

### Reading
- As a researcher, I want a structured summary of any paper in under 60 seconds, so I can decide whether to read deeply without reading the whole thing first.
- As a researcher, I want to walk through a paper section by section with Claude asking me questions, so I develop genuine understanding rather than passive reading.
- As a researcher, I want to add a note mid-reading that is automatically linked to the current paper, so my insight is captured in context.

### Discovery & Synthesis
- As a researcher, I want to ask "what papers are related to this one?" and get a list with explanations, so I can trace the intellectual lineage of an idea.
- As a researcher, I want to ask "write me a survey on topic X" and get a structured draft that cites my library, so I have a starting point for a literature review section.

---

## Requirements

### Phase 1 — Import & Search (P0)

| Requirement | Acceptance Criteria |
|---|---|
| Local PDF import with auto metadata extraction | title/authors/year extracted in ≥85% of standard academic PDFs |
| arXiv import: fetch metadata + download PDF | Given an arXiv ID, paper is in library with full metadata in <30s |
| arXiv search from CLI | Returns ranked results with title, authors, year, abstract snippet |
| Full-text library search | Keyword query returns matching papers ordered by relevance |
| SQLite local database | All data in `~/.scholarmind/library.db`; original PDFs never modified |
| `/paper` command family | `add`, `search`, `web-search`, `list`, `show`, `tag`, `delete`, `config` |

### Phase 2 — Read & Annotate (P0)

| Requirement | Acceptance Criteria |
|---|---|
| Summary mode | Structured 5-section summary generated from full PDF text |
| Deep read mode | PDF split into detected sections; Claude guides one section at a time |
| Note creation | Notes bound to paper ID and timestamped |
| Cross-library note search | Keyword search returns matching notes with paper context |
| Markdown export | Notes for a paper exportable as clean Markdown with frontmatter |
| Read status tracking | Papers can be marked unread / reading / read |

### Phase 3 — Discover & Synthesize (P1)

| Requirement | Acceptance Criteria |
|---|---|
| Related paper finder | Returns top-N most similar papers with similarity explanations |
| Graph mode | Timeline + auto-detected connections rendered as text for Claude to analyze |
| Survey mode | Claude produces structured survey draft with inline citations from library |
| Topic clustering | `graph <topic>` and `survey <topic>` filter to relevant papers |

### Future (P2)

- MCP Server: expose library as MCP tools for other Claude instances
- Obsidian sync: export notes as Obsidian-compatible Markdown with backlinks
- Local vector embeddings: semantic search via local embedding model (e.g. nomic-embed)
- Reading time & progress tracking

---

## Success Metrics

| Metric | Target | Window |
|---|---|---|
| Import success rate (arXiv) | ≥95% | Per session |
| Metadata completeness (title+authors+year) | ≥85% | Per 20 sampled papers |
| Summary generation time | <60s for papers ≤30 pages | Per invocation |
| Library growth | ≥10 papers/week added | 4 weeks post-install |
| Note reuse in writing | ≥50% of notes referenced in later sessions | 8 weeks post-install |

---

## Open Questions (resolved)

| Question | Resolution |
|---|---|
| PDF parsing library? | `pymupdf` (fitz) — best double-column academic PDF support |
| Library default path? | `~/.scholarmind/` with user override via `config --set-lib-dir` |
| Semantic similarity for graph? | TF-IDF keyword overlap (v1); local embeddings deferred to P2 |
| Can Claude Code web_search download PDFs? | No binary download — arXiv PDFs fetched via `requests` directly |
| arXiv-only or also Semantic Scholar / PubMed? | arXiv only in v1; others deferred |

---

## Timeline

| Phase | Scope | Status |
|---|---|---|
| Phase 1 | Import, search, arXiv download, SQLite library | Complete |
| Phase 2 | Summary, deep read, notes, export | Complete |
| Phase 3 | Related papers, graph, survey | Complete |
| Phase 4 | MCP server, vector search, Obsidian sync | Planned |
