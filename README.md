<div align="center">

# 📚 zpaper

**Your personal research assistant, living inside [Claude Code](https://claude.ai/code).**

Import papers · Search your library · Deep-read PDFs · Take notes · Discover connections · Generate surveys

*All through natural language. No GUI. No cloud. Everything local.*

---

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Claude Code](https://img.shields.io/badge/Claude_Code-skill-CC785C?style=flat-square&logo=anthropic&logoColor=white)](https://claude.ai/code)
[![License](https://img.shields.io/badge/License-MIT-22C55E?style=flat-square)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-macOS%20%7C%20Linux-lightgrey?style=flat-square)]()

</div>

---

## ✨ Features

<table>
<tr>
<td width="50%">

**📥 Import & Organize**
- Paste an arXiv ID, URL, or local path — metadata and PDF fetched automatically
- Tag papers, track read status (`unread` / `reading` / `read`)
- Full-text search across titles, abstracts, keywords, and notes

</td>
<td width="50%">

**🌐 Discover**
- Search arXiv directly and import results in one step
- Automatically surface related papers with reasons
- Visualize your library as a timeline and connection graph

</td>
</tr>
<tr>
<td width="50%">

**🔍 Read & Understand**
- Structured summary: Background · Method · Results · Limitations
- Section-by-section deep read with comprehension checks
- Paste any term — Claude finds it in the PDF and explains it in context

</td>
<td width="50%">

**📝 Annotate & Synthesize**
- Add freeform notes to any paper, search them across your entire library
- Export notes to Markdown
- Generate a cited survey draft on any topic

</td>
</tr>
</table>

---

## 🚀 Installation

**Prerequisites:** [Claude Code](https://docs.anthropic.com/en/docs/claude-code) · Python 3.9+ · `pymupdf` · `requests`

```bash
git clone https://github.com/YOUR_USERNAME/zpaper.git
cd zpaper
bash scripts/install.sh
```

The installer does three things:

1. 📦 Installs the `zpaper` Python package (`pip install -e .`)
2. 🗄️ Creates `~/.scholarmind/` for your database and PDFs
3. 🔌 Copies the skill file to `~/.claude/skills/paper/`

> Open any Claude Code session and start with `/paper`.

---

## ⚡ Quick Start

```bash
# ── Import ──────────────────────────────────────────
/paper add 1706.03762
/paper add https://arxiv.org/abs/2310.06825
/paper add ~/Downloads/my_paper.pdf

# ── Search ──────────────────────────────────────────
/paper search "attention mechanism"
/paper web-search "vision language model survey"

# ── Read ────────────────────────────────────────────
/paper read arxiv:1706.03762                       # summarize
/paper read arxiv:1706.03762 --mode deep           # section by section

# ── Annotate ────────────────────────────────────────
/paper note arxiv:1706.03762 This is key
/paper related arxiv:1706.03762

# ── Synthesize ──────────────────────────────────────
/paper survey "transformer language model"
```

Or just talk to Claude naturally:

> 💬 *"Add the BERT paper to my library"*

> 💬 *"Summarize GPT-3 for me"*

> 💬 *"What papers do I have on diffusion models?"*

> 💬 *"Write a survey on vision-language pre-training"*

---

## 📖 Command Reference

<details>
<summary><b>📥 Import & Organize</b></summary>

```
/paper add <arxiv_id|url|path>             Import a paper
/paper list                                List all papers
/paper list --status <unread|reading|read> Filter by status
/paper search <keywords>                   Full-text search your library
/paper web-search <keywords>               Search arXiv
/paper show <id>                           Show full paper details
/paper tag <id> <tag1,tag2>                Add tags
/paper status <id> <status>                Update read status
/paper delete <id>                         Remove from library (PDF kept)
```

</details>

<details>
<summary><b>🔍 Read & Annotate</b></summary>

```
/paper read <id>                           Summarize (default)
/paper read <id> --mode deep               Deep read — full paper
/paper read <id> --mode deep --section N   Deep read — specific section
/paper sections <id>                       List detected sections
/paper explain <id> <keyword or phrase>    Find and explain a passage
/paper note <id> <text>                    Add a note
/paper notes <id>                          List notes for a paper
/paper notes --search <keywords>           Search notes across library
/paper export <id>                         Print notes as Markdown
/paper export <id> -o notes.md             Save notes to file
```

</details>

<details>
<summary><b>🗺️ Discover & Synthesize</b></summary>

```
/paper related <id>                        Find related papers (with reasons)
/paper graph                               Full library network
/paper graph <topic>                       Topic-filtered network view
/paper survey                              Overview of entire library
/paper survey <topic>                      Survey draft on a topic
```

</details>

<details>
<summary><b>⚙️ Config</b></summary>

```
/paper config                              Show library path and stats
/paper config --set-lib-dir <path>         Move library to a custom directory
```

</details>

---

## 🏗️ Architecture

**Python handles all I/O** — database reads/writes, PDF parsing, arXiv API calls.
**Claude handles all reasoning** — summarization, deep reading, survey writing, graph analysis.

No separate API key needed. Everything runs through your existing Claude Code session.

**Repository layout**

```
zpaper/
├── src/zpaper/
│   ├── cli.py           # All subcommands
│   ├── library.py       # SQLite database + metadata extraction
│   ├── search.py        # arXiv API + PDF download
│   ├── reader.py        # PDF text extraction + section detection
│   └── graph.py         # Similarity scoring + topic clustering
├── skill/
│   └── skill.md         # Claude Code skill definition
├── scripts/
│   └── install.sh       # One-command installer
└── pyproject.toml
```

**Runtime layout** (after install)

```
~/.claude/skills/paper/
└── skill.md             # Tells Claude how to invoke the tools

~/.scholarmind/
├── library.db           # Papers + notes (SQLite)
└── pdfs/                # Downloaded PDFs
```

> **Similarity algorithm:** TF-IDF-weighted token overlap across abstracts, titles, and keywords — with bonus weight for shared user tags. No embeddings or vector database required. Fully local.

---

## 🔖 Paper ID Format

Each paper gets a stable, human-readable ID:

| Format | Assigned when |
|:---|:---|
| `arxiv:2301.12345` | Imported via arXiv ID or URL |
| `local:abc123def` | Local PDFs with no detected arXiv ID |

Use these in any command — e.g. `/paper read arxiv:1706.03762`.

---

## 📄 License

[MIT](LICENSE) · Built for [Claude Code](https://claude.ai/code)
