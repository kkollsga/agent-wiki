"""Helper methods for maintaining wiki index, log, and sources status."""

import re
from datetime import datetime, timezone
from pathlib import Path

from agent_wiki.frontmatter import parse_frontmatter


def update_index(root: Path, title: str | None = None) -> Path:
    """Auto-generate index.md from the topic folder structure.

    Scans wiki/topics/ (or root/topics/) for topic pages, builds a tree
    from their parent frontmatter fields, and writes index.md.

    Args:
        root: Wiki root directory.
        title: Wiki title for the index page. Defaults to current title or root dir name.

    Returns:
        Path to the written index.md.
    """
    index_path = root / "index.md"
    topics_dir = root / "topics"

    # Read existing title if present
    if title is None and index_path.exists():
        meta, _ = parse_frontmatter(index_path.read_text(encoding="utf-8"))
        title = meta.get("title", root.name)
    elif title is None:
        title = root.name

    # Scan all topic pages
    pages: dict[str, dict] = {}  # stem → {title, parent, path}
    if topics_dir.is_dir():
        for md_file in sorted(topics_dir.rglob("*.md")):
            if any(part.startswith(".") for part in md_file.relative_to(root).parts):
                continue
            text = md_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(text)
            if meta.get("type") != "topic":
                continue

            parent_raw = meta.get("parent", "")
            parent = None
            if parent_raw:
                m = re.search(r"\[\[(.+?)\]\]", str(parent_raw))
                if m and m.group(1) != "index":
                    parent = m.group(1)

            # Extract first sentence for description
            desc = ""
            body_stripped = body.strip()
            # Skip breadcrumb line
            for line in body_stripped.split("\n"):
                line = line.strip()
                if not line or line.startswith("*[[") or line.startswith("#"):
                    continue
                desc = line[:120]
                if len(line) > 120:
                    desc += "..."
                break

            pages[md_file.stem] = {
                "title": meta.get("title", md_file.stem),
                "parent": parent,
                "desc": desc,
            }

    # Build tree
    children: dict[str | None, list[str]] = {}  # parent → [child stems]
    for stem, info in pages.items():
        parent = info["parent"]
        children.setdefault(parent, []).append(stem)

    # Render tree
    lines = [
        "---",
        f"title: {title}",
        "type: index",
        "---",
        "",
        f"# {title}",
        "",
        "## Topics",
        "",
    ]

    def _render(parent: str | None, indent: int):
        for stem in sorted(children.get(parent, [])):
            info = pages[stem]
            prefix = "  " * indent + "- "
            desc = f" — {info['desc']}" if info["desc"] else ""
            lines.append(f"{prefix}[[{stem}]]{desc}")
            _render(stem, indent + 1)

    _render(None, 0)

    if not children.get(None):
        lines.append(
            "*No topics yet. Topics will appear here as sources are ingested.*"
        )

    lines.append("")

    index_path.write_text("\n".join(lines), encoding="utf-8")
    return index_path


def append_log(
    root: Path,
    action: str,
    description: str,
    details: str = "",
) -> Path:
    """Append a formatted entry to log.md.

    Args:
        root: Wiki root directory.
        action: Action type (ingest, query, lint, split, reorganize).
        description: Short description of what was done.
        details: Multi-line details (pages created/updated, etc.).

    Returns:
        Path to log.md.
    """
    log_path = root / "log.md"

    # Create log file if it doesn't exist
    if not log_path.exists():
        log_path.write_text(
            "---\ntitle: Log\ntype: log\n---\n\n# Log\n", encoding="utf-8"
        )

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entry = f"\n## [{date}] {action} | {description}\n"
    if details:
        entry += f"\n{details.strip()}\n"

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(entry)

    return log_path


def generate_sources_status(
    root: Path,
    raw_dir: Path | None = None,
    kanban_dir: Path | None = None,
) -> Path:
    """Auto-generate sources-status.md from raw files and wiki state.

    Derives status from:
    - wiki/sources/ — if a source page exists for a file, it's [x]
    - kanban/done/ — completed cards are [x]
    - kanban/backlog|processing|review/ — in progress [~]
    - Remaining raw files — pending [ ]

    Args:
        root: Wiki root directory.
        raw_dir: Directory with source files. Defaults to root/../raw/.
        kanban_dir: Kanban directory. Defaults to root/../kanban/.

    Returns:
        Path to sources-status.md.
    """
    if raw_dir is None:
        raw_dir = root.parent / "raw"
    if kanban_dir is None:
        kanban_dir = root.parent / "kanban"

    # Collect processed stems from source pages
    sources_dir = root / "sources"
    ingested_stems: set[str] = set()
    if sources_dir.is_dir():
        for md_file in sources_dir.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            # Try to find the original file reference
            file_ref = meta.get("file", "")
            if file_ref:
                m = re.search(r"\[\[(.+?)\]\]", str(file_ref))
                if m:
                    ingested_stems.add(Path(m.group(1)).stem)

    # Collect in-progress stems from kanban
    in_progress_stems: set[str] = set()
    for col in ("backlog", "processing", "review"):
        col_dir = kanban_dir / col
        if col_dir.is_dir():
            for card in col_dir.glob("*.md"):
                in_progress_stems.add(card.stem)

    # Collect done stems from kanban
    done_dir = kanban_dir / "done"
    if done_dir.is_dir():
        for card in done_dir.glob("*.md"):
            ingested_stems.add(card.stem)

    # Scan raw directory
    status_path = root / "sources-status.md"
    lines = [
        "---",
        "title: Sources Status",
        "type: status",
        "---",
        "",
        "# Sources Status",
        "",
    ]

    if raw_dir.is_dir():
        _scan_dir(raw_dir, raw_dir, lines, ingested_stems, in_progress_stems)

    lines.append("")
    status_path.write_text("\n".join(lines), encoding="utf-8")
    return status_path


def _scan_dir(
    dir_path: Path,
    raw_root: Path,
    lines: list[str],
    ingested: set[str],
    in_progress: set[str],
):
    """Recursively scan a directory and add status entries."""
    # Skip completed directory
    if dir_path.name == "completed":
        return

    # Add section header for subdirectories
    if dir_path != raw_root:
        lines.append(f"## {dir_path.name}")
        lines.append("")

    # List files
    for f in sorted(dir_path.iterdir()):
        if f.is_dir():
            if f.name not in (
                "completed",
                ".images",
                ".extracted",
            ) and not f.name.startswith("."):
                _scan_dir(f, raw_root, lines, ingested, in_progress)
            continue

        stem = f.stem
        ext = f.suffix.lower()

        if ext in (".pptx", ".docx"):
            lines.append(f"- [-] {f.name}")
        elif ext in (".jpg", ".jpeg", ".png"):
            continue  # Skip images
        elif stem in ingested:
            lines.append(f"- [x] {f.name}")
        elif stem in in_progress:
            lines.append(f"- [~] {f.name}")
        else:
            lines.append(f"- [ ] {f.name}")

    lines.append("")
