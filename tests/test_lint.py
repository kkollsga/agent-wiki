"""Tests for wiki linting."""

from agent_wiki.lint import lint
from agent_wiki._types import IssueKind


def test_clean_wiki_no_errors(wiki_root):
    issues = lint(wiki_root)
    errors = [i for i in issues if i.kind == IssueKind.BROKEN_LINK]
    assert len(errors) == 0


def test_detects_orphan(wiki_with_orphan):
    issues = lint(wiki_with_orphan)
    orphans = [i for i in issues if i.kind == IssueKind.ORPHAN_PAGE]
    orphan_files = [i.file.stem for i in orphans]
    assert "Orphan Page" in orphan_files


def test_detects_broken_link(wiki_with_broken_link):
    issues = lint(wiki_with_broken_link)
    broken = [i for i in issues if i.kind == IssueKind.BROKEN_LINK]
    assert any("Nonexistent Page" in i.context for i in broken)


def test_detects_dispute_chronology(wiki_root):
    # Add a backwards dispute
    topic_dir = wiki_root / "topics" / "Test Topic"
    page = topic_dir / "Test Topic.md"
    text = page.read_text()
    text += '\n\n> **Disputed:** Smith (2020) argues X. However, Jones (2010) found Y.\n'
    page.write_text(text)

    issues = lint(wiki_root)
    chrono = [i for i in issues if i.kind == IssueKind.DISPUTE_CHRONOLOGY]
    assert len(chrono) == 1


def test_detects_missing_section(tmp_path):
    # Topic without ## Sources
    topics = tmp_path / "topics"
    topics.mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    (topics / "Bad Topic.md").write_text(
        '---\ntitle: Bad\nparent: "[[index]]"\ntype: topic\n---\n\n'
        "*[[index]] > Bad Topic*\n\nContent but no Sources section.\n"
    )

    issues = lint(tmp_path)
    missing = [i for i in issues if i.kind == IssueKind.MISSING_SECTION]
    assert len(missing) == 1
