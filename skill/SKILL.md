# Paper — ScholarMind Literature Assistant

A personal literature management and reading assistant for researchers, integrated into Claude Code.

## Trigger

Use this skill when the user invokes `/paper` or asks you to:
- Import, add, or save a paper (local PDF or arXiv)
- Search their literature library or arXiv
- List, browse, tag, or manage papers
- **Read, summarize, or deep-read a paper**
- **Add, view, search, or export reading notes**

## How to Run Commands

All operations go through the Python CLI:

```bash
paper <subcommand> [args]
```

Never reconstruct logic yourself — always delegate to the script.

---

## Commands Reference

### Import & Organize

| User Says | Command to Run |
|-----------|---------------|
| "add arxiv 2301.12345" | `paper add 2301.12345` |
| "add this PDF ~/Downloads/paper.pdf" | `paper add ~/Downloads/paper.pdf` |
| "search my library for transformers" | `paper search transformers` |
| "search arXiv for diffusion models" | `paper web-search diffusion models` |
| "list my papers" | `paper list` |
| "show unread papers" | `paper list --status unread` |
| "show details of paper X" | `paper show <id>` |
| "tag paper X with survey" | `paper tag <id> survey` |
| "mark paper X as read" | `paper status <id> read` |
| "delete paper X" | `paper delete <id>` |

### Reading Modes

| User Says | Command to Run |
|-----------|---------------|
| "summarize this paper" / "read paper X" | `paper read <id>` |
| "deep read paper X" / "精读" | `paper read <id> --mode deep` |
| "next section" (during deep read) | `paper read <id> --mode deep --section <N>` |
| "what sections does paper X have" | `paper sections <id>` |
| "explain this phrase" / "I don't understand X" | `paper explain <id> <keyword or phrase>` |

### Notes

| User Says | Command to Run |
|-----------|---------------|
| "add note to paper X: <text>" | `paper note <id> <text>` |
| "save this as a note" (after summary) | `paper note <id> <summary_text> --type summary` |
| "show notes for paper X" | `paper notes <id>` |
| "search my notes for attention" | `paper notes --search attention` |
| "export notes for paper X" | `paper export <id>` |
| "export notes to file.md" | `paper export <id> -o ~/notes/paper.md` |

### Discover & Synthesize

| User Says | Command to Run |
|-----------|---------------|
| "find papers related to X" | `paper related <id>` |
| "what papers are similar to this one" | `paper related <id>` |
| "show me the literature network" | `paper graph` |
| "show connections for topic X" | `paper graph X` |
| "write a survey on X" / "综述" | `paper survey X` |
| "give me an overview of my library" | `paper survey` |

---

## Reading Mode Workflows

### Summary Mode

1. Run: `paper read <id>`
2. The script outputs the full paper text between `--- PAPER TEXT START ---` and `--- PAPER TEXT END ---`
3. **You (Claude) must generate the structured summary** with these five sections:
   - **Background & Motivation** — What problem does this solve? Why does it matter?
   - **Core Method** — The key technical contribution, explained clearly
   - **Key Results** — Main experimental findings with numbers where available
   - **Limitations** — What the authors acknowledge; what you notice
   - **Relation to Prior Work** — How it connects to or differs from related work
4. After the summary, ask: *"Want me to save this as a note, or enter deep read mode for a closer look?"*
5. If user says yes to saving: run `paper note <id> "<summary>" --type summary`

### Deep Read Mode

Two sub-modes depending on whether `--section` is provided:

**Full-text deep read** (`paper read <id> --mode deep`, no `--section`):
1. Run: `paper read <id> --mode deep`
2. The script outputs the full paper text between `--- PAPER TEXT START ---` and `--- PAPER TEXT END ---`
3. **You (Claude) must** walk through the paper in your own structure:
   - Divide the text into logical sections yourself
   - Explain each part clearly, highlight key concepts
   - Ask **one focused question** per section to check understanding
   - Wait for user's response before moving on
4. After all sections, offer a final synthesis and suggest: `paper status <id> read`

**Section-by-section deep read** (`paper read <id> --mode deep --section N`):
1. First, show available sections: `paper sections <id>`
2. Start with section 0: `paper read <id> --mode deep --section 0`
3. The script outputs one section's text between `--- SECTION TEXT START ---` and `--- SECTION TEXT END ---`
4. **You (Claude) must**:
   - Explain the section in clear language
   - Highlight key concepts or surprising claims
   - Ask **one focused question** to check user's understanding (not multiple questions at once)
   - Wait for user's response before moving on
5. When user is ready for the next section, increment `--section N` by 1
6. After each section, offer: *"Ready for the next section? Or want to add a note about something here?"*
7. If user wants to note something: `paper note <id> "<their insight>" --type insight`
8. When all sections are done, offer a final synthesis and suggest marking as read: `paper status <id> read`

**When to use which**: prefer full-text mode when section detection looks unreliable (e.g. `paper sections` returns garbled titles). Use section mode when the paper has clean detected sections and the user wants to jump to a specific one.

---

## After Commands — Response Style

Always summarize the result naturally. Don't dump raw script output verbatim.

**After add:**
> Added **Attention Is All You Need** (2017) to your library as `arxiv:1706.03762`. PDF saved. Want me to summarize it?

**After summary:**
> Here's my summary of *Attention Is All You Need*: [structured summary]. Want me to save this as a note, or go deeper on any section?

**After web-search:**
> Found 8 papers on arXiv. Top result: **[title]** (2025). Want me to import any? Just give me the number.

**After note saved:**
> Note saved for *[paper title]*. You now have N notes for this paper.

**After explain:**
> Found 2 match(es) for "scaled dot-product attention". Here's what it means: [explanation using the surrounding context]. Want to add a note about this, or keep reading?

**After related:**
> Found 3 related papers. Closest match: *[title]* (2023) — shares keywords on multi-head attention and positional encoding. Want me to add it to your library?

**After graph:**
> [Analyze the INSTRUCTION_FOR_CLAUDE output and describe the network structure to the user naturally]

**After survey:**
> [Generate the full survey draft based on INSTRUCTION_FOR_CLAUDE. After drafting, ask if user wants to expand a section or save it as a note with `/paper note <id> <text>`]

---

## Discover & Synthesize Workflows

### Related Papers (`related`)

1. Run: `paper related <id>`
2. Script outputs related papers with similarity reasons
3. **You (Claude) must**:
   - Explain *why* each paper is related in plain language (don't just repeat the "Because:" line)
   - Highlight the most intellectually interesting connection
   - Offer to import any related paper not yet in the library
   - Offer: *"Want me to show the full literature network around this topic?"*

### Graph Mode (`graph`)

1. Run: `paper graph [topic]`
2. Script outputs timeline + connection hints, ending with `INSTRUCTION_FOR_CLAUDE`
3. **You (Claude) must** analyze and describe:
   - The main research threads visible in the library
   - Key bridges between papers (which papers connect different threads)
   - Any notable chronological trends
   - Gaps: what's missing that would strengthen the collection
4. Offer: *"Want me to write a survey based on these connections?"*

### Survey Mode (`survey`)

1. Run: `paper survey [topic]`
2. Script outputs all paper metadata + user notes, ending with `INSTRUCTION_FOR_CLAUDE`
3. **You (Claude) must write a structured survey draft**:
   - **Introduction** — scope, why this topic matters
   - **Timeline & Evolution** — chronological development of ideas
   - **Main Approaches** — group papers by methodology/paradigm
   - **Comparison & Analysis** — trade-offs, open problems, conflicting findings
   - **Conclusion & Future Directions** — where the field is heading
4. Use inline citations: *(Vaswani et al., 2017)* or *[arxiv:1706.03762]*
5. Weave in the user's reading notes naturally as first-person insights
6. After the draft: *"Want me to expand any section? I can also save this draft as a note."*
7. To save: `paper note <any_relevant_id> "<draft>" --type summary`

---

## Resolving Paper IDs

Papers have IDs like `arxiv:1706.03762` or `local:abc123`. When the user refers to a paper by title or partial name:
1. Run `paper search <partial title>` to find the full ID
2. Then use the full ID in subsequent commands

---

## Error Handling

- **PDF not found**: Tell user metadata is saved, provide the source URL, offer to proceed once they download manually
- **Metadata extraction gaps**: List missing fields, suggest `/paper show <id>` to review
- **Search returns nothing**: Suggest `/paper web-search` as an alternative
- **Section detection fails**: Fall back to full-text deep read (`paper read <id> --mode deep` without `--section`), explain why
- **explain returns no matches**: Tell user no exact or fuzzy match was found, ask them to try a shorter or differently worded fragment

---

## Library Location

Default: `~/.scholarmind/`
- Database: `~/.scholarmind/library.db`
- PDFs: `~/.scholarmind/pdfs/`

Change with: `paper config --set-lib-dir <path>`
