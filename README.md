# agent-wiki

**Toolkit for building LLM-maintained wikis.** Handles the plumbing — link management, linting, file operations, document conversion, and agent coordination — so LLMs focus on content.

Based on the [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern by Andrej Karpathy: instead of RAG (re-deriving knowledge on every query), the LLM **incrementally builds and maintains a persistent wiki** — a structured, interlinked collection of markdown files. The wiki is a compounding artifact: cross-references are already there, contradictions already flagged, synthesis already current. You curate sources and ask questions; the LLM does the bookkeeping.

## Install

```bash
pip install agent-wiki
```

## Quick Start

```python
from agent_wiki import WikiRoot

wiki = WikiRoot("/path/to/wiki")

# Health check — find broken links, missing backlinks, orphan pages
issues = wiki.lint()

# Move a page and auto-update every [[link]] across the wiki
wiki.move("topics/Old Name.md", "topics/New Name.md")

# Convert a PDF to structured markdown with images
wiki.convert_pdf("paper.pdf", "processed/paper.md", max_dpi=150)

# Find all pages linking to a topic
wiki.backlinks("Sand Injectites")

# Search for a concept across all pages
wiki.find_references("polygonal fault")

# Wiki statistics
wiki.stats()
```

## CLI

Every operation is also available from the command line — designed for AI agents calling via Bash.

```bash
# Lint
agent-wiki --root wiki/ lint
agent-wiki --root wiki/ lint --json          # structured output for agents

# File operations (auto-updates all links)
agent-wiki --root wiki/ move old.md new.md
agent-wiki --root wiki/ merge source.md target.md
agent-wiki --root wiki/ rename "Old Name" "New Name"

# Document conversion
agent-wiki --root wiki/ convert pdf paper.pdf processed/paper.md --max-dpi 150

# Search
agent-wiki --root wiki/ backlinks "Page Name"
agent-wiki --root wiki/ find-references "some concept"
agent-wiki --root wiki/ stats
```

Use `--json` on any command for machine-readable output.

## Features

### Link Management

Obsidian-style `[[wiki-links]]` with full support for `[[target|display text]]`. The library builds a link graph, resolves links by filename stem (Obsidian's shortest-unique-path matching), and rewrites links automatically when files move.

```python
from agent_wiki.links import parse_links, find_backlinks, rewrite_links

links = parse_links("See [[Topic A]] and [[Topic B|related topic]]")
# → [WikiLink(target="Topic A", ...), WikiLink(target="Topic B", display="related topic", ...)]

rewrite_links(text, "Old Name", "New Name")
# → updates [[Old Name]] → [[New Name]], preserves [[Old Name|display]] → [[New Name|display]]
```

### Linting

Automated wiki health checks that catch real problems:

| Check | Severity | What it detects |
|-------|----------|-----------------|
| Broken links | error | `[[Target]]` where no file matches |
| Broken images | error | `![](path)` where the image file doesn't exist |
| Broken anchors | warning | `[[Page#Section]]` where the heading doesn't exist in the target |
| Broken URLs | warning | Malformed external URLs; optionally validates via HTTP (`--check-urls`) |
| Parent chain | error | Topic page with missing or broken `parent:` frontmatter chain |
| Missing frontmatter | error | Required YAML fields missing per page type (Quartz-compatible) |
| Missing backlinks | warning | Topic lists source but source doesn't link back |
| Orphan pages | warning | Pages with zero inbound links |
| Missing sections | warning | Topic without `## Sources`, source without `## Topics` |
| Dispute chronology | warning | Disputed claims with dates out of order (supports callout syntax) |
| Split candidates | info | Pages exceeding 500 lines |
| Structure mismatch | warning | Folder missing its hub page |

```python
issues = wiki.lint()
for issue in issues:
    print(f"[{issue.severity.value}] {issue.file}: {issue.message}")
```

### File Operations

Move, rename, or merge pages — all `[[wiki-links]]` across the entire wiki are updated automatically.

```python
# Rename a page — finds it by name, renames file, updates all references
wiki.rename("Old Topic Name", "New Topic Name")

# Merge two pages — appends content, redirects all links, deletes source
wiki.merge("sources/duplicate.md", "sources/canonical.md")
```

### Document Conversion

PDF to structured markdown using [pymupdf4llm](https://github.com/pymupdf/RAG) — proper headings, paragraphs, tables, and extracted images. Not flat text.

```python
wiki.convert_pdf(
    "paper.pdf",
    "processed/paper.md",
    max_dpi=150,           # image resolution cap
    extract_images=True,   # images saved to img/ subfolder
)
```

Stubs for `.docx`, `.pptx`, `.xlsx` conversion are included for future implementation.

### Kanban Agent Pipeline

A filesystem-based kanban system for coordinating multiple AI agents. No database — the folder structure **is** the state. Agents communicate through task cards that move between columns.

#### Columns

```
kanban/
├── backlog/        # cards waiting for an agent to claim
├── processing/     # claimed by an agent, work in progress
├── review/         # work done, waiting for the next stage
└── done/           # completed and archived
```

#### Task Cards

Each card is a lightweight markdown file with YAML frontmatter:

```yaml
---
agent: reader|writer|reviewer     # which agent type should pick this up
model: sonnet|opus                # which model to use (default: sonnet)
status: pending|claimed
action: rewrite|merge|move|delete|rename|create  # for structural fix cards
source_file: "raw/paper.pdf"
processed_file: "processed/paper.md"
summary_file: ""                  # filled by reader → path to source page
topic_files: []                   # filled by writer → list of topic pages
created: 2024-01-01T00:00:00+00:00
claimed_at: ""
---

## Actions

Specific instructions for the agent (free-form markdown body).
```

Cards flow through the pipeline by physically moving between folders. An agent "claims" a card by moving it from `backlog/` to `processing/` (atomic filesystem operation — prevents race conditions). When done, it moves the card to `review/` with the next agent type set.

#### The Four-Agent Pipeline

```
raw/paper.pdf
  → kanban_process: converts PDF to markdown, creates card (agent: reader)
    → Reader (Sonnet): reads processed markdown, writes source page
      → card moves to review (agent: writer)
        → Writer (Sonnet): reads source page, writes/updates topic pages
          → card moves to review (agent: reviewer)
            → Reviewer (Opus): checks quality, tree placement, citations
              ├── approve → done/
              ├── send back → backlog/ (agent: writer) with rewrite instructions
              └── escalate → backlog/ (agent: writer, model: opus) for complex rewrites
```

After all per-article reviews, a final **structure audit** (Opus reviewer) examines the full wiki tree and creates fix cards:

```
Structure audit
  → Creates cards: merge duplicates, move misplaced pages, create missing articles
    → Writer agents execute the fixes using agent-wiki CLI (move/merge/rename)
```

#### Orchestrator Role

The **orchestrator** (typically an Opus-level agent or the main Claude Code session) coordinates the pipeline but never writes or reviews content itself:

1. Runs `kanban_process` to convert new PDFs
2. Spawns reader agents (max 5 parallel)
3. Spawns writer agents (respects `model:` field on cards)
4. Spawns reviewer agents (always Opus)
5. Spawns structure audit reviewer
6. Executes fix cards
7. Updates `index.md`, `log.md`, runs lint

#### Python API

```python
from agent_wiki.kanban import create_card, claim, complete, list_cards

# Batch: scan for new files, convert, create task cards — one call
cards = wiki.kanban_process(input_dir="raw/")

# Agent claims work (atomic move)
card = claim("kanban/backlog/paper.md", "kanban/processing/")

# Agent finishes — move to next stage
complete("kanban/processing/paper.md", "kanban/review/", agent="writer")

# List cards filtered by column and agent type
cards = list_cards("kanban/", column="backlog", agent="reader")

# Recover cards stuck in processing (agent crashed)
from agent_wiki.kanban import recover_stale
recover_stale("kanban/processing/", "kanban/backlog/", max_age_minutes=30)
```

## Project Layout

`agent-wiki init` creates the full project structure. The wiki vault (`wiki/`) is an Obsidian vault that can be published directly with Quartz.

```
my-wiki-project/
├── raw/                    # source PDFs (immutable — never modified by agents)
│   └── completed/          # originals moved here after processing
├── wiki/                   # ← the Obsidian vault / Quartz site (WikiRoot)
│   ├── index.md            # root page — links all top-level topics
│   ├── log.md              # chronological activity log
│   ├── processed/          # auto-generated markdown from PDFs (with images)
│   │   └── img/            # extracted figures, organized by paper
│   ├── sources/            # one page per ingested paper
│   │   └── Topic Area/     # grouped by top-level topic
│   └── topics/             # synthesized knowledge pages (the core)
│       └── Topic Area/     # folder = breadcrumb level in Quartz
│           ├── Topic Area.md   # hub page (shares folder name)
│           └── Sub Topic.md    # child topic
├── kanban/                 # task cards for agent coordination
│   ├── backlog/            # waiting for an agent
│   ├── processing/         # claimed, work in progress
│   ├── review/             # done, waiting for next stage
│   └── done/               # archived
├── instructions/
│   ├── agents/             # agent prompts
│   │   ├── reader.md       # extracts findings from processed papers
│   │   ├── writer.md       # synthesizes topic pages from source pages
│   │   ├── orchestrator.md # coordinates the pipeline
│   │   └── reviewer.md     # audits quality and wiki structure
│   ├── kanban-design.md    # pipeline spec
│   └── lint.md             # audit checklist
├── docs/
│   └── publishing.md       # Quartz publishing guide
├── .claude/commands/       # slash commands for Claude Code
│   ├── ingest.md           # /ingest — full pipeline
│   ├── lint.md             # /lint — health check
│   └── review.md           # /review — structure audit
├── CLAUDE.md               # project instructions for Claude
└── SETUP.md                # first-run setup guide
```

```bash
# Initialize a new project
agent-wiki init my-project --name "My Research Wiki"
```

## The Pattern

The LLM Wiki pattern has three layers:

1. **Raw sources** — your curated documents. Immutable. The LLM reads but never modifies.
2. **The wiki** — LLM-generated markdown. Source pages, topic pages, cross-references. The LLM owns this entirely.
3. **The schema** — instructions that tell the LLM how the wiki is structured and what workflows to follow.

Four operations:

- **Ingest** — process a new source into the wiki. Reader creates a source page, writer synthesizes topic pages, reviewer audits quality and structure.
- **Review** — audit the wiki tree. Find duplicates, misplaced topics, missing articles. Create fix cards for writers.
- **Lint** — health-check the wiki. Find broken links, broken images, orphan pages, contradictions, missing cross-references.
- **Query** — answer questions from the wiki. Good answers get filed back as new pages.

The human curates sources and directs exploration. The LLM does the bookkeeping.

### Citation Traceability

Every claim in a topic page links to the specific subsection of the source page it came from:

```
[[Source Page#Reservoir Properties|Author et al. (2014)]]
```

Each source page statement links back to the original paper text:

```
- Clean sand porosity 26-30% [[Processed Filename#Results|p.Results]]
```

This creates a two-hop traceability chain: **topic page → source page subsection → original paper section**.

### Quartz Publishing

The wiki is designed for static publishing with [Quartz](https://quartz.jzhao.xyz/). All pages use Quartz-compatible frontmatter (`title`, `description`, `tags`), Obsidian wikilinks, and callout syntax. Breadcrumbs are generated from the folder hierarchy — no hardcoded navigation. See `docs/publishing.md` after init.

For the full LLM Wiki pattern description, see [Andrej Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

## Requirements

- Python 3.12+
- Dependencies: `pymupdf`, `pymupdf4llm`, `Pillow`

## License

MIT
