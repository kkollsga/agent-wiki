"""Tests for file operations — move, merge, rename."""

import pytest
from agent_wiki.files import merge, move, rename


def test_move_updates_links(wiki_root):
    old = wiki_root / "topics" / "Test Topic" / "Child Topic.md"
    new = wiki_root / "topics" / "Test Topic" / "Renamed Child.md"

    move(old, new, wiki_root)

    # File moved
    assert not old.exists()
    assert new.exists()

    # Links updated in other files
    index_text = (wiki_root / "index.md").read_text()
    assert "[[Renamed Child]]" in index_text
    assert "[[Child Topic]]" not in index_text

    # Source page updated
    source = wiki_root / "sources" / "Test Topic" / "Author 2020 - Test Paper.md"
    source_text = source.read_text()
    assert "[[Renamed Child]]" in source_text


def test_move_nonexistent_raises(wiki_root):
    with pytest.raises(FileNotFoundError):
        move(wiki_root / "nope.md", wiki_root / "dest.md", wiki_root)


def test_move_to_existing_raises(wiki_root):
    src = wiki_root / "topics" / "Test Topic" / "Child Topic.md"
    dst = wiki_root / "topics" / "Test Topic" / "Test Topic.md"
    with pytest.raises(FileExistsError):
        move(src, dst, wiki_root)


def test_rename_by_name(wiki_root):
    modified = rename("Child Topic", "New Child Name", wiki_root)

    assert any("New Child Name" in str(p) for p in modified)

    # Old name gone from references
    index_text = (wiki_root / "index.md").read_text()
    assert "[[New Child Name]]" in index_text
    assert "[[Child Topic]]" not in index_text


def test_rename_nonexistent_raises(wiki_root):
    with pytest.raises(FileNotFoundError):
        rename("Does Not Exist", "Whatever", wiki_root)


def test_merge(wiki_root):
    # Create a second source page to merge
    sources_dir = wiki_root / "sources" / "Test Topic"
    dup = sources_dir / "Duplicate 2020 - Same Paper.md"
    dup.write_text(
        '---\ntitle: "Dup"\nauthors: [Dup]\nyear: 2020\ntype: source\n---\n\n'
        "## Key Contributions\n\n- Duplicate finding\n\n"
        "## Topics\n\n- [[Test Topic]]\n",
        encoding="utf-8",
    )

    # Add a link to the dup in some page
    topic = wiki_root / "topics" / "Test Topic" / "Test Topic.md"
    text = topic.read_text()
    text = text.replace("## Sources", "## Sources\n\n- [[Duplicate 2020 - Same Paper]]")
    topic.write_text(text)

    target = sources_dir / "Author 2020 - Test Paper.md"
    merge(dup, target, wiki_root)

    # Dup deleted
    assert not dup.exists()

    # Content appended
    merged_text = target.read_text()
    assert "Duplicate finding" in merged_text

    # Links redirected
    topic_text = topic.read_text()
    assert "[[Duplicate 2020 - Same Paper]]" not in topic_text
    assert "[[Author 2020 - Test Paper]]" in topic_text
