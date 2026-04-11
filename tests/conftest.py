"""Shared test fixtures — small wiki trees for testing."""

import pytest
from pathlib import Path


@pytest.fixture
def wiki_root(tmp_path: Path) -> Path:
    """Create a minimal wiki tree for testing."""
    topics = tmp_path / "topics" / "Test Topic"
    sources = tmp_path / "sources" / "Test Topic"
    topics.mkdir(parents=True)
    sources.mkdir(parents=True)

    # index.md
    (tmp_path / "index.md").write_text(
        "---\ntitle: Test Wiki\ntype: index\n---\n\n# Test Wiki\n\n"
        "## Topics\n\n- [[Test Topic]]\n  - [[Child Topic]]\n",
        encoding="utf-8",
    )

    # Hub topic
    (topics / "Test Topic.md").write_text(
        "---\ntitle: Test Topic\n"
        'description: "A test topic for unit testing"\n'
        "tags: [test]\n"
        'parent: "[[index]]"\n'
        "type: topic\n---\n\n"
        "Some content about the topic.\n\n"
        "## See Also\n\n- [[Child Topic]]\n\n"
        "## Sources\n\n- [[Author 2020 - Test Paper]]\n",
        encoding="utf-8",
    )

    # Child topic
    (topics / "Child Topic.md").write_text(
        "---\ntitle: Child Topic\n"
        'description: "A child topic"\n'
        "tags: [test]\n"
        'parent: "[[Test Topic]]"\n'
        "type: topic\n---\n\n"
        "Child content.\n\n"
        "## Sources\n\n- [[Author 2020 - Test Paper]]\n",
        encoding="utf-8",
    )

    # Source page
    (sources / "Author 2020 - Test Paper.md").write_text(
        '---\ntitle: "Test Paper Title"\n'
        'description: "A test paper"\n'
        "authors: [Author]\n"
        "date: 2020-01-01\n"
        "tags: [test]\n"
        'doi: "10.1234/test"\n'
        'type: source\nfile: "[[Raw/test.pdf]]"\n---\n\n'
        "# Test Paper\n\n**Authors:** Author (2020)\n\n"
        "## Key Contributions\n\n- Finding 1\n\n"
        "## Topics\n\n- [[Test Topic]] — main topic\n"
        "- [[Child Topic]] — also relevant\n",
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def wiki_with_orphan(wiki_root: Path) -> Path:
    """Wiki with an orphan page (no inbound links)."""
    topics = wiki_root / "topics" / "Test Topic"
    (topics / "Orphan Page.md").write_text(
        "---\ntitle: Orphan Page\n"
        'description: "An orphan"\n'
        "tags: [test]\n"
        'parent: "[[Test Topic]]"\n'
        "type: topic\n---\n\n"
        "No one links here.\n\n"
        "## Sources\n\n",
        encoding="utf-8",
    )
    return wiki_root


@pytest.fixture
def wiki_with_broken_link(wiki_root: Path) -> Path:
    """Wiki with a broken outbound link."""
    topics = wiki_root / "topics" / "Test Topic"
    page = topics / "Test Topic.md"
    text = page.read_text(encoding="utf-8")
    text = text.replace("## See Also", "## See Also\n\n- [[Nonexistent Page]]")
    page.write_text(text, encoding="utf-8")
    return wiki_root


@pytest.fixture
def wiki_with_images(wiki_root: Path) -> Path:
    """Wiki with image references — some valid, some broken."""
    # Create an image directory with one real image
    img_dir = wiki_root / "processed" / "img" / "Test Paper"
    img_dir.mkdir(parents=True)
    (img_dir / "0001-01.png").write_bytes(b"\x89PNG\r\n")  # minimal PNG header

    # Add image references to a topic page
    topics = wiki_root / "topics" / "Test Topic"
    page = topics / "Test Topic.md"
    text = page.read_text(encoding="utf-8")
    text += (
        "\n\n![Valid image](processed/img/Test Paper/0001-01.png)\n"
        "![Missing image](processed/img/Test Paper/9999-99.png)\n"
    )
    page.write_text(text, encoding="utf-8")
    return wiki_root
