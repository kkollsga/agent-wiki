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
        '---\ntitle: Test Wiki\ntype: index\n---\n\n# Test Wiki\n\n'
        '## Topics\n\n- [[Test Topic]]\n  - [[Child Topic]]\n',
        encoding="utf-8",
    )

    # Hub topic
    (topics / "Test Topic.md").write_text(
        '---\ntitle: Test Topic\nparent: "[[index]]"\ntype: topic\n---\n\n'
        '*[[index]] > Test Topic*\n\nSome content about the topic (Author, 2020).\n\n'
        '## See Also\n\n- [[Child Topic]]\n\n'
        '## Sources\n\n- [[Author 2020 - Test Paper]]\n',
        encoding="utf-8",
    )

    # Child topic
    (topics / "Child Topic.md").write_text(
        '---\ntitle: Child Topic\nparent: "[[Test Topic]]"\ntype: topic\n---\n\n'
        '*[[index]] > [[Test Topic]] > Child Topic*\n\nChild content.\n\n'
        '## Sources\n\n- [[Author 2020 - Test Paper]]\n',
        encoding="utf-8",
    )

    # Source page
    (sources / "Author 2020 - Test Paper.md").write_text(
        '---\ntitle: "Test Paper Title"\nauthors: [Author]\nyear: 2020\n'
        'type: source\nfile: "[[Raw/test.pdf]]"\n---\n\n'
        '# Test Paper\n\n**Authors:** Author (2020)\n\n'
        '## Key Contributions\n\n- Finding 1\n\n'
        '## Topics\n\n- [[Test Topic]] — main topic\n'
        '- [[Child Topic]] — also relevant\n',
        encoding="utf-8",
    )

    return tmp_path


@pytest.fixture
def wiki_with_orphan(wiki_root: Path) -> Path:
    """Wiki with an orphan page (no inbound links)."""
    topics = wiki_root / "topics" / "Test Topic"
    (topics / "Orphan Page.md").write_text(
        '---\ntitle: Orphan Page\nparent: "[[Test Topic]]"\ntype: topic\n---\n\n'
        '*[[index]] > [[Test Topic]] > Orphan Page*\n\nNo one links here.\n\n'
        '## Sources\n\n',
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
