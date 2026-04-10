"""Tests for link parsing, resolution, and rewriting."""

from agent_wiki.links import (
    build_link_graph,
    build_name_index,
    extract_section_links,
    find_backlinks,
    parse_links,
    parse_link_targets,
    resolve_link,
    rewrite_links,
)


def test_parse_simple_link():
    links = parse_links("See [[Topic A]] for details")
    assert len(links) == 1
    assert links[0].target == "Topic A"
    assert links[0].display is None


def test_parse_display_text_link():
    links = parse_links("See [[Target|display text]] here")
    assert len(links) == 1
    assert links[0].target == "Target"
    assert links[0].display == "display text"


def test_parse_multiple_links():
    links = parse_links("[[A]] and [[B]] and [[C|see C]]")
    assert len(links) == 3
    targets = [l.target for l in links]
    assert targets == ["A", "B", "C"]


def test_parse_link_targets():
    targets = parse_link_targets("[[A]] text [[B|display]]")
    assert targets == ["A", "B"]


def test_parse_no_links():
    assert parse_links("no links here") == []


def test_build_name_index(wiki_root):
    index = build_name_index(wiki_root)
    assert "index" in index
    assert "Test Topic" in index
    assert "Child Topic" in index
    assert "Author 2020 - Test Paper" in index


def test_resolve_link(wiki_root):
    index = build_name_index(wiki_root)
    assert resolve_link("Test Topic", index) is not None
    assert resolve_link("Nonexistent", index) is None


def test_find_backlinks(wiki_root):
    pages = find_backlinks("Test Topic", wiki_root)
    stems = [p.stem for p in pages]
    assert "index" in stems
    assert "Child Topic" in stems
    assert "Author 2020 - Test Paper" in stems


def test_build_link_graph(wiki_root):
    graph = build_link_graph(wiki_root)
    assert len(graph) == 4  # index, 2 topics, 1 source


def test_rewrite_links_simple():
    text = "See [[Old Name]] for details"
    result = rewrite_links(text, "Old Name", "New Name")
    assert result == "See [[New Name]] for details"


def test_rewrite_links_preserves_display():
    text = "See [[Old Name|some display]] here"
    result = rewrite_links(text, "Old Name", "New Name")
    assert result == "See [[New Name|some display]] here"


def test_rewrite_links_no_match():
    text = "See [[Other]] here"
    result = rewrite_links(text, "Old Name", "New Name")
    assert result == text


def test_extract_section_links():
    text = """# Title

## Sources

- [[Source A]]
- [[Source B]]

## See Also

- [[Related]]
"""
    sources = extract_section_links(text, "Sources")
    assert sources == ["Source A", "Source B"]

    see_also = extract_section_links(text, "See Also")
    assert see_also == ["Related"]

    missing = extract_section_links(text, "Nonexistent")
    assert missing == []
