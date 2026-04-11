"""agent-wiki — Toolkit for building LLM-maintained wikis."""

from importlib.metadata import version

__version__ = version("agent-wiki")

import shutil
from pathlib import Path

from agent_wiki.init_project import init_project as init_project

from agent_wiki._types import LintIssue, WikiStats
from agent_wiki import files as _files
from agent_wiki import helpers as _helpers
from agent_wiki import kanban as _kanban
from agent_wiki import links as _links
from agent_wiki import lint as _lint
from agent_wiki.convert.pdf import convert_pdf as _convert_pdf


class WikiRoot:
    """Central entry point for wiki operations.

    Initialize once with the wiki root path, then call methods:

        wiki = WikiRoot("/path/to/wiki")
        issues = wiki.lint()
        wiki.move("old/path.md", "new/path.md")
    """

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve()
        if not self.root.is_dir():
            raise FileNotFoundError(f"Wiki root not found: {self.root}")
        self._name_index: dict[str, Path] | None = None

    @property
    def name_index(self) -> dict[str, Path]:
        """Lazily built name-to-path index. Invalidated after mutations."""
        if self._name_index is None:
            self._name_index = _links.build_name_index(self.root)
        return self._name_index

    def _invalidate(self):
        self._name_index = None

    def lint(self, *, check_urls: bool = False) -> list[LintIssue]:
        """Run all lint checks. Returns issues sorted by severity."""
        return _lint.lint(self.root, check_urls=check_urls)

    def move(self, old_path: str | Path, new_path: str | Path) -> list[Path]:
        """Move/rename a file and update all references wiki-wide."""
        result = _files.move(self.root / old_path, self.root / new_path, self.root)
        self._invalidate()
        return result

    def merge(self, source_path: str | Path, target_path: str | Path) -> list[Path]:
        """Merge source into target, updating all references."""
        result = _files.merge(
            self.root / source_path, self.root / target_path, self.root
        )
        self._invalidate()
        return result

    def rename(self, old_name: str, new_name: str) -> list[Path]:
        """Rename a page by name (finds the file automatically)."""
        result = _files.rename(old_name, new_name, self.root)
        self._invalidate()
        return result

    def convert_pdf(
        self, pdf_path: str | Path, output_path: str | Path, **kwargs
    ) -> Path:
        """Convert PDF to markdown with extracted images."""
        return _convert_pdf(Path(pdf_path), Path(output_path), **kwargs)

    def backlinks(self, page_name: str) -> list[Path]:
        """Find all pages linking to the given page."""
        return _links.find_backlinks(page_name, self.root)

    def find_references(self, term: str) -> dict[Path, int]:
        """Search for a term across all wiki files. Returns {path: count}."""
        results: dict[Path, int] = {}
        for md_file in self.root.rglob("*.md"):
            if any(
                part.startswith(".") for part in md_file.relative_to(self.root).parts
            ):
                continue
            text = md_file.read_text(encoding="utf-8")
            count = text.lower().count(term.lower())
            if count > 0:
                results[md_file] = count
        return dict(sorted(results.items(), key=lambda x: -x[1]))

    # --- Kanban ---

    def kanban_process(
        self,
        input_dir: str | Path,
        output_dir: str | Path | None = None,
        *,
        completed_dir: str = "./completed",
        kanban_dir: str | Path | None = None,
        ignore: list[str] | None = None,
        max_dpi: int = 150,
    ) -> list[Path]:
        """Scan for new source files, convert them, and create kanban task cards.

        Args:
            input_dir: Directory to scan for source files (e.g. "raw/").
            output_dir: Where to write converted markdown. Defaults to root/processed/.
            completed_dir: Where to move originals after conversion.
                Relative to input_dir (default: "./completed").
            kanban_dir: Backlog directory for task cards.
                Defaults to root/kanban/backlog/.
            ignore: Subdirectory names to skip (default: ["completed"]).
            max_dpi: Image resolution for PDF conversion.

        Returns:
            List of created task card paths.
        """
        input_dir = Path(input_dir).resolve()
        if output_dir is None:
            output_dir = self.root / "processed"
        else:
            output_dir = Path(output_dir).resolve()
        if kanban_dir is None:
            kanban_dir = self.root.parent / "kanban" / "backlog"
        else:
            kanban_dir = Path(kanban_dir).resolve()

        if ignore is None:
            ignore = ["completed"]

        # Resolve completed_dir relative to input_dir
        if completed_dir.startswith("./"):
            abs_completed = input_dir / completed_dir[2:]
        else:
            abs_completed = Path(completed_dir).resolve()

        # Supported converters
        converters = {".pdf": _convert_pdf}

        cards: list[Path] = []

        for source_file in sorted(input_dir.rglob("*")):
            if not source_file.is_file():
                continue

            # Skip ignored directories
            rel = source_file.relative_to(input_dir)
            if any(part in ignore for part in rel.parts):
                continue

            # Skip unsupported extensions
            ext = source_file.suffix.lower()
            if ext not in converters:
                continue

            # Check if already processed — flat output, no subfolders
            md_name = source_file.stem + ".md"
            dest_md = output_dir / md_name
            completed_path = abs_completed / rel

            if dest_md.exists() or completed_path.exists():
                continue

            # Convert — images go in img/<stem>/
            img_dir = output_dir / "img" / source_file.stem
            try:
                converters[ext](
                    source_file, dest_md,
                    img_dir=img_dir, base_dir=self.root, max_dpi=max_dpi,
                )
            except Exception as e:
                print(f"WARN: Failed to convert {rel}: {e}")
                continue

            # Move original to completed
            completed_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(source_file), str(completed_path))

            # Create task card
            card = _kanban.create_card(
                source_file=str(rel),
                processed_file=str(dest_md.relative_to(self.root)),
                kanban_dir=str(kanban_dir),
                agent="reader",
                card_name=source_file.stem + ".md",
            )
            cards.append(card)

        return cards

    def kanban_status(self, kanban_dir: str | Path | None = None) -> dict[str, int]:
        """Count cards per kanban column."""
        if kanban_dir is None:
            kanban_dir = self.root.parent / "kanban"
        return _kanban.kanban_status(kanban_dir)

    def kanban_list(
        self,
        column: str | None = None,
        agent: str | None = None,
        kanban_dir: str | Path | None = None,
    ) -> list[dict]:
        """List kanban cards, optionally filtered."""
        if kanban_dir is None:
            kanban_dir = self.root.parent / "kanban"
        return _kanban.list_cards(kanban_dir, column=column, agent=agent)

    # --- Helpers ---

    def update_index(self, title: str | None = None) -> Path:
        """Auto-generate index.md from the topic folder structure."""
        return _helpers.update_index(self.root, title=title)

    def append_log(self, action: str, description: str, details: str = "") -> Path:
        """Append a formatted entry to log.md."""
        return _helpers.append_log(self.root, action, description, details)

    def generate_sources_status(
        self,
        raw_dir: str | Path | None = None,
        kanban_dir: str | Path | None = None,
    ) -> Path:
        """Auto-generate sources-status.md from raw files and wiki state."""
        if raw_dir is not None:
            raw_dir = Path(raw_dir)
        if kanban_dir is not None:
            kanban_dir = Path(kanban_dir)
        return _helpers.generate_sources_status(self.root, raw_dir, kanban_dir)

    # --- Stats ---

    def stats(self) -> WikiStats:
        """Compute summary statistics for the wiki."""
        from agent_wiki.frontmatter import parse_frontmatter

        graph = _links.build_link_graph(self.root)
        name_index = self.name_index

        type_counts: dict[str, int] = {}
        topic_count = source_count = 0

        for page_path in name_index.values():
            text = page_path.read_text(encoding="utf-8")
            meta, _ = parse_frontmatter(text)
            pt = meta.get("type", "unknown")
            type_counts[pt] = type_counts.get(pt, 0) + 1
            if pt == "topic":
                topic_count += 1
            elif pt == "source":
                source_count += 1

        all_targets = [t for targets in graph.values() for t in targets]

        # Inbound link tracking
        inbound: set[str] = set()
        for targets in graph.values():
            for t in targets:
                if t in name_index:
                    inbound.add(t)
        orphans = set(name_index.keys()) - inbound - {"index"}

        # Broken links
        all_unique = set(all_targets)
        broken = sum(
            1 for t in all_unique if t not in name_index and not t.startswith("Raw/")
        )

        return WikiStats(
            total_pages=len(name_index),
            topic_pages=topic_count,
            source_pages=source_count,
            total_links=len(all_targets),
            unique_links=len(all_unique),
            orphan_count=len(orphans),
            broken_link_count=broken,
            missing_backlink_count=0,  # computed by full lint
            pages_by_type=type_counts,
        )
