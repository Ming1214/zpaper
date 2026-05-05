# zpaper — Literature Management & Reading Assistant for Claude Code

A personal research assistant that lives inside [Claude Code](https://claude.ai/code). Import papers, search your library, deep-read PDFs section by section, take notes, discover connections, and generate survey drafts — all through natural language, without leaving your terminal.

No GUI. No cloud. Everything stored locally.

---

## What it does

| Feature | How it works |
|---|---|
| **Import papers** | Paste an arXiv ID or URL — metadata is fetched automatically and the PDF is downloaded. Or drag in a local PDF. |
| **Search library** | Full-text search across titles, abstracts, keywords, and your own notes. |
| **Search arXiv** | Query arXiv directly and import results in one step. |
| **Summary mode** | Claude reads the full paper and produces a structured summary: Background / Method / Results / Limitations / Prior Work. |
| **Deep read mode** | Read the full paper or jump to a specific section. Claude explains each part and asks a question to check your understanding. |
| **Explain a passage** | Paste a keyword or phrase you don't understand — Claude finds all matching passages in the PDF (with fuzzy matching for line-break artifacts) and explains them in context. |
| **Notes** | Add freeform notes to any paper. Search notes across your entire library. Export to Markdown. |
| **Related papers** | Automatically find papers in your library that share keywords, topics, or tags — with an explanation of why they're related. |
| **Graph mode** | See the timeline and connection map of your library (or a topic slice of it). |
| **Survey mode** | Pick a topic — Claude synthesizes all relevant papers and your notes into a structured survey draft with inline citations. |

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (CLI)
- Python 3.9+
- `pymupdf` and `requests` (see install below)

---

## Installation

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/zpaper.git
cd zpaper
```

### 2. Run the installer

```bash
bash scripts/install.sh
```

This does three things:
1. Installs the `zpaper` Python package (editable install via `pip install -e .`)
2. Creates `~/.scholarmind/` for your literature database and PDFs
3. Copies the Claude Code skill file to `~/.claude/skills/paper/`

After installation, the `paper` command is available globally in your terminal, and Claude Code will recognize the `/paper` skill.

That's it. Open a Claude Code session and start using `/paper`.

---

## Quick Start

```
# Import a paper from arXiv
/paper add 1706.03762

# Import from a URL
/paper add https://arxiv.org/abs/2310.06825

# Import a local PDF
/paper add ~/Downloads/my_paper.pdf

# Search arXiv and pick what to import
/paper web-search "vision language model survey"

# Search your local library
/paper search "attention mechanism"

# Summarize a paper
/paper read arxiv:1706.03762

# Deep read — section by section with Claude
/paper read arxiv:1706.03762 --mode deep

# Add a note while reading
/paper note arxiv:1706.03762 This is where they justify dropping recurrence entirely

# Find related papers in your library
/paper related arxiv:1706.03762

# Generate a survey draft on a topic
/paper survey transformer language model
```

You can also just talk to Claude naturally inside Claude Code:

> "Add the BERT paper to my library"
> "Summarize the GPT-3 paper for me"
> "What papers do I have related to diffusion models?"
> "Write me a survey on vision-language pre-training"

---

## Full Command Reference

### Import & Organize

```
/paper add <arxiv_id|url|path>            Import a paper
/paper list                               List all papers
/paper list --status unread               Filter by read status (unread/reading/read)
/paper search <keywords>                  Full-text search your library
/paper web-search <keywords>              Search arXiv
/paper show <id>                          Show full paper details
/paper tag <id> <tag1,tag2>               Add tags to a paper
/paper status <id> <unread|reading|read>  Update read status
/paper delete <id>                        Remove from library (PDF kept)
```

### Read & Annotate

```
/paper read <id>                          Summarize a paper (default)
/paper read <id> --mode deep              Deep read the full paper (Claude structures it)
/paper read <id> --mode deep --section N  Deep read a specific detected section
/paper sections <id>                      List detected sections in a PDF
/paper explain <id> <keyword or phrase>   Find and explain a term or passage in the PDF
/paper note <id> <text>                   Add a note to a paper
/paper notes <id>                         List all notes for a paper
/paper notes --search <keywords>          Search notes across entire library
/paper export <id>                        Print notes as Markdown
/paper export <id> -o notes.md            Save notes to a file
```

### Discover & Synthesize

```
/paper related <id>                       Find related papers (with reasons)
/paper graph                              Full library network overview
/paper graph <topic>                      Topic-filtered network view
/paper survey                             Overview of entire library
/paper survey <topic>                     Survey draft focused on a topic
```

### Config

```
/paper config                             Show library location and stats
/paper config --set-lib-dir <path>        Move library to a custom directory
```

---

## How it works

**Repository layout:**

```
zpaper/
├── src/zpaper/          # Python package
│   ├── cli.py           # CLI entry point — all subcommands
│   ├── library.py       # SQLite database + PDF metadata extraction
│   ├── search.py        # arXiv API search + PDF download
│   ├── reader.py        # PDF text extraction + section detection
│   └── graph.py         # Similarity scoring + topic clustering
├── skill/
│   └── skill.md         # Claude Code skill definition
├── docs/
│   ├── PRD.md           # Product requirements document (EN)
│   └── PRD.zh.md        # Product requirements document (ZH)
├── scripts/
│   └── install.sh       # One-command installer
├── pyproject.toml       # Package metadata + `paper` CLI entrypoint
├── README.md
└── README.zh.md
```

**Runtime layout (after install):**

```
~/.claude/skills/paper/
└── skill.md             # Tells Claude how to invoke the tools

~/.scholarmind/
├── library.db           # SQLite database (papers + notes)
└── pdfs/                # Downloaded PDFs
```

**Architecture:** The Python scripts handle all I/O — database reads/writes, PDF parsing, arXiv API calls. Claude handles all reasoning — summarization, deep reading, survey writing, network analysis. No separate LLM API key needed; it all runs through your existing Claude Code session.

**Similarity algorithm:** Paper-to-paper relatedness is computed locally using TF-IDF-weighted token overlap across abstracts, titles, and keyword fields, with bonus weight for shared user tags. No vector database or embeddings required.

---

## Paper IDs

Each paper gets a stable ID:

| Format | When assigned |
|---|---|
| `arxiv:2301.12345` | Papers imported via arXiv ID or URL |
| `local:abc123def` | Local PDFs with no detected arXiv ID |

Use these IDs in commands, e.g. `/paper read arxiv:1706.03762`.

---

## PRD

The full product requirements document that drove this implementation is in [`PRD.md`](PRD.md).

---

## License

MIT
