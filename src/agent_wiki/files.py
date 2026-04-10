"""File operations — move, merge, rename with automatic link updates."""

import shutil
from pathlib import Path

from agent_wiki.links import build_name_index, rewrite_links


def move(old_path: Path, new_path: Path, root: Path) -> list[Path]:
    """Move/rename a markdown file and update all references across the wiki.

    Args:
        old_path: Current absolute path to the file.
        new_path: Destination absolute path.
        root: Wiki root directory.

    Returns:
        List of all files that were modified (including the moved file).
    """
    if not old_path.exists():
        raise FileNotFoundError(f"Source file not found: {old_path}")
    if new_path.exists():
        raise FileExistsError(f"Destination already exists: {new_path}")

    old_stem = old_path.stem
    new_stem = new_path.stem
    modified: list[Path] = []

    # Create destination directory
    new_path.parent.mkdir(parents=True, exist_ok=True)

    # Move the file
    shutil.move(str(old_path), str(new_path))
    modified.append(new_path)

    # If the name changed, update all references across the wiki
    if old_stem != new_stem:
        for md_file in sorted(root.rglob("*.md")):
            if any(part.startswith(".") for part in md_file.relative_to(root).parts):
                continue

            text = md_file.read_text(encoding="utf-8")
            new_text = rewrite_links(text, old_stem, new_stem)
            if new_text != text:
                md_file.write_text(new_text, encoding="utf-8")
                modified.append(md_file)

    return sorted(set(modified))


def merge(source_path: Path, target_path: Path, root: Path) -> list[Path]:
    """Merge source page into target page.

    Appends source body content to target, redirects all links
    from source to target, then deletes source.

    Args:
        source_path: File to merge FROM (will be deleted).
        target_path: File to merge INTO (will be appended to).
        root: Wiki root directory.

    Returns:
        List of all modified files.
    """
    if not source_path.exists():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if not target_path.exists():
        raise FileNotFoundError(f"Target file not found: {target_path}")

    source_stem = source_path.stem
    target_stem = target_path.stem
    modified: list[Path] = []

    # Read both files
    from agent_wiki.frontmatter import parse_frontmatter

    source_text = source_path.read_text(encoding="utf-8")
    target_text = target_path.read_text(encoding="utf-8")

    _, source_body = parse_frontmatter(source_text)

    # Append source body to target
    target_text = target_text.rstrip() + "\n\n" + source_body.strip() + "\n"
    target_path.write_text(target_text, encoding="utf-8")
    modified.append(target_path)

    # Delete source
    source_path.unlink()

    # Rewrite all links across the wiki
    for md_file in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue

        text = md_file.read_text(encoding="utf-8")
        new_text = rewrite_links(text, source_stem, target_stem)
        if new_text != text:
            md_file.write_text(new_text, encoding="utf-8")
            modified.append(md_file)

    return sorted(set(modified))


def rename(old_name: str, new_name: str, root: Path) -> list[Path]:
    """Rename a page by name — finds the file, renames it, updates all references.

    Args:
        old_name: Current page name (stem, no .md).
        new_name: New page name (stem, no .md).
        root: Wiki root directory.

    Returns:
        List of all modified files.
    """
    name_index = build_name_index(root)

    if old_name not in name_index:
        raise FileNotFoundError(f"No page found with name: {old_name}")

    old_path = name_index[old_name]
    new_path = old_path.parent / f"{new_name}.md"

    return move(old_path, new_path, root)
