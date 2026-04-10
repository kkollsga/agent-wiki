"""Tests for project initialization."""

from agent_wiki.init_project import init_project


def test_init_creates_structure(tmp_path):
    root = tmp_path / "my-wiki"
    init_project(root, name="Test Wiki")

    assert (root / "raw").is_dir()
    assert (root / "wiki/index.md").exists()
    assert (root / "wiki/log.md").exists()
    assert (root / "wiki/processed").is_dir()
    assert (root / "wiki/sources").is_dir()
    assert (root / "wiki/topics").is_dir()
    assert (root / "kanban/backlog").is_dir()
    assert (root / "kanban/processing").is_dir()
    assert (root / "kanban/review").is_dir()
    assert (root / "kanban/done").is_dir()
    assert (root / "instructions/agents/reader.md").exists()
    assert (root / "instructions/agents/writer.md").exists()
    assert (root / "instructions/agents/orchestrator.md").exists()
    assert (root / "instructions/lint.md").exists()
    assert (root / "instructions/kanban-design.md").exists()
    assert (root / ".claude/commands/ingest.md").exists()
    assert (root / ".claude/commands/lint.md").exists()
    assert (root / "CLAUDE.md").exists()
    assert (root / ".gitignore").exists()


def test_init_uses_name(tmp_path):
    root = tmp_path / "project"
    init_project(root, name="My Research")

    index = (root / "wiki/index.md").read_text()
    assert "My Research" in index

    claude = (root / "CLAUDE.md").read_text()
    assert "My Research" in claude


def test_init_never_overwrites(tmp_path):
    root = tmp_path / "project"
    init_project(root, name="First")

    # Write custom content
    (root / "CLAUDE.md").write_text("custom content")

    # Re-init should not overwrite
    init_project(root, name="Second")
    assert (root / "CLAUDE.md").read_text() == "custom content"
