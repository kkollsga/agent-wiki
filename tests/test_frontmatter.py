"""Tests for frontmatter parsing and serialization."""

from agent_wiki.frontmatter import extract_parent_link, parse_frontmatter, serialize_frontmatter


def test_parse_topic_frontmatter():
    text = '---\ntitle: My Topic\nparent: "[[Parent]]"\ntype: topic\n---\n\nBody text.'
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "My Topic"
    assert meta["parent"] == "[[Parent]]"
    assert meta["type"] == "topic"
    assert body.strip() == "Body text."


def test_parse_source_frontmatter():
    text = '---\ntitle: "Paper Title"\nauthors: [Smith, Jones]\nyear: 2024\ntype: source\n---\n\nBody.'
    meta, body = parse_frontmatter(text)
    assert meta["title"] == "Paper Title"
    assert meta["authors"] == ["Smith", "Jones"]
    assert meta["year"] == 2024
    assert meta["type"] == "source"


def test_parse_no_frontmatter():
    text = "Just a regular file\nwith content."
    meta, body = parse_frontmatter(text)
    assert meta == {}
    assert body == text


def test_extract_parent_link():
    assert extract_parent_link({"parent": "[[Sand Injectites]]"}) == "Sand Injectites"
    assert extract_parent_link({"parent": '[[index]]'}) == "index"
    assert extract_parent_link({}) is None
    assert extract_parent_link({"parent": ""}) is None


def test_serialize_roundtrip():
    meta = {"title": "Test", "type": "topic", "year": 2024}
    serialized = serialize_frontmatter(meta)
    assert serialized.startswith("---\n")
    assert serialized.endswith("---\n")
    assert "title: Test" in serialized
    assert "year: 2024" in serialized

    # Parse it back
    parsed, _ = parse_frontmatter(serialized + "\nBody")
    assert parsed["title"] == "Test"
    assert parsed["year"] == 2024


def test_serialize_quoted_wikilinks():
    meta = {"parent": "[[My Parent]]"}
    serialized = serialize_frontmatter(meta)
    assert '"[[My Parent]]"' in serialized


def test_serialize_list():
    meta = {"authors": ["Smith", "Jones"]}
    serialized = serialize_frontmatter(meta)
    assert "[Smith, Jones]" in serialized
