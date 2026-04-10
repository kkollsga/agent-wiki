"""Wiki health checks — broken links, missing backlinks, orphans, etc."""

import re
from pathlib import Path

from agent_wiki._types import (
    IssueKind,
    IssueSeverity,
    LintIssue,
    PageInfo,
    PageType,
)
from agent_wiki.frontmatter import extract_parent_link, parse_frontmatter
from agent_wiki.links import (
    build_link_graph,
    build_name_index,
    extract_section_links,
    parse_link_targets,
)

_BREADCRUMB_RE = re.compile(r"^\*(.+)\*\s*$", re.MULTILINE)
_DISPUTED_RE = re.compile(r"^>\s*\*\*Disputed:\*\*(.+)", re.MULTILINE)
_YEAR_RE = re.compile(r"\((\d{4})\)")


def lint(root: Path) -> list[LintIssue]:
    """Run all lint checks on the wiki rooted at root."""
    pages = _scan_all_pages(root)
    name_index = build_name_index(root)
    link_graph = build_link_graph(root)

    issues: list[LintIssue] = []
    issues.extend(_check_broken_links(pages, name_index))
    issues.extend(_check_missing_backlinks(pages, name_index))
    issues.extend(_check_orphan_pages(pages, link_graph, name_index))
    issues.extend(_check_broken_breadcrumbs(pages, name_index))
    issues.extend(_check_missing_frontmatter(pages))
    issues.extend(_check_missing_sections(pages))
    issues.extend(_check_dispute_chronology(pages))
    issues.extend(_check_split_candidates(pages))
    issues.extend(_check_structure(pages, root))

    return sorted(issues, key=lambda i: (i.severity.value, str(i.file)))


def _scan_all_pages(root: Path) -> list[PageInfo]:
    """Parse every .md file in the wiki into PageInfo objects."""
    pages: list[PageInfo] = []

    for md_file in sorted(root.rglob("*.md")):
        if any(part.startswith(".") for part in md_file.relative_to(root).parts):
            continue

        text = md_file.read_text(encoding="utf-8")
        meta, body = parse_frontmatter(text)

        # Determine page type
        raw_type = meta.get("type", "")
        try:
            page_type = PageType(raw_type)
        except ValueError:
            page_type = None

        # Extract sections (## headings)
        sections = re.findall(r"^## (.+)$", body, re.MULTILINE)

        # Extract breadcrumb
        bc_match = _BREADCRUMB_RE.search(body[:500])
        breadcrumb = bc_match.group(0).strip() if bc_match else None

        pages.append(
            PageInfo(
                path=md_file,
                title=meta.get("title", md_file.stem),
                page_type=page_type,
                parent=extract_parent_link(meta),
                authors=meta.get("authors", []),
                year=meta.get("year"),
                file_ref=meta.get("file"),
                outbound_links=parse_link_targets(body),
                sections=sections,
                line_count=text.count("\n") + 1,
                breadcrumb=breadcrumb,
                body=body,
            )
        )

    return pages


def _check_broken_links(
    pages: list[PageInfo], name_index: dict[str, Path]
) -> list[LintIssue]:
    """Check for outbound links that don't resolve to any file."""
    issues: list[LintIssue] = []
    for page in pages:
        for target in page.outbound_links:
            # Skip Raw/ file references and index
            if target.startswith("Raw/") or "/" in target:
                continue
            if target not in name_index:
                issues.append(
                    LintIssue(
                        kind=IssueKind.BROKEN_LINK,
                        severity=IssueSeverity.ERROR,
                        file=page.path,
                        message=f"Broken link: [[{target}]] — no matching page found",
                        context=target,
                    )
                )
    return issues


def _check_missing_backlinks(
    pages: list[PageInfo], name_index: dict[str, Path]
) -> list[LintIssue]:
    """Check bidirectional link integrity between Sources and Topics sections."""
    issues: list[LintIssue] = []

    # Build lookup by stem
    page_by_stem: dict[str, PageInfo] = {p.path.stem: p for p in pages}

    for page in pages:
        if page.page_type == PageType.TOPIC:
            # Topic's Sources should be mirrored in each source's Topics
            source_links = extract_section_links(page.body, "Sources")
            for src_name in source_links:
                src_page = page_by_stem.get(src_name)
                if src_page is None:
                    continue
                topic_links = extract_section_links(src_page.body, "Topics")
                if page.path.stem not in topic_links:
                    issues.append(
                        LintIssue(
                            kind=IssueKind.MISSING_BACKLINK,
                            severity=IssueSeverity.WARNING,
                            file=src_page.path,
                            message=(
                                f"Missing backlink: [[{page.path.stem}]] lists "
                                f"[[{src_name}]] as a source, but {src_name} "
                                f"doesn't link back in its Topics section"
                            ),
                            suggestion=f"Add [[{page.path.stem}]] to {src_name}'s ## Topics",
                        )
                    )

        elif page.page_type == PageType.SOURCE:
            # Source's Topics should be mirrored in each topic's Sources
            topic_links = extract_section_links(page.body, "Topics")
            for topic_name in topic_links:
                topic_page = page_by_stem.get(topic_name)
                if topic_page is None:
                    continue
                source_links = extract_section_links(topic_page.body, "Sources")
                if page.path.stem not in source_links:
                    issues.append(
                        LintIssue(
                            kind=IssueKind.MISSING_BACKLINK,
                            severity=IssueSeverity.WARNING,
                            file=topic_page.path,
                            message=(
                                f"Missing backlink: [[{page.path.stem}]] lists "
                                f"[[{topic_name}]] as a topic, but {topic_name} "
                                f"doesn't link back in its Sources section"
                            ),
                            suggestion=f"Add [[{page.path.stem}]] to {topic_name}'s ## Sources",
                        )
                    )

    return issues


def _check_orphan_pages(
    pages: list[PageInfo],
    link_graph: dict[Path, list[str]],
    name_index: dict[str, Path],
) -> list[LintIssue]:
    """Find pages with zero inbound links."""
    # Build set of all stems that are linked to
    linked_stems: set[str] = set()
    for targets in link_graph.values():
        linked_stems.update(targets)

    issues: list[LintIssue] = []
    for page in pages:
        stem = page.path.stem
        if stem == "index":
            continue
        if stem not in linked_stems:
            issues.append(
                LintIssue(
                    kind=IssueKind.ORPHAN_PAGE,
                    severity=IssueSeverity.WARNING,
                    file=page.path,
                    message=f"Orphan page: no other page links to [[{stem}]]",
                )
            )

    return issues


def _check_broken_breadcrumbs(
    pages: list[PageInfo], name_index: dict[str, Path]
) -> list[LintIssue]:
    """Check breadcrumb trails for broken links and completeness."""
    issues: list[LintIssue] = []

    for page in pages:
        if page.page_type not in (PageType.TOPIC, PageType.SOURCE):
            continue
        if page.page_type == PageType.SOURCE:
            continue  # Source pages don't have breadcrumbs

        if not page.breadcrumb:
            issues.append(
                LintIssue(
                    kind=IssueKind.BROKEN_BREADCRUMB,
                    severity=IssueSeverity.ERROR,
                    file=page.path,
                    message="Missing breadcrumb trail",
                    suggestion="Add *[[index]] > ... > Page Name* at top of page",
                )
            )
            continue

        # Extract links from breadcrumb
        bc_links = parse_link_targets(page.breadcrumb)
        if not bc_links or bc_links[0] != "index":
            issues.append(
                LintIssue(
                    kind=IssueKind.BROKEN_BREADCRUMB,
                    severity=IssueSeverity.ERROR,
                    file=page.path,
                    message="Breadcrumb doesn't start with [[index]]",
                    context=page.breadcrumb,
                )
            )

        for link in bc_links:
            if link not in name_index:
                issues.append(
                    LintIssue(
                        kind=IssueKind.BROKEN_BREADCRUMB,
                        severity=IssueSeverity.ERROR,
                        file=page.path,
                        message=f"Broken breadcrumb link: [[{link}]]",
                        context=page.breadcrumb,
                    )
                )

    return issues


def _check_missing_frontmatter(pages: list[PageInfo]) -> list[LintIssue]:
    """Check for required frontmatter fields per page type."""
    issues: list[LintIssue] = []

    required = {
        PageType.TOPIC: ["title", "parent", "type"],
        PageType.SOURCE: ["title", "authors", "year", "type"],
        PageType.INDEX: ["title", "type"],
    }

    for page in pages:
        if page.page_type is None:
            issues.append(
                LintIssue(
                    kind=IssueKind.MISSING_FRONTMATTER,
                    severity=IssueSeverity.ERROR,
                    file=page.path,
                    message="Missing or invalid 'type' field in frontmatter",
                )
            )
            continue

        reqs = required.get(page.page_type, [])
        meta_text = page.path.read_text(encoding="utf-8")
        meta, _ = parse_frontmatter(meta_text)

        for field in reqs:
            if field not in meta or not meta[field]:
                issues.append(
                    LintIssue(
                        kind=IssueKind.MISSING_FRONTMATTER,
                        severity=IssueSeverity.ERROR,
                        file=page.path,
                        message=f"Missing required frontmatter field: '{field}'",
                    )
                )

    return issues


def _check_missing_sections(pages: list[PageInfo]) -> list[LintIssue]:
    """Check for required H2 sections per page type."""
    issues: list[LintIssue] = []

    for page in pages:
        if page.page_type == PageType.TOPIC and "Sources" not in page.sections:
            issues.append(
                LintIssue(
                    kind=IssueKind.MISSING_SECTION,
                    severity=IssueSeverity.WARNING,
                    file=page.path,
                    message="Topic page missing ## Sources section",
                )
            )
        if page.page_type == PageType.SOURCE and "Topics" not in page.sections:
            issues.append(
                LintIssue(
                    kind=IssueKind.MISSING_SECTION,
                    severity=IssueSeverity.WARNING,
                    file=page.path,
                    message="Source page missing ## Topics section",
                )
            )

    return issues


def _check_dispute_chronology(pages: list[PageInfo]) -> list[LintIssue]:
    """Check that Disputed markers lead with the earlier publication year."""
    issues: list[LintIssue] = []

    for page in pages:
        for m in _DISPUTED_RE.finditer(page.body):
            disputed_text = m.group(0)
            years = [int(y) for y in _YEAR_RE.findall(disputed_text)]
            if len(years) >= 2 and years[0] > years[1]:
                issues.append(
                    LintIssue(
                        kind=IssueKind.DISPUTE_CHRONOLOGY,
                        severity=IssueSeverity.WARNING,
                        file=page.path,
                        message=(
                            f"Dispute chronology: first year ({years[0]}) is later "
                            f"than second year ({years[1]}) — lead with the earlier claim"
                        ),
                        context=disputed_text[:120],
                    )
                )

    return issues


def _check_split_candidates(pages: list[PageInfo]) -> list[LintIssue]:
    """Flag pages exceeding 500 lines."""
    return [
        LintIssue(
            kind=IssueKind.SPLIT_CANDIDATE,
            severity=IssueSeverity.INFO,
            file=page.path,
            message=f"Page has {page.line_count} lines — consider splitting",
        )
        for page in pages
        if page.line_count > 500
    ]


def _check_structure(pages: list[PageInfo], root: Path) -> list[LintIssue]:
    """Check folder structure conventions."""
    issues: list[LintIssue] = []

    for page in pages:
        if page.page_type != PageType.TOPIC:
            continue

        # Hub pages should share their folder's name
        folder = page.path.parent
        if folder != root and folder.name != page.path.stem:
            # This is a child page, not a hub — check parent folder has a hub
            hub_path = folder / f"{folder.name}.md"
            if not hub_path.exists():
                issues.append(
                    LintIssue(
                        kind=IssueKind.STRUCTURE_MISMATCH,
                        severity=IssueSeverity.WARNING,
                        file=page.path,
                        message=(
                            f"Folder '{folder.name}' has no hub page ({folder.name}.md)"
                        ),
                    )
                )

    return issues
