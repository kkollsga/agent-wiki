"""Minimal YAML frontmatter parser for Obsidian-style markdown.

No PyYAML dependency — uses regex for the simple patterns found in wiki pages.
"""

import re

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_LIST_RE = re.compile(r"^\[(.+)\]$")
_WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter from markdown text.

    Returns (metadata_dict, body_text_without_frontmatter).
    If no frontmatter found, returns ({}, original_text).
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text

    yaml_block = m.group(1)
    body = text[m.end():]
    meta: dict = {}

    for line in yaml_block.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        colon_idx = line.find(":")
        if colon_idx < 0:
            continue

        key = line[:colon_idx].strip()
        val_raw = line[colon_idx + 1:].strip()

        # Parse value
        meta[key] = _parse_value(val_raw)

    return meta, body


def _parse_value(val: str):
    """Parse a YAML value string into a Python type."""
    if not val:
        return ""

    # Quoted string
    if (val.startswith('"') and val.endswith('"')) or (
        val.startswith("'") and val.endswith("'")
    ):
        return val[1:-1]

    # YAML list: [item1, item2]
    list_match = _LIST_RE.match(val)
    if list_match:
        items = list_match.group(1).split(",")
        return [item.strip().strip("'\"") for item in items]

    # Integer
    try:
        return int(val)
    except ValueError:
        pass

    # Boolean
    if val.lower() in ("true", "yes"):
        return True
    if val.lower() in ("false", "no"):
        return False

    return val


def serialize_frontmatter(meta: dict) -> str:
    """Serialize a metadata dict to a YAML frontmatter block."""
    lines = ["---"]
    for key, val in meta.items():
        lines.append(f"{key}: {_serialize_value(val)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _serialize_value(val) -> str:
    """Serialize a Python value to YAML."""
    if isinstance(val, list):
        items = ", ".join(str(v) for v in val)
        return f"[{items}]"
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str):
        if "[[" in val or '"' in val or ":" in val:
            return f'"{val}"'
        return val
    return str(val)


def extract_parent_link(meta: dict) -> str | None:
    """Extract the wiki-link target from the parent field.

    Handles: parent: "[[Sand Injectites]]" -> "Sand Injectites"
    """
    parent = meta.get("parent")
    if not parent:
        return None
    m = _WIKILINK_RE.search(str(parent))
    return m.group(1) if m else None
