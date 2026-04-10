"""Initialize a new Agent Wiki project with standard structure and instructions."""

from pathlib import Path

_CLAUDE_MD = """\
# {name}

A knowledge wiki built with the [Agent Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) pattern. The LLM builds and maintains all wiki content; the human curates sources and directs exploration.

## Project Structure

```
{name}/
├── raw/                     # source documents (immutable — never modified by agents)
├── wiki/                    # the wiki (Obsidian vault)
│   ├── index.md             # root — links all top-level topics
│   ├── log.md               # chronological activity log
│   ├── processed/           # auto-generated markdown from sources
│   ├── sources/             # one lightweight page per source
│   └── topics/              # synthesized knowledge (the core)
├── kanban/                  # task cards for agent coordination
├── instructions/
│   ├── agents/              # agent prompts (reader, writer, orchestrator)
│   ├── kanban-design.md     # pipeline design spec
│   └── lint.md              # lint checklist
└── docs/                    # reference material
```

## Tools

All wiki operations use the `agent-wiki` library:

```bash
agent-wiki --root wiki/ lint                              # health check
agent-wiki --root wiki/ stats                             # page/link counts
agent-wiki --root wiki/ move old.md new.md                # move + update all links
agent-wiki --root wiki/ backlinks "Page Name"             # find linking pages
agent-wiki --root wiki/ kanban process raw/               # convert sources + create task cards
agent-wiki --root wiki/ kanban status                     # pipeline overview
```

## Slash Commands

- `/ingest [N]` — process sources through the kanban pipeline (reader → writer → review)
- `/lint` — run wiki health check and propose fixes

## Conventions

- **Links:** Obsidian `[[wiki-links]]`. Bidirectional — sources list topics, topics list sources.
- **Navigation:** Every topic page has a breadcrumb: `*[[index]] > [[Parent]] > Topic*`
- **Naming:** Topic pages use Title Case with spaces. Source pages: `Author Year - Short Title.md`
- **Hierarchy:** Each top-level topic = a folder in both `topics/` and `sources/`. Hub pages share the folder name.
- **Disputes:** Lead with the earlier publication, then the later challenge. See `instructions/agents/writer.md`.
- **Splitting:** Pages over ~500 lines or covering separable concepts get split. Original becomes a hub.

## Agent Pipeline

Agents coordinate through the kanban system. See `instructions/agents/` for role-specific prompts.

```
raw/source.pdf
  → kanban_process: converts source, creates task card
    → reader agent: writes source page
      → writer agent: writes/updates topic pages
        → orchestrator: reviews, approves or sends back
```

## Detailed Instructions

- Agent roles and prompts: `instructions/agents/`
- Kanban pipeline design: `instructions/kanban-design.md`
- Lint checks: `instructions/lint.md`
"""

_INDEX_MD = """\
---
title: {name}
type: index
---

# {name}

## Topics

*No topics yet. Topics will appear here as sources are ingested.*
"""

_LOG_MD = """\
---
title: Log
type: log
---

# Log
"""

_SOURCES_STATUS_MD = """\
---
title: Sources Status
type: status
---

# Sources Status

*Add source files to `raw/` and run `/ingest` to process them.*
"""

_READER_MD = """\
# Reader Agent

You are a reader agent in a kanban pipeline. Your job: read a processed markdown file (converted from a source document) and produce a source page for the wiki.

## Input

You receive a task card from `kanban/backlog/` with `agent: reader`. The card's `processed_file` field points to the converted markdown in `wiki/processed/`.

Read the processed file using the Read tool.

## What to Extract

Focus on the key contributions — what is new or important. Not a general summary.

Extract:

1. **Metadata** — title, authors, year, publication venue
2. **Key findings** — only what is new or important
3. **Topics/concepts** — specific concepts covered
4. **Key figures** — what they show, why they matter

## Output

Create a source page at `wiki/sources/<Top-Level Topic>/Author Year - Short Title.md`:

```markdown
---
title: "Full Title"
authors: [Last1, Last2]
year: 2024
type: source
file: "[[Processed Filename]]"
---

# Short Title

**Authors:** Last1 & Last2 (Year)
**Full text:** [[Processed Filename]]

## Key Contributions

- What this source adds that isn't already in the wiki

## Topics

- [[Topic A]] — brief note on relevance
- [[Topic B]] — brief note on relevance
```

## Rules

- Read the processed markdown — do NOT read the original source file
- Do NOT write topic pages — that's the writer agent's job
- Do NOT update index.md or log.md — the orchestrator handles that
"""

_WRITER_MD = """\
# Writer Agent

You are a writer agent in a kanban pipeline. Your job: take a source page (produced by the reader agent) and write or update topic pages in the wiki.

## Input

You receive a task card with `agent: writer`. The card has:

- `processed_file` — the full converted markdown (for reference)
- `summary_file` — the source page created by the reader agent

Read both files. Also read `wiki/index.md` to understand the current topic structure.

## What to Do

For each topic listed in the source page's `## Topics` section:

### If the topic page exists:

1. **Read the current page first**
2. **Integrate naturally** — weave new information where it logically belongs. Don't append at the bottom.
3. **Add the new source to `## Sources`**
4. **Update inline citations**

### If the topic page doesn't exist:

Create it with frontmatter, breadcrumb trail, synthesized content, See Also, and Sources sections.

## Writing Style

- Write as a **coherent synthesis**, not a paper-by-paper summary
- Use inline citations: `(Author, Year)`
- The reader should learn about the *topic*, not about individual papers

## Handling Contradictions

**Chronological order matters** — lead with the earlier publication:

> **Disputed:** Earlier Author (Year) argued X. Later Author (Year) challenged this with Z. The discrepancy may reflect...

## Rules

- Do NOT modify the source page or processed files
- Do NOT update index.md or log.md
- Maintain bidirectional links (source ↔ topic)
- Every topic page must have a breadcrumb trail back to `[[index]]`
- Use `agent-wiki --root wiki/ move old.md new.md` for file moves/renames
"""

_ORCHESTRATOR_MD = """\
# Orchestrator Agent

You are the orchestrator. You manage the kanban pipeline, spawn reader and writer agents, and review their output yourself.

## Pipeline

### Step 1: Process new files

```bash
agent-wiki --root wiki/ kanban process raw/
agent-wiki --root wiki/ kanban status
```

### Step 2: Spawn reader agents (max 5 parallel)

```bash
agent-wiki --root wiki/ kanban list --column backlog --agent reader
```

For each card (up to 5 at a time):

1. Claim the card (move to processing)
2. Spawn a **Sonnet** agent with `instructions/agents/reader.md` as its prompt
3. Tell the agent which `processed_file` to read

Launch all agents in a single message (parallel). Wait for all to return.

When a reader agent returns:

- Update the card's `summary_file` field
- Move the card to `kanban/review/` with `agent: writer`

### Step 3: Spawn writer agents (max 5 parallel)

```bash
agent-wiki --root wiki/ kanban list --column review --agent writer
```

Same pattern: claim, spawn Sonnet agents, wait, update cards.

### Step 4: Review (you do this yourself)

For each completed writer card:

1. Read the topic pages listed in `topic_files`
2. Check: content quality, citations, breadcrumbs, backlinks, hierarchy
3. If approved: move card to `kanban/done/`
4. If needs work: add actions and move to `kanban/backlog/` with `agent: writer`

### Step 5: Wrap up

1. Update `wiki/index.md` — add any new top-level topics
2. Update `wiki/log.md` — append ingest entry
3. Update `wiki/sources-status.md` — mark processed sources as `[x]`
4. Run lint: `agent-wiki --root wiki/ lint`

## Rules

- Max **5 agents** in parallel
- Use `model: "sonnet"` for reader and writer agents
- You (orchestrator) are Opus — you do the review yourself
- Do NOT write source or topic pages — agents do that
"""

_LINT_MD = """\
# Lint — Wiki Health Check

Run `agent-wiki --root wiki/ lint` to detect issues automatically.

## Additional Manual Checks

Beyond what the tool catches, review:

### Topic Hierarchy

- Redundant scoping in names (e.g., "X in Y Systems" when the whole wiki is about Y)
- Child topics at the wrong level — ask "would a textbook put this as a subsection?"
- Topics that exist only because one source framed things that way
- Hub pages that are too thin (<50 lines)

### Content Quality

- Dispute chronology: earlier publication must come first
- Topics that should split (>500 lines or clearly separable)
- Concepts mentioned 5+ times but lacking their own page
- Thin topics with only 1 source

## Output

Present findings as a structured report. Wait for user approval before making changes.
"""

_KANBAN_DESIGN_MD = """\
# Kanban Agent Pipeline

Filesystem-based kanban for coordinating AI agents. No database — the folder structure is the state.

## Columns

```
wiki/kanban/
├── backlog/        # waiting for an agent
├── processing/     # claimed by an agent
├── review/         # done, waiting for next stage
└── done/           # archived
```

## Task Cards

Lightweight markdown files with frontmatter:

```yaml
---
agent: reader|writer
status: pending|claimed
source_file: "raw/paper.pdf"
processed_file: "wiki/processed/paper.md"
summary_file: ""
topic_files: []
created: 2024-01-01T00:00:00+00:00
claimed_at: ""
---
```

## Agent Pipeline

1. `kanban_process` converts sources → creates cards in backlog (agent: reader)
2. Reader claims card → creates source page → card moves to review (agent: writer)
3. Writer claims card → writes topic pages → card moves to review (agent: orchestrator)
4. Orchestrator reviews → approves to done/ or sends back to backlog with actions

## Claiming Protocol

Agent moves card from backlog to processing (atomic). If file is gone, another agent claimed it.

## Commands

```bash
agent-wiki --root wiki/ kanban process raw/     # convert + create cards
agent-wiki --root wiki/ kanban status           # counts per column
agent-wiki --root wiki/ kanban list             # list all cards
agent-wiki --root wiki/ kanban recover          # unstick crashed agents
```
"""

_GITIGNORE = """\
.venv/
__pycache__/
raw/completed/
wiki/processed/
kanban/
"""

_INGEST_CMD = """\
# Wiki Ingest

Process pending sources into wiki articles using the kanban pipeline.

**Target:** $ARGUMENTS (default: all new files in raw/)

## Instructions

1. Read `CLAUDE.md` for project overview.
2. Read `instructions/agents/orchestrator.md` for your workflow.
3. Run `kanban_process` to convert any new sources and create task cards.
4. Follow the pipeline: spawn reader agents, then writer agents, then review.
"""

_LINT_CMD = """\
# Wiki Lint

Run a health check on the wiki structure and content.

## Instructions

1. Read `instructions/lint.md` for the full checklist.
2. Run `agent-wiki --root wiki/ lint` for automated checks.
3. Read `wiki/index.md` to understand the current topic tree.
4. Present a structured report with proposed fixes.
5. Wait for user approval before making any changes.
"""


def init_project(path: str | Path, name: str | None = None) -> Path:
    """Initialize a new Agent Wiki project with standard structure.

    Creates:
        - raw/                          empty, for source documents
        - wiki/                         with index.md, log.md
        - wiki/processed/               empty
        - wiki/sources/                 empty
        - wiki/topics/                  empty
        - kanban/                       backlog, processing, review, done
        - instructions/agents/          reader.md, writer.md, orchestrator.md
        - instructions/                 kanban-design.md, lint.md
        - docs/                         empty
        - .claude/commands/             ingest.md, lint.md
        - CLAUDE.md                     project reference card
        - .gitignore

    Args:
        path: Directory to create the project in. Will be created if needed.
        name: Project name. Defaults to the directory name.

    Returns:
        The project root path.
    """
    root = Path(path).resolve()
    if name is None:
        name = root.name

    # Directories
    for d in [
        "raw",
        "wiki/processed",
        "wiki/sources",
        "wiki/topics",
        "kanban/backlog",
        "kanban/processing",
        "kanban/review",
        "kanban/done",
        "instructions/agents",
        "docs",
        ".claude/commands",
    ]:
        (root / d).mkdir(parents=True, exist_ok=True)

    # Wiki files
    _write(root / "wiki/index.md", _INDEX_MD.format(name=name))
    _write(root / "wiki/log.md", _LOG_MD)

    # Instructions
    _write(root / "instructions/agents/reader.md", _READER_MD)
    _write(root / "instructions/agents/writer.md", _WRITER_MD)
    _write(root / "instructions/agents/orchestrator.md", _ORCHESTRATOR_MD)
    _write(root / "instructions/kanban-design.md", _KANBAN_DESIGN_MD)
    _write(root / "instructions/lint.md", _LINT_MD)

    # Slash commands
    _write(root / ".claude/commands/ingest.md", _INGEST_CMD)
    _write(root / ".claude/commands/lint.md", _LINT_CMD)

    # Root files
    _write(root / "CLAUDE.md", _CLAUDE_MD.format(name=name))
    _write(root / ".gitignore", _GITIGNORE)

    return root


def _write(path: Path, content: str):
    """Write file only if it doesn't exist (never overwrite)."""
    if not path.exists():
        path.write_text(content, encoding="utf-8")
