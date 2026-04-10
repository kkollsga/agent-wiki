"""Tests for kanban operations."""

from agent_wiki.kanban import (
    claim,
    complete,
    create_card,
    kanban_status,
    list_cards,
    recover_stale,
)


def test_create_card(tmp_path):
    backlog = tmp_path / "backlog"
    card = create_card("raw/paper.pdf", "processed/paper.md", backlog, agent="reader")

    assert card.exists()
    assert card.name == "paper.md"

    text = card.read_text()
    assert "agent: reader" in text
    assert "status: pending" in text
    assert "raw/paper.pdf" in text


def test_claim(tmp_path):
    backlog = tmp_path / "backlog"
    processing = tmp_path / "processing"
    create_card("raw/a.pdf", "processed/a.md", backlog)

    result = claim(backlog / "a.md", processing)
    assert result is not None
    assert result.parent == processing
    assert not (backlog / "a.md").exists()

    text = result.read_text()
    assert "status: claimed" in text


def test_claim_already_taken(tmp_path):
    backlog = tmp_path / "backlog"
    processing = tmp_path / "processing"
    create_card("raw/a.pdf", "processed/a.md", backlog)

    # First claim succeeds
    claim(backlog / "a.md", processing)

    # Second claim returns None
    result = claim(backlog / "a.md", processing)
    assert result is None


def test_complete(tmp_path):
    backlog = tmp_path / "backlog"
    processing = tmp_path / "processing"
    review = tmp_path / "review"

    create_card("raw/a.pdf", "processed/a.md", backlog)
    claimed = claim(backlog / "a.md", processing)

    result = complete(claimed, review, agent="writer", summary_file="sources/a.md")
    assert result.parent == review
    assert not claimed.exists()

    text = result.read_text()
    assert "agent: writer" in text
    assert "sources/a.md" in text


def test_list_cards(tmp_path):
    backlog = tmp_path / "backlog"
    create_card("raw/a.pdf", "processed/a.md", backlog, agent="reader")
    create_card("raw/b.pdf", "processed/b.md", backlog, agent="writer")

    all_cards = list_cards(tmp_path, column="backlog")
    assert len(all_cards) == 2

    readers = list_cards(tmp_path, column="backlog", agent="reader")
    assert len(readers) == 1
    assert readers[0]["agent"] == "reader"


def test_kanban_status(tmp_path):
    for col in ("backlog", "processing", "review", "done"):
        (tmp_path / col).mkdir()

    create_card("raw/a.pdf", "processed/a.md", tmp_path / "backlog")
    create_card("raw/b.pdf", "processed/b.md", tmp_path / "backlog")

    counts = kanban_status(tmp_path)
    assert counts["backlog"] == 2
    assert counts["processing"] == 0


def test_recover_stale(tmp_path):
    backlog = tmp_path / "backlog"
    processing = tmp_path / "processing"
    backlog.mkdir()
    processing.mkdir()

    create_card("raw/a.pdf", "processed/a.md", backlog)
    claimed = claim(backlog / "a.md", processing)

    # Force stale by setting claimed_at to old time
    text = claimed.read_text()
    text = text.replace(
        "claimed_at:", "claimed_at: 2020-01-01T00:00:00+00:00\nold_claimed_at:"
    )
    claimed.write_text(text)

    recovered = recover_stale(processing, backlog, max_age_minutes=1)
    assert len(recovered) == 1
    assert (backlog / "a.md").exists()
    assert not (processing / "a.md").exists()
