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


def test_detects_dispute_chronology_legacy(wiki_root):
    """Legacy format: > **Disputed:**"""
    topic_dir = wiki_root / "topics" / "Test Topic"
    page = topic_dir / "Test Topic.md"
    text = page.read_text()
    text += (
        "\n\n> **Disputed:** Smith (2020) argues X. However, Jones (2010) found Y.\n"
    )
    page.write_text(text)

    issues = lint(wiki_root)
    chrono = [i for i in issues if i.kind == IssueKind.DISPUTE_CHRONOLOGY]
    assert len(chrono) == 1


def test_detects_dispute_chronology_callout(wiki_root):
    """Obsidian callout format: > [!warning] Disputed"""
    topic_dir = wiki_root / "topics" / "Test Topic"
    page = topic_dir / "Test Topic.md"
    text = page.read_text()
    text += (
        "\n\n> [!warning] Disputed\n"
        "> Smith (2020) argues X. However, Jones (2010) found Y.\n"
    )
    page.write_text(text)

    issues = lint(wiki_root)
    chrono = [i for i in issues if i.kind == IssueKind.DISPUTE_CHRONOLOGY]
    assert len(chrono) == 1


def test_detects_missing_section(tmp_path):
    """Topic without ## Sources."""
    topics = tmp_path / "topics"
    topics.mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    (topics / "Bad Topic.md").write_text(
        "---\ntitle: Bad\n"
        'description: "bad"\n'
        "tags: [test]\n"
        'parent: "[[index]]"\n'
        "type: topic\n---\n\n"
        "Content but no Sources section.\n"
    )

    issues = lint(tmp_path)
    missing = [i for i in issues if i.kind == IssueKind.MISSING_SECTION]
    assert len(missing) == 1


# --- New tests ---


def test_detects_broken_image(wiki_with_images):
    """Broken image path should be flagged."""
    issues = lint(wiki_with_images)
    broken_imgs = [i for i in issues if i.kind == IssueKind.BROKEN_IMAGE]
    assert any("9999-99.png" in i.context for i in broken_imgs)


def test_valid_image_no_issue(wiki_with_images):
    """Valid image path should NOT be flagged."""
    issues = lint(wiki_with_images)
    broken_imgs = [i for i in issues if i.kind == IssueKind.BROKEN_IMAGE]
    assert not any("0001-01.png" in i.context for i in broken_imgs)


def test_detects_broken_anchor(wiki_root):
    """[[Page#NonexistentSection]] should flag BROKEN_ANCHOR."""
    topic_dir = wiki_root / "topics" / "Test Topic"
    page = topic_dir / "Child Topic.md"
    text = page.read_text()
    text += "\n\nSee [[Test Topic#Nonexistent Section]] for details.\n"
    page.write_text(text)

    issues = lint(wiki_root)
    anchors = [i for i in issues if i.kind == IssueKind.BROKEN_ANCHOR]
    assert any("Nonexistent Section" in i.context for i in anchors)


def test_valid_anchor_no_issue(wiki_root):
    """[[Page#See Also]] with existing heading should NOT flag."""
    topic_dir = wiki_root / "topics" / "Test Topic"
    page = topic_dir / "Child Topic.md"
    text = page.read_text()
    text += "\n\nSee [[Test Topic#See Also]] for details.\n"
    page.write_text(text)

    issues = lint(wiki_root)
    anchors = [i for i in issues if i.kind == IssueKind.BROKEN_ANCHOR]
    assert not any("See Also" in i.context for i in anchors)


def test_missing_frontmatter_description_tags(tmp_path):
    """Topic missing description and tags should be flagged."""
    topics = tmp_path / "topics"
    topics.mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    (topics / "Sparse.md").write_text(
        "---\ntitle: Sparse\n"
        'parent: "[[index]]"\n'
        "type: topic\n---\n\n"
        "Minimal page.\n\n## Sources\n\n"
    )

    issues = lint(tmp_path)
    fm_issues = [
        i for i in issues
        if i.kind == IssueKind.MISSING_FRONTMATTER and "Sparse" in str(i.file)
    ]
    missing_fields = [i.message for i in fm_issues]
    assert any("description" in m for m in missing_fields)
    assert any("tags" in m for m in missing_fields)


def test_processed_page_type(tmp_path):
    """type: processed should be recognized, not flagged as invalid."""
    processed = tmp_path / "processed"
    processed.mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    (processed / "Paper.md").write_text(
        '---\ntitle: "Some Paper"\ntype: processed\n---\n\nContent.\n'
    )

    issues = lint(tmp_path)
    type_errors = [
        i for i in issues
        if i.kind == IssueKind.MISSING_FRONTMATTER
        and "type" in i.message
        and "Paper" in str(i.file)
    ]
    assert len(type_errors) == 0


def test_parent_chain_missing_parent(tmp_path):
    """Topic without parent should flag BROKEN_BREADCRUMB."""
    topics = tmp_path / "topics"
    topics.mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    (topics / "No Parent.md").write_text(
        "---\ntitle: No Parent\n"
        'description: "test"\n'
        "tags: [test]\n"
        "type: topic\n---\n\n"
        "Content.\n\n## Sources\n\n"
    )

    issues = lint(tmp_path)
    parent_issues = [i for i in issues if i.kind == IssueKind.BROKEN_BREADCRUMB]
    assert any("Missing parent" in i.message for i in parent_issues)


def test_parent_chain_broken_parent(tmp_path):
    """Topic with nonexistent parent should flag BROKEN_BREADCRUMB."""
    topics = tmp_path / "topics"
    topics.mkdir()
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    (topics / "Bad Parent.md").write_text(
        "---\ntitle: Bad Parent\n"
        'description: "test"\n'
        "tags: [test]\n"
        'parent: "[[Does Not Exist]]"\n'
        "type: topic\n---\n\n"
        "Content.\n\n## Sources\n\n"
    )

    issues = lint(tmp_path)
    parent_issues = [i for i in issues if i.kind == IssueKind.BROKEN_BREADCRUMB]
    assert any("Does Not Exist" in i.message for i in parent_issues)


def test_malformed_url(tmp_path):
    """Malformed URL should be flagged."""
    (tmp_path / "index.md").write_text("---\ntitle: T\ntype: index\n---\n\n# T\n")
    topics = tmp_path / "topics"
    topics.mkdir()
    (topics / "URL Test.md").write_text(
        "---\ntitle: URL Test\n"
        'description: "test"\n'
        "tags: [test]\n"
        'parent: "[[index]]"\n'
        "type: topic\n---\n\n"
        "[bad link](http://)\n\n## Sources\n\n"
    )

    issues = lint(tmp_path)
    url_issues = [i for i in issues if i.kind == IssueKind.BROKEN_URL]
    assert len(url_issues) == 1
