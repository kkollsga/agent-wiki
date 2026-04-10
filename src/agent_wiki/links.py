"""Wiki link parsing, resolution, graph building, and rewriting."""

import re
from pathlib import Path

from agent_wiki._types import WikiLink

WIKI_LINK_RE = re.compile(r"\[\[([^\]|]+?)(?:\|([^\]]+?))?\]\]")


def parse_links(text: str) -> list[WikiLink]:
    """Extract all wiki-links from markdown text.

    Returns WikiLink objects with target, optional display text,
    and character offsets for rewriting.
    """
    return [
        WikiLink(
            target=m.group(1).strip(),
            display=m.group(2).strip() if m.group(2) else None,
            start=m.start(),
            end=m.end(),
        )
        for m in WIKI_LINK_RE.finditer(text)
    ]


def parse_link_targets(text: str) -> list[str]:
    """Extract just the target strings from all wiki-links in text."""
    return [m.group(1).strip() for m in WIKI_LINK_RE.finditer(text)]


def build_name_index(root: Path) -> dict[str, Path]:
    """Build a mapping from page name (stem) to file path.

    Scans all .md files under root. In Obsidian, links resolve
    by filename stem. If stems collide, both entries are kept
    (last one wins — but this wiki has unique stems).
    """
    index: dict[str, Path] = {}
    for md_file in sorted(root.rglob("*.md")):
        # Skip hidden directories
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue
        index[md_file.stem] = md_file
    return index


def resolve_link(link_target: str, name_index: dict[str, Path]) -> Path | None:
    """Resolve a wiki-link target to a file path.

    1. Try exact stem match
    2. Try path suffix match (for targets like "topics/Sand Injectites")
    3. Return None if unresolvable
    """
    # Direct stem match
    if link_target in name_index:
        return name_index[link_target]

    # Path suffix match — strip .md if present
    target_clean = link_target.removesuffix(".md")
    for stem, path in name_index.items():
        if str(path).endswith(target_clean + ".md"):
            return path

    return None


def find_backlinks(page_name: str, root: Path) -> list[Path]:
    """Find all .md files under root that contain a wiki-link to page_name."""
    pattern = re.compile(r"\[\[" + re.escape(page_name) + r"(?:\|[^\]]+)?\]\]")
    results: list[Path] = []

    for md_file in root.rglob("*.md"):
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue
        text = md_file.read_text(encoding="utf-8")
        if pattern.search(text):
            results.append(md_file)

    return sorted(results)


def build_link_graph(root: Path) -> dict[Path, list[str]]:
    """Build a complete link graph: each .md file mapped to its outbound link targets."""
    graph: dict[Path, list[str]] = {}

    for md_file in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue
        text = md_file.read_text(encoding="utf-8")
        graph[md_file] = parse_link_targets(text)

    return graph


def rewrite_links(text: str, old_name: str, new_name: str) -> str:
    """Rewrite wiki-links: [[old_name]] → [[new_name]], preserving display text.

    For [[old_name|display]], becomes [[new_name|display]].
    """

    def _replace(m: re.Match) -> str:
        target = m.group(1).strip()
        display = m.group(2)
        if target == old_name:
            if display:
                return f"[[{new_name}|{display.strip()}]]"
            return f"[[{new_name}]]"
        return m.group(0)

    return WIKI_LINK_RE.sub(_replace, text)


def extract_section_links(text: str, section_name: str) -> list[str]:
    """Extract wiki-link targets from a specific ## section.

    Finds the section by heading, reads until the next ## or end of file,
    and returns all wiki-link targets within that section.
    """
    pattern = re.compile(
        rf"^## {re.escape(section_name)}\s*\n(.*?)(?=\n## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    m = pattern.search(text)
    if not m:
        return []
    return parse_link_targets(m.group(1))
