"""Initialize a new Agent Wiki project with standard structure and instructions."""

from pathlib import Path

# ---------------------------------------------------------------------------
# CLAUDE.md — project reference card
# ---------------------------------------------------------------------------

_CLAUDE_MD = """\
# {name}

A knowledge wiki built with the [Agent Wiki](https://github.com/anthropics/agent-wiki) pattern. The LLM builds and maintains all wiki content; the human curates sources and directs exploration.

## Project Structure

```
{name}/
├── raw/                     # source documents (immutable — never modified by agents)
├── wiki/                    # the wiki (Obsidian vault / Quartz site)
│   ├── index.md             # root — links all top-level topics
│   ├── log.md               # chronological activity log
│   ├── processed/           # auto-generated markdown from sources
│   ├── sources/             # one page per ingested paper/document
│   └── topics/              # synthesized knowledge (the core)
├── kanban/                  # task cards for agent coordination
├── instructions/
│   ├── agents/              # agent prompts (reader, writer, orchestrator, reviewer)
│   ├── kanban-design.md     # pipeline design spec
│   └── lint.md              # lint checklist
├── docs/                    # reference material
│   └── publishing.md        # Quartz publishing guide
├── CLAUDE.md                # this file
└── SETUP.md                 # first-run setup instructions
```

## Tools

All wiki operations use the `agent-wiki` library:

```bash
.venv/bin/agent-wiki --root wiki/ lint                    # health check
.venv/bin/agent-wiki --root wiki/ stats                   # page/link counts
.venv/bin/agent-wiki --root wiki/ move old.md new.md      # move + update all links
.venv/bin/agent-wiki --root wiki/ merge src.md tgt.md     # merge + redirect links
.venv/bin/agent-wiki --root wiki/ backlinks "Page Name"   # find linking pages
.venv/bin/agent-wiki --root wiki/ kanban process raw/     # convert sources + create task cards
.venv/bin/agent-wiki --root wiki/ kanban status           # pipeline overview
```

## Slash Commands

- `/ingest [N]` — process sources through the kanban pipeline (reader → writer → reviewer)
- `/lint` — run wiki health check and propose fixes
- `/review` — audit wiki structure and create fix cards

## Conventions

- **Links:** Obsidian `[[wiki-links]]`. Bidirectional — sources list topics, topics list sources.
- **Citations:** Section-referenced: `[[Source Page#Subsection|Author et al. (Year)]]`
- **Navigation:** Quartz generates breadcrumbs from folder structure. No hardcoded breadcrumbs.
- **Naming:** Topic pages use Title Case with spaces. Source pages: `Author Year - Short Title.md`
- **Hierarchy:** Each top-level topic = a folder in `topics/`. Hub pages share the folder name. Tree can be 3+ levels deep.
- **Disputes:** Lead with the earlier publication. Use `> [!warning] Disputed` callout syntax.
- **Splitting:** Pages over ~500 lines or covering separable concepts get split.

## Agent Pipeline

```
raw/source.pdf
  → kanban_process: converts PDF, creates task card
    → reader agent (Sonnet): writes source page
      → writer agent (Sonnet): writes/updates topic pages
        → reviewer agent (Opus): reviews quality + tree placement
          → structure audit (Opus): full wiki tree review
```

## Detailed Instructions

- Agent roles and prompts: `instructions/agents/`
- Kanban pipeline design: `instructions/kanban-design.md`
- Lint checks: `instructions/lint.md`
- Publishing guide: `docs/publishing.md`
"""

# ---------------------------------------------------------------------------
# SETUP.md — run-once setup instructions
# ---------------------------------------------------------------------------

_SETUP_MD = """\
# {name} — First-Time Setup

Follow these steps to set up your wiki. You can ask Claude to read this file and execute the steps for you.

## Step 1: Install agent-wiki

```bash
pip install agent-wiki
```

Or if using a virtual environment:

```bash
python -m venv .venv
.venv/bin/pip install agent-wiki
```

## Step 2: Add your source documents

Place PDF files (research papers, reports, etc.) in the `raw/` folder. These are your source material — the wiki content will be synthesized from them.

```
raw/
├── Author 2020 - Paper Title.pdf
├── Author 2021 - Another Paper.pdf
└── ...
```

## Step 3: Run the ingest pipeline

Tell Claude: `/ingest`

This will:
1. Convert PDFs to markdown (with extracted images)
2. Create source pages summarizing each paper
3. Write topic pages synthesizing knowledge across papers
4. Review and audit the wiki structure

## Step 4: Review the wiki

Tell Claude: `/review`

This audits the topic tree for structural issues (duplicates, orphans, missing articles) and creates fix cards.

## Step 5: Publish (optional)

See `docs/publishing.md` for instructions on publishing with Quartz.

## After Setup

You can delete this file once setup is complete. The wiki is self-maintaining — just add new PDFs to `raw/` and run `/ingest` again.
"""

# ---------------------------------------------------------------------------
# wiki/index.md
# ---------------------------------------------------------------------------

_INDEX_MD = """\
---
title: {name}
type: index
---

# {name}

## Topics

*No topics yet. Topics will appear here as sources are ingested.*
"""

# ---------------------------------------------------------------------------
# wiki/log.md
# ---------------------------------------------------------------------------

_LOG_MD = """\
---
title: Log
type: log
---

# Log
"""

# ---------------------------------------------------------------------------
# instructions/agents/reader.md
# ---------------------------------------------------------------------------

_READER_MD = """\
# Reader Agent

You are a reader agent in a kanban pipeline. Your job: read a processed markdown file (converted from a PDF) and produce a source page for the wiki.

## Input

You receive a task card from `kanban/backlog/` with `agent: reader`. The card's `processed_file` field points to the converted markdown in `wiki/processed/`.

Read the processed file using the Read tool.

## What to Extract

Read the full paper. Pay special attention to the **abstract** and **conclusions** sections — every point in both must be captured in your source page.

Also read introduction, key results, and discussion for context. Skip methods detail unless the method itself is the contribution.

Extract:

1. **Metadata** — title, authors, date (publication date as `YYYY-MM-DD`; use `YYYY-01-01` if only the year is known), journal/conference, DOI
2. **Description** — one sentence summarizing the paper's main contribution (goes in the `description` frontmatter field)
3. **Key findings** — cover ALL points from the abstract AND conclusions. Include specific data. Include caveats and stated limitations.
4. **Topics/concepts** — specific concepts covered (3-10 topics)
5. **Locations/settings** — with context
6. **Key figures** — map figure references to actual extracted images (see below)

## Figure-to-Image Mapping

The processed markdown contains extracted images with paths like `processed/img/<paper>/0015-02.png` where `0015` is the page number and `02` is the image index on that page.

When the paper text references a figure, map it to the actual image file by checking which page the figure is discussed near. In the source page, reference the actual image path, not the paper's figure number.

If you cannot confidently map a figure to an image file, note it as: `(Fig. N — image not mapped)`

## Topic Selection

Limit to **3-10 topics** per source page. These should be concept-level, reusable across papers.

Before suggesting topics:
- Read `wiki/index.md` to see what topics already exist
- Prefer existing topic names over creating new ones
- Only propose a new topic if the concept genuinely doesn't fit any existing page

## Section-Referenced Backlinks

Obsidian (and Quartz) supports linking to a specific section of a page using `[[Page Name#Section Name]]`. We use this for **two levels of traceability**:

### 1. Backlinks to the processed paper

**Every factual statement in Key Contributions must end with a backlink to the relevant section of the processed markdown file.** This links the claim back to the original paper text.

```markdown
- The system shows compensationally stacked architecture [[Processed Filename#Results|p.Results]]
- Quality ranges from 26-30% in clean intervals [[Processed Filename#Discussion|p.Discussion]]
```

The `p.` prefix distinguishes processed-file references from source-page section references.

### 2. Thematic subsections for writer traceability

**Organize Key Contributions under thematic `###` subsections** (3-8 per paper). Group related findings under a descriptive heading. Name subsections by concept, not by paper structure.

The writer agent uses `[[Source Page#Subsection|Author et al. (Year)]]` when citing specific claims in topic pages.

## Quartz-Ready Format

All pages must be publishable via Quartz. Follow these rules:

- **Frontmatter:** Include `title`, `description`, `tags`, `date`, and `doi` (see template).
- **No hardcoded breadcrumbs.** Quartz generates breadcrumbs from folder structure.
- **Images:** Use standard markdown `![alt](path)`. Paths relative to wiki root.
- **Callouts:** Use Obsidian callout syntax for caveats or important notes.

## Output

Create a source page at `wiki/sources/<Top-Level Topic>/Author Year - Short Title.md`:

```markdown
---
title: "Full Paper Title"
description: "One-sentence summary of the paper's main contribution"
authors: [Last1, Last2]
date: 2015-01-01
tags: [relevant, topic, tags]
doi: "10.xxxx/xxxxx"
type: source
file: "[[Processed Filename]]"
---

# Short Title

**Authors:** Last1 & Last2 (Year)
**Full text:** [[Processed Filename]]
**Journal:** Journal Name, Volume, Pages
**DOI:** [https://doi.org/10.xxxx/xxxxx](https://doi.org/10.xxxx/xxxxx)

## Key Contributions

### Subsection Name A
- Factual statement with specific data [[Processed Filename#Paper Section|p.Paper Section]]

### Subsection Name B
- Another statement [[Processed Filename#Discussion|p.Discussion]]

## Key Figures

- ![Description](processed/img/<paper>/0003-01.png) — significance

## Locations / Settings

- **Location Name** — context, role in study

## Topics

- [[Topic A]] — brief note (key subsections: [[#Subsection Name A]])
- [[Topic B]] — brief note (key subsections: [[#Subsection Name B]])
```

## Rules

- Read the processed markdown — do NOT read the original PDF
- Do NOT write topic pages — that's the writer agent's job
- Do NOT update index.md or log.md — the orchestrator handles that
- Cover ALL points from both abstract and conclusions — completeness is critical
- Limit to 3-10 topics, prefer existing topic names
"""

# ---------------------------------------------------------------------------
# instructions/agents/writer.md
# ---------------------------------------------------------------------------

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

1. **Read the current page first** — understand what's already there
2. **Integrate naturally** — weave new information where it logically belongs. Don't append at the bottom. The page should read as a coherent synthesis.
3. **Add the new source to `## Sources`**
4. **Update inline citations** wherever new information was integrated

### If the topic page doesn't exist:

Create it following the Quartz-ready template:

```markdown
---
title: Topic Name
description: "One-sentence summary of what this topic covers"
parent: "[[Parent Topic]]"
tags: [relevant, topic, tags]
type: topic
---

Synthesized content with linked citations.

## See Also

- [[Related Topic]]

## Sources

- [[Source Page Name#Relevant Subsection|Author et al. (Year)]]
```

**Note:** Do NOT add hardcoded breadcrumbs. Quartz generates breadcrumbs from the folder structure.

## Writing Style

### Depth and Detail

Write for a **specialist reader** — someone who will use this wiki as a working reference. Include:

- **Specific data:** measurements, ranges, counts, percentages, depths, dimensions. If the source page gives numbers, put them in the topic page.
- **Named examples:** specific names, identifiers, locations. Concrete over abstract.
- **Mechanistic explanations:** don't just state what was found — explain *why* and *how*. Connect observations to underlying processes.
- **Quantified comparisons:** when contrasting features, give the numbers.

### Varying section length — write like a human

**This is critical.** Do NOT write every section to the same length. Real written text has natural variation:

- A **central or complex topic** with rich data deserves 2-4 paragraphs.
- A **simple clarification** or definition may need only 3-5 sentences.
- A **brief but important note** can be just 1-2 sentences folded into a nearby section.

**Do not pad short sections to match long ones.** Let the content dictate the length.

### Narrative flow

Write as a **coherent synthesis**, not a paper-by-paper summary. Each topic page should tell a story about the concept — its definition, how it works, where it's observed, why it matters, and what's still debated. The reader should learn about the *topic*, not about individual papers.

### Citation Format — Obsidian Backlinks with Section References

**All citations must be Obsidian wiki-links** using a **section reference** to point directly to the relevant subsection of the source page's Key Contributions:

```
[[Source Page Name#Subsection Name|Author et al. (Year)]]
```

If the source page does not have subsections (legacy format), fall back to a plain page link:
```
[[Source Page Name|Author et al. (Year)]]
```

**Never use plain-text citations** like `(Author, Year)`. Every citation must be a `[[link|display]]`.

### What NOT to write

- Generic introductory sentences that could apply to any topic
- **Uniform section lengths** — if every section is 2 paragraphs, the article reads like a machine wrote it
- Unsupported claims without a linked citation
- Paper-by-paper summaries ("Author A found X. Author B found Y.")

## Quartz-Ready Format

- **Frontmatter:** Include `title`, `description`, `tags`, and `type`.
- **No hardcoded breadcrumbs.** Quartz generates breadcrumbs from folder structure.
- **Callouts:** Use Obsidian callout syntax for disputes, caveats, and important notes.
- **Images:** Use standard markdown `![alt](path)` with a caption line. Paths relative to wiki root.
- **Tags:** Choose 3-6 lowercase tags per page.

## Handling Contradictions

When the new source contradicts existing content, keep both views. **Chronological order matters** — lead with the earlier publication. Use a callout:

```markdown
> [!warning] Disputed
> [[Earlier Source#Section|Earlier Author (Year)]] argued X based on evidence Y.
> [[Later Source#Section|Later Author (Year)]] challenged this, presenting Z.
> The discrepancy may reflect...
```

## Structural Operations (from reviewer cards)

When a kanban card has an `action` field, you are executing a structural fix. **Always use the `agent-wiki` CLI** — it updates all wiki-wide references automatically.

```bash
.venv/bin/agent-wiki --root wiki/ move "old/path.md" "new/path.md"
.venv/bin/agent-wiki --root wiki/ merge "source.md" "target.md"
.venv/bin/agent-wiki --root wiki/ rename "Old Name" "New Name"
```

After structural operations, update affected pages' frontmatter and `## See Also` sections.

## Rules

- Do NOT modify the source page — the reader agent wrote it
- Do NOT modify processed files — they are auto-generated
- Do NOT update index.md or log.md — the orchestrator handles that
- Maintain bidirectional links: if you add a source to a topic's `## Sources`, the source page must already list that topic in its `## Topics`
- Do NOT add hardcoded breadcrumbs — Quartz generates them from folder structure
- **Always use `agent-wiki` CLI for moves/merges/renames**
"""

# ---------------------------------------------------------------------------
# instructions/agents/orchestrator.md
# ---------------------------------------------------------------------------

_ORCHESTRATOR_MD = """\
# Orchestrator Agent

You are the orchestrator. You manage the kanban pipeline, spawn agents, and coordinate the flow. **You do NOT review articles yourself** — you spawn reviewer agents for that.

## CLI Setup

The `agent-wiki` CLI is installed in the project venv. **Always use the venv path:**

```bash
.venv/bin/agent-wiki --root wiki/ <command>
```

## Pipeline

### Step 1: Process new files

```bash
.venv/bin/agent-wiki --root wiki/ kanban process raw/
.venv/bin/agent-wiki --root wiki/ kanban status
```

### Step 2: Spawn reader agents (max 5 parallel)

```bash
.venv/bin/agent-wiki --root wiki/ kanban list --column backlog --agent reader
```

For each card (up to 5 at a time):

1. Claim the card (move to processing)
2. Spawn a **Sonnet** agent with `instructions/agents/reader.md` as its prompt
3. Tell the agent which `processed_file` to read

When a reader agent returns:
- Update the card's `summary_file` field
- Move the card to `kanban/review/` with `agent: writer`

### Step 3: Spawn writer agents (max 5 parallel)

For each card (up to 5 at a time):

1. Claim the card (move to processing)
2. Check the card for `model:` field — use the specified model (default: **Sonnet**)
3. Spawn the agent with `instructions/agents/writer.md` as its prompt

When a writer agent returns:
- Update the card's `topic_files` field
- Move the card to `kanban/review/` with `agent: reviewer`

### Step 4: Spawn reviewer agents

For each card with `agent: reviewer`, spawn an **Opus** reviewer agent. The reviewer can:

1. **Approve** → move card to `kanban/done/`
2. **Send back** → create a new card with `agent: writer` and rewrite instructions
3. **Escalate** → create a card with `model: opus` for complex rewrites

### Step 5: Structure audit

After all per-article reviews, spawn one **Opus** reviewer for a full wiki tree audit:
- Runs lint and stats
- Evaluates hierarchy, duplicates, missing articles
- Creates kanban fix cards

### Step 6: Execute fix cards

Process the reviewer's cards (max 5 parallel, respecting `model:` field). Priority order: moves, merges, creates, renames, rewrites.

### Step 7: Wrap up

1. Update `wiki/index.md` — reflect the final topic structure
2. Update `wiki/log.md` — append ingest entry
3. Update `wiki/sources-status.md` — mark processed papers as `[x]`
4. Run lint:

```bash
.venv/bin/agent-wiki --root wiki/ lint
.venv/bin/agent-wiki --root wiki/ stats
```

## Quartz-Ready Format

All wiki markdown must be publishable via Quartz:

- **Frontmatter:** Every page needs `title`, `description`, and `tags`. Source pages also need `date`, `authors`, `doi`.
- **No hardcoded breadcrumbs.** Quartz generates from folder structure.
- **Section-referenced citations:** `[[Source#Section|Author (Year)]]`. Source pages trace to `[[Processed#Section|p.Section]]`.
- **Callouts** for disputes and important notes.
- **Images** relative to wiki root (`processed/img/...`).

## Rules

- Max **5 agents** in parallel at any time
- Use `model: "sonnet"` for reader and writer agents (default)
- Use `model: "opus"` for reviewer agents and escalated writer cards
- You (orchestrator) **coordinate** — you do NOT write or review content
"""

# ---------------------------------------------------------------------------
# instructions/agents/reviewer.md
# ---------------------------------------------------------------------------

_REVIEWER_MD = """\
# Reviewer Agent

You are a wiki reviewer. You operate in two modes depending on what the orchestrator asks:

1. **Article review** — evaluate specific topic pages just written by a writer agent
2. **Structure audit** — full wiki tree review after all articles are written

**You are an Opus agent.**

---

## Mode 1: Article Review

When given specific `topic_files` to review:

### What to check

1. **Content quality** — coherent synthesis? Specific data, named examples, mechanistic explanations?
2. **Citations** — section-referenced (`[[Source#Section|Author (Year)]]`)? Chronologically ordered?
3. **Backlinks** — source ↔ topic bidirectional?
4. **Tree placement** — does this article belong in its current folder? Overlap with siblings?
5. **Quartz-ready** — frontmatter has `title`, `description`, `tags`; no hardcoded breadcrumbs; callouts for disputes

### Decisions

- **Approve** → tell the orchestrator to move the card to `kanban/done/`
- **Send back** → create a card in `kanban/backlog/` with `agent: writer` and specific rewrite instructions
- **Escalate** → set `model: opus` on the card if the rewrite is too complex for Sonnet

---

## Mode 2: Structure Audit

### Goal

The wiki should be a **learning resource**: broad concepts at the top, specific sub-topics nested below, hub pages at each branching point. **The tree can be 3+ levels deep.**

### Steps

1. Run `.venv/bin/agent-wiki --root wiki/ lint` and `stats`
2. Read `wiki/index.md` and every topic page
3. Read source pages' `## Topics` sections for coverage gaps
4. Evaluate: hierarchy, duplicates, orphans, missing articles, folder structure
5. Create kanban cards in `kanban/backlog/` for fixes

### Card actions

- **`create`** — missing article. List which source pages the writer should use.
- **`merge`** — combine near-duplicates. Writer uses `agent-wiki merge`.
- **`move`** — relocate page. Writer uses `agent-wiki move`.
- **`rewrite`** — restructure content.
- **`rename`** — change title/filename. Writer uses `agent-wiki rename`.
- **`delete`** — remove page (redirect links first).

### Hub pages

Each folder should have a hub page matching the folder name (e.g., `topics/Deep Water/Deep Water.md`). Hub pages need substantive overview content, not just link lists.

### Propose new index.md

After creating cards, draft what `wiki/index.md` should look like after fixes. Write this in your report — don't modify index.md directly.

## Rules

- Do NOT modify wiki pages directly — create kanban cards for the writer
- Read every topic page before making judgments
- Be specific in card actions — the writer needs exact instructions
- For `create` cards, always list which source pages to draw from
"""

# ---------------------------------------------------------------------------
# instructions/lint.md
# ---------------------------------------------------------------------------

_LINT_MD = """\
# Lint — Wiki Health Check

Run `.venv/bin/agent-wiki --root wiki/ lint` to detect issues automatically.

## Automated Checks

The tool catches: broken links, broken images, broken anchors, malformed URLs, missing frontmatter, orphan pages, missing backlinks, missing sections, dispute chronology, split candidates, and structure mismatches.

## Additional Manual Checks

Beyond what the tool catches, review:

### Topic Hierarchy

- Redundant scoping in names (e.g., "X in Y Systems" when the wiki is about Y)
- Child topics at the wrong level — ask "would a textbook put this as a subsection?"
- Topics that exist only because one source framed things that way
- Hub pages that are too thin (<50 lines) or are just link lists
- Singleton folders with only one page — merge into parent

### Content Quality

- Dispute chronology: earlier publication must come first
- Topics that should split (>500 lines or clearly separable)
- Concepts mentioned 5+ times but lacking their own page
- Thin topics with only 1 source
- Stale claims from superseded papers

### Cross-Linking

- Related topics should link via `## See Also`
- Source ↔ topic links must be bidirectional
- Parent chain must reach index

## Output

Present findings as a structured report. Wait for user approval before making changes.
"""

# ---------------------------------------------------------------------------
# instructions/kanban-design.md
# ---------------------------------------------------------------------------

_KANBAN_DESIGN_MD = """\
# Kanban Agent Pipeline

Filesystem-based kanban for coordinating AI agents. No database — the folder structure is the state.

## Columns

```
kanban/
├── backlog/        # waiting for an agent
├── processing/     # claimed by an agent
├── review/         # done, waiting for next stage
└── done/           # archived
```

## Task Cards

Lightweight markdown files with frontmatter:

```yaml
---
agent: reader|writer|reviewer
model: sonnet|opus
status: pending|claimed
action: rewrite|merge|move|delete|rename|create
source_file: "raw/paper.pdf"
processed_file: "processed/paper.md"
summary_file: ""
topic_files: []
created: 2024-01-01T00:00:00+00:00
claimed_at: ""
---

## Actions

Specific instructions for the agent.
```

## Agent Pipeline

1. `kanban_process` converts sources → creates cards in backlog (agent: reader)
2. Reader claims card → creates source page → card moves to review (agent: writer)
3. Writer claims card → writes topic pages → card moves to review (agent: reviewer)
4. Reviewer reviews → approves to done/ or sends back to backlog with actions
5. Structure audit → creates fix cards in backlog (agent: writer)

## Claiming Protocol

Agent moves card from backlog to processing (atomic). If file is gone, another agent claimed it.

## Commands

```bash
.venv/bin/agent-wiki --root wiki/ kanban process raw/     # convert + create cards
.venv/bin/agent-wiki --root wiki/ kanban status            # counts per column
.venv/bin/agent-wiki --root wiki/ kanban list              # list all cards
.venv/bin/agent-wiki --root wiki/ kanban recover           # unstick crashed agents
```
"""

# ---------------------------------------------------------------------------
# .claude/commands/ingest.md
# ---------------------------------------------------------------------------

_INGEST_CMD = """\
# Wiki Ingest

Process pending sources into wiki articles using the kanban pipeline.

**Target:** $ARGUMENTS (default: all new files in raw/)

## Instructions

1. Read `CLAUDE.md` for project overview.
2. Read `instructions/agents/orchestrator.md` for your workflow.
3. Run `kanban_process` to convert any new sources and create task cards.
4. Follow the pipeline: spawn reader agents, then writer agents, then reviewer agents.
5. **After all agents finish**, run a structure audit (spawn reviewer in audit mode).
6. Execute any fix cards the reviewer creates.
7. Update index.md, log.md, and run lint.

Agent prompts: `instructions/agents/reader.md`, `writer.md`, `orchestrator.md`, `reviewer.md`.
"""

# ---------------------------------------------------------------------------
# .claude/commands/lint.md
# ---------------------------------------------------------------------------

_LINT_CMD = """\
# Wiki Lint

Run a health check on the wiki structure and content.

## Instructions

1. Read `instructions/lint.md` for the full checklist.
2. Run `.venv/bin/agent-wiki --root wiki/ lint` for automated checks.
3. Read `wiki/index.md` to understand the current topic tree.
4. Present a structured report with proposed fixes.
5. Wait for user approval before making any changes.
"""

# ---------------------------------------------------------------------------
# .claude/commands/review.md
# ---------------------------------------------------------------------------

_REVIEW_CMD = """\
# Wiki Review

Audit wiki structure and create fix cards for the writer agent.

**Scope:** $ARGUMENTS (default: full wiki)

## Instructions

1. Read `instructions/agents/reviewer.md` for the full reviewer spec.
2. Run lint and stats to gather diagnostics.
3. Read the topic tree and evaluate hierarchy, navigation, duplicates, folder structure.
4. Create kanban cards in `kanban/backlog/` with `agent: writer` for each fix needed.
5. After creating cards, spawn writer agents to execute the fixes.
6. Update `wiki/index.md` to reflect the final structure.
"""

# ---------------------------------------------------------------------------
# docs/publishing.md — Quartz publishing guide
# ---------------------------------------------------------------------------

_PUBLISHING_MD = """\
# Publishing with Quartz

This wiki is designed to be published as a static site using [Quartz](https://quartz.jzhao.xyz/).

## Frontmatter Fields

Quartz uses these frontmatter fields:

| Field | Used For | Required |
|---|---|---|
| `title` | Page heading, Explorer, breadcrumbs | Yes |
| `description` | Link previews, social cards, search | Yes |
| `tags` | Tag index pages, graph filtering | Yes |
| `date` | Sorting, Recent Notes | Source pages |
| `aliases` | Alternative names for wikilink resolution | Optional |
| `draft` | `draft: true` excludes from published site | Optional |

## Supported Syntax

Quartz supports full Obsidian-flavored markdown:

- **Wikilinks:** `[[Page]]`, `[[Page|Display]]`, `[[Page#Section]]`, `[[Page#Section|Display]]`
- **Embeds:** `![[Page]]`, `![[image.png]]`, `![[image.png|100x200]]`
- **Callouts:** `> [!note]`, `> [!warning]`, `> [!tip]` (12 types, collapsible, nestable)
- **Images:** Standard markdown `![alt](path)` with paths relative to wiki root

## Breadcrumbs

Quartz generates breadcrumbs from **folder structure**, not from frontmatter. A file at `topics/Deep Water/Channels.md` renders: `Home > Deep Water > Channels`.

**Do NOT add hardcoded breadcrumbs** like `*[[index]] > [[Parent]] > Topic*`.

## Folder Structure

- Hub pages should share their folder name: `topics/Deep Water/Deep Water.md`
- Quartz auto-generates listing pages for folders
- Create `index.md` only at the wiki root, not in topic folders

## Graph View

Built automatically from wikilinks. Bidirectional links (sources ↔ topics) produce a rich graph.

## Publishing

```bash
# Install Quartz
git clone https://github.com/jackyzha0/quartz.git
cd quartz
npm i
npx quartz create

# Point to your wiki content
# Set contentFolder in quartz.config.ts to your wiki/ directory

# Build and preview
npx quartz build --serve

# Deploy
npx quartz sync
```

## Excluding Content

In `quartz.config.ts`, use `ignorePatterns` to exclude non-wiki content:

```ts
ignorePatterns: ["processed/", "kanban/", "instructions/"]
```

**Important:** Non-markdown files (images, PDFs) are always emitted publicly.
"""

# ---------------------------------------------------------------------------
# .gitignore
# ---------------------------------------------------------------------------

_GITIGNORE = """\
.venv/
__pycache__/
raw/completed/
kanban/
"""

# ---------------------------------------------------------------------------
# Init function
# ---------------------------------------------------------------------------


def init_project(path: str | Path, name: str | None = None) -> Path:
    """Initialize a new Agent Wiki project with standard structure.

    Creates:
        - raw/                          empty, for source documents
        - wiki/                         with index.md, log.md
        - wiki/processed/               empty
        - wiki/sources/                 empty
        - wiki/topics/                  empty
        - kanban/                       backlog, processing, review, done
        - instructions/agents/          reader.md, writer.md, orchestrator.md, reviewer.md
        - instructions/                 kanban-design.md, lint.md
        - docs/                         publishing.md
        - .claude/commands/             ingest.md, lint.md, review.md
        - CLAUDE.md                     project reference card
        - SETUP.md                      first-run setup instructions
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
    _write(root / "instructions/agents/reviewer.md", _REVIEWER_MD)
    _write(root / "instructions/kanban-design.md", _KANBAN_DESIGN_MD)
    _write(root / "instructions/lint.md", _LINT_MD)

    # Docs
    _write(root / "docs/publishing.md", _PUBLISHING_MD)

    # Slash commands
    _write(root / ".claude/commands/ingest.md", _INGEST_CMD)
    _write(root / ".claude/commands/lint.md", _LINT_CMD)
    _write(root / ".claude/commands/review.md", _REVIEW_CMD)

    # Root files
    _write(root / "CLAUDE.md", _CLAUDE_MD.format(name=name))
    _write(root / "SETUP.md", _SETUP_MD.format(name=name))
    _write(root / ".gitignore", _GITIGNORE)

    return root


def _write(path: Path, content: str):
    """Write file only if it doesn't exist (never overwrite)."""
    if not path.exists():
        path.write_text(content, encoding="utf-8")
