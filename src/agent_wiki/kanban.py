"""Filesystem-based kanban for coordinating AI agents.

Agents communicate through task cards — lightweight markdown files that move
between column folders (backlog → processing → review → done). No database;
the folder structure is the state.
"""

import shutil
from datetime import datetime, timezone
from pathlib import Path

from agent_wiki.frontmatter import parse_frontmatter, serialize_frontmatter

COLUMNS = ("backlog", "processing", "review", "done")


def create_card(
    source_file: str | Path,
    processed_file: str | Path,
    kanban_dir: str | Path,
    agent: str = "reader",
    *,
    card_name: str | None = None,
) -> Path:
    """Create a task card in the kanban backlog.

    Args:
        source_file: Path to the original source document.
        processed_file: Path to the converted markdown.
        kanban_dir: Path to the backlog column (e.g. kanban/backlog/).
        agent: Which agent type should handle this card.
        card_name: Filename for the card. Defaults to processed file stem.

    Returns:
        Path to the created card.
    """
    kanban_dir = Path(kanban_dir)
    kanban_dir.mkdir(parents=True, exist_ok=True)

    if card_name is None:
        card_name = Path(processed_file).stem + ".md"
    if not card_name.endswith(".md"):
        card_name += ".md"

    meta = {
        "agent": agent,
        "status": "pending",
        "source_file": str(source_file),
        "processed_file": str(processed_file),
        "summary_file": "",
        "topic_files": [],
        "created": _now_iso(),
        "claimed_at": "",
    }

    content = serialize_frontmatter(meta) + "\n## Actions\n\n"
    card_path = kanban_dir / card_name
    card_path.write_text(content, encoding="utf-8")
    return card_path


def claim(card_path: str | Path, processing_dir: str | Path) -> Path | None:
    """Claim a task card by moving it to the processing column.

    This is an atomic operation — if the file is already gone
    (another agent claimed it), returns None.

    Args:
        card_path: Path to the card in backlog/ or review/.
        processing_dir: Path to the processing column.

    Returns:
        New path in processing/, or None if the card was already claimed.
    """
    card_path = Path(card_path)
    processing_dir = Path(processing_dir)
    processing_dir.mkdir(parents=True, exist_ok=True)

    dest = processing_dir / card_path.name

    try:
        shutil.move(str(card_path), str(dest))
    except FileNotFoundError:
        return None

    # Update metadata
    text = dest.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)
    meta["status"] = "claimed"
    meta["claimed_at"] = _now_iso()
    dest.write_text(serialize_frontmatter(meta) + body, encoding="utf-8")

    return dest


def complete(
    card_path: str | Path,
    target_dir: str | Path,
    *,
    agent: str | None = None,
    summary_file: str | None = None,
    topic_files: list[str] | None = None,
    actions: list[str] | None = None,
) -> Path:
    """Complete a task and move the card to the next column.

    Args:
        card_path: Path to the card in processing/.
        target_dir: Where to move it (review/, done/, or backlog/ for rework).
        agent: Set the next agent type (for handoff to next stage).
        summary_file: Path to the source page created (reader output).
        topic_files: Paths to topic pages created/updated (writer output).
        actions: Action items to add (for rework cards sent back to backlog).

    Returns:
        New path in the target column.
    """
    card_path = Path(card_path)
    target_dir = Path(target_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    text = card_path.read_text(encoding="utf-8")
    meta, body = parse_frontmatter(text)

    # Update metadata
    meta["status"] = "pending"
    meta["claimed_at"] = ""
    if agent is not None:
        meta["agent"] = agent
    if summary_file is not None:
        meta["summary_file"] = summary_file
    if topic_files is not None:
        meta["topic_files"] = topic_files

    # Update actions in body
    if actions is not None:
        action_lines = "\n".join(f"- {a}" for a in actions)
        body = f"\n## Actions\n\n{action_lines}\n"
    elif "## Actions" not in body:
        body += "\n## Actions\n\n"

    dest = target_dir / card_path.name
    dest.write_text(serialize_frontmatter(meta) + body, encoding="utf-8")

    # Remove from current location if different
    if dest != card_path:
        card_path.unlink(missing_ok=True)

    return dest


def list_cards(
    kanban_dir: str | Path,
    column: str | None = None,
    agent: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List task cards, optionally filtered by column, agent type, or status.

    Args:
        kanban_dir: Root kanban directory (contains backlog/, processing/, etc.).
        column: Filter to a specific column (e.g. "backlog", "review").
        agent: Filter by agent type (e.g. "reader", "writer").
        status: Filter by status (e.g. "pending", "claimed").

    Returns:
        List of dicts with card metadata + path + column info.
    """
    kanban_dir = Path(kanban_dir)
    results: list[dict] = []

    columns = [column] if column else list(COLUMNS)

    for col in columns:
        col_dir = kanban_dir / col
        if not col_dir.is_dir():
            continue

        for card_file in sorted(col_dir.glob("*.md")):
            text = card_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(text)

            if agent and meta.get("agent") != agent:
                continue
            if status and meta.get("status") != status:
                continue

            entry = {**meta, "path": str(card_file), "column": col}
            results.append(entry)

    return results


def recover_stale(
    processing_dir: str | Path,
    backlog_dir: str | Path,
    max_age_minutes: int = 30,
) -> list[Path]:
    """Move stale cards from processing back to backlog.

    Cards are considered stale if their claimed_at timestamp
    is older than max_age_minutes.

    Returns:
        List of recovered card paths (now in backlog).
    """
    processing_dir = Path(processing_dir)
    backlog_dir = Path(backlog_dir)
    backlog_dir.mkdir(parents=True, exist_ok=True)
    recovered: list[Path] = []
    now = datetime.now(timezone.utc)

    if not processing_dir.is_dir():
        return recovered

    for card_file in processing_dir.glob("*.md"):
        text = card_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        claimed_at = meta.get("claimed_at", "")
        if not claimed_at:
            # No timestamp — recover immediately
            pass
        else:
            try:
                claimed_time = datetime.fromisoformat(claimed_at)
                age = (now - claimed_time).total_seconds() / 60
                if age < max_age_minutes:
                    continue
            except (ValueError, TypeError):
                pass  # Bad timestamp — recover it

        # Move back to backlog
        meta["status"] = "pending"
        meta["claimed_at"] = ""
        dest = backlog_dir / card_file.name
        dest.write_text(serialize_frontmatter(meta) + body, encoding="utf-8")
        card_file.unlink()
        recovered.append(dest)

    return recovered


def kanban_status(kanban_dir: str | Path) -> dict[str, int]:
    """Count cards per column.

    Returns:
        Dict like {"backlog": 5, "processing": 2, "review": 1, "done": 10}
    """
    kanban_dir = Path(kanban_dir)
    counts: dict[str, int] = {}
    for col in COLUMNS:
        col_dir = kanban_dir / col
        if col_dir.is_dir():
            counts[col] = len(list(col_dir.glob("*.md")))
        else:
            counts[col] = 0
    return counts


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
