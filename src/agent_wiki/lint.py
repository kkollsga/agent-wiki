"""Wiki health checks — broken links, images, URLs, anchors, frontmatter, etc."""

import re
import urllib.parse
import urllib.request
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
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
_URL_LINK_RE = re.compile(r"\[([^\]]*)\]\((https?://[^)]*)\)")
_DISPUTED_BOLD_RE = re.compile(r"^>\s*\*\*Disputed:\*\*(.+)", re.MULTILINE)
_CALLOUT_DISPUTED_RE = re.compile(
    r"^>\s*\[!warning\]\s*Disputed.*$", re.MULTILINE
)
_YEAR_RE = re.compile(r"\((\d{4})\)")


def lint(root: Path, *, check_urls: bool = False) -> list[LintIssue]:
    """Run all lint checks on the wiki rooted at root."""
    pages = _scan_all_pages(root)
    name_index = build_name_index(root)
    link_graph = build_link_graph(root)

    issues: list[LintIssue] = []
    issues.extend(_check_broken_links(pages, name_index))
    issues.extend(_check_broken_anchors(pages, name_index, _pages_by_stem(pages)))
    issues.extend(_check_broken_images(pages, root))
    issues.extend(_check_broken_urls(pages, check_http=check_urls))
    issues.extend(_check_missing_backlinks(pages, name_index))
    issues.extend(_check_orphan_pages(pages, link_graph, name_index))
    issues.extend(_check_parent_chain(pages, name_index))
    issues.extend(_check_missing_frontmatter(pages))
    issues.extend(_check_missing_sections(pages))
    issues.extend(_check_dispute_chronology(pages))
    issues.extend(_check_split_candidates(pages))
    issues.extend(_check_structure(pages, root))

    return sorted(issues, key=lambda i: (i.severity.value, str(i.file)))


def _pages_by_stem(pages: list[PageInfo]) -> dict[str, PageInfo]:
    return {p.path.stem: p for p in pages}


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

        # Extract sections (## headings) and all headings (any level)
        sections = re.findall(r"^## (.+)$", body, re.MULTILINE)
        headings = re.findall(r"^#{1,6}\s+(.+)$", body, re.MULTILINE)

        # Extract breadcrumb (legacy — kept for backward compat)
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
                headings=headings,
                line_count=text.count("\n") + 1,
                breadcrumb=breadcrumb,
                body=body,
                meta=meta,
            )
        )

    return pages


# ---------------------------------------------------------------------------
# Check: broken wiki-links
# ---------------------------------------------------------------------------


def _check_broken_links(
    pages: list[PageInfo], name_index: dict[str, Path]
) -> list[LintIssue]:
    """Check for outbound links that don't resolve to any file."""
    issues: list[LintIssue] = []
    for page in pages:
        for target in page.outbound_links:
            # Skip Raw/ file references
            if target.startswith("Raw/"):
                continue
            # Strip #anchor before resolving
            target_stem = target.split("#")[0].strip()
            if not target_stem:
                continue
            if target_stem not in name_index:
                # Try path suffix match
                found = False
                target_clean = target_stem.removesuffix(".md")
                for _, path in name_index.items():
                    if str(path).endswith(target_clean + ".md"):
                        found = True
                        break
                if not found:
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


# ---------------------------------------------------------------------------
# Check: broken anchors ([[Page#Section]] where Section doesn't exist)
# ---------------------------------------------------------------------------


def _check_broken_anchors(
    pages: list[PageInfo],
    name_index: dict[str, Path],
    page_lookup: dict[str, PageInfo],
) -> list[LintIssue]:
    """Check that [[Page#Section]] anchors resolve to actual headings."""
    issues: list[LintIssue] = []
    for page in pages:
        for target in page.outbound_links:
            if "#" not in target:
                continue
            page_part, anchor = target.split("#", 1)
            page_part = page_part.strip()
            anchor = anchor.strip()
            if not page_part or not anchor:
                continue

            # Resolve the target page
            target_page = page_lookup.get(page_part)
            if target_page is None:
                # Page doesn't exist — _check_broken_links handles this
                continue

            # Check if heading exists (case-insensitive, stripped)
            anchor_lower = anchor.lower().strip()
            heading_matches = [
                h for h in target_page.headings if h.strip().lower() == anchor_lower
            ]
            if not heading_matches:
                issues.append(
                    LintIssue(
                        kind=IssueKind.BROKEN_ANCHOR,
                        severity=IssueSeverity.WARNING,
                        file=page.path,
                        message=(
                            f"Broken anchor: [[{target}]] — heading '{anchor}' "
                            f"not found in {page_part}"
                        ),
                        context=target,
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# Check: broken image paths
# ---------------------------------------------------------------------------


def _check_broken_images(
    pages: list[PageInfo], root: Path
) -> list[LintIssue]:
    """Check that ![alt](path) image references point to existing files."""
    issues: list[LintIssue] = []
    for page in pages:
        for m in _IMAGE_RE.finditer(page.body):
            img_path = m.group(2).strip()
            # Skip URLs
            if img_path.startswith("http://") or img_path.startswith("https://"):
                continue
            # Skip data URIs
            if img_path.startswith("data:"):
                continue
            # Strip optional size suffix (Obsidian: |100x200)
            if "|" in img_path:
                img_path = img_path.split("|")[0].strip()

            # Try resolving relative to wiki root first, then relative to file
            resolved = root / img_path
            if not resolved.exists():
                resolved = page.path.parent / img_path
            if not resolved.exists():
                issues.append(
                    LintIssue(
                        kind=IssueKind.BROKEN_IMAGE,
                        severity=IssueSeverity.ERROR,
                        file=page.path,
                        message=f"Broken image: {img_path} — file not found",
                        context=img_path,
                    )
                )
    return issues


# ---------------------------------------------------------------------------
# Check: broken/malformed URLs
# ---------------------------------------------------------------------------


def _check_broken_urls(
    pages: list[PageInfo], *, check_http: bool = False
) -> list[LintIssue]:
    """Check external URL links for validity."""
    issues: list[LintIssue] = []
    seen_urls: set[str] = set()

    for page in pages:
        for m in _URL_LINK_RE.finditer(page.body):
            url = m.group(2).strip()
            if url in seen_urls:
                continue
            seen_urls.add(url)

            parsed = urllib.parse.urlparse(url)
            if not parsed.netloc or "." not in parsed.netloc:
                issues.append(
                    LintIssue(
                        kind=IssueKind.BROKEN_URL,
                        severity=IssueSeverity.WARNING,
                        file=page.path,
                        message=f"Malformed URL: {url}",
                        context=url,
                    )
                )
                continue

            if check_http:
                try:
                    req = urllib.request.Request(url, method="HEAD")
                    req.add_header("User-Agent", "agent-wiki-lint/1.0")
                    with urllib.request.urlopen(req, timeout=5) as resp:
                        if resp.status >= 400:
                            issues.append(
                                LintIssue(
                                    kind=IssueKind.BROKEN_URL,
                                    severity=IssueSeverity.WARNING,
                                    file=page.path,
                                    message=f"URL returned HTTP {resp.status}: {url}",
                                    context=url,
                                )
                            )
                except Exception as e:
                    issues.append(
                        LintIssue(
                            kind=IssueKind.BROKEN_URL,
                            severity=IssueSeverity.WARNING,
                            file=page.path,
                            message=f"URL unreachable: {url} ({e})",
                            context=url,
                        )
                    )

    return issues


# ---------------------------------------------------------------------------
# Check: missing backlinks (Sources ↔ Topics bidirectional integrity)
# ---------------------------------------------------------------------------


def _check_missing_backlinks(
    pages: list[PageInfo], name_index: dict[str, Path]
) -> list[LintIssue]:
    """Check bidirectional link integrity between Sources and Topics sections."""
    issues: list[LintIssue] = []
    page_by_stem: dict[str, PageInfo] = {p.path.stem: p for p in pages}

    for page in pages:
        if page.page_type == PageType.TOPIC:
            source_links = extract_section_links(page.body, "Sources")
            for src_name in source_links:
                # Strip #anchor from source link
                src_stem = src_name.split("#")[0].strip()
                src_page = page_by_stem.get(src_stem)
                if src_page is None:
                    continue
                topic_links = extract_section_links(src_page.body, "Topics")
                topic_stems = [t.split("#")[0].strip() for t in topic_links]
                if page.path.stem not in topic_stems:
                    issues.append(
                        LintIssue(
                            kind=IssueKind.MISSING_BACKLINK,
                            severity=IssueSeverity.WARNING,
                            file=src_page.path,
                            message=(
                                f"Missing backlink: [[{page.path.stem}]] lists "
                                f"[[{src_stem}]] as a source, but {src_stem} "
                                f"doesn't link back in its Topics section"
                            ),
                            suggestion=f"Add [[{page.path.stem}]] to {src_stem}'s ## Topics",
                        )
                    )

        elif page.page_type == PageType.SOURCE:
            topic_links = extract_section_links(page.body, "Topics")
            for topic_name in topic_links:
                topic_stem = topic_name.split("#")[0].strip()
                topic_page = page_by_stem.get(topic_stem)
                if topic_page is None:
                    continue
                source_links = extract_section_links(topic_page.body, "Sources")
                source_stems = [s.split("#")[0].strip() for s in source_links]
                if page.path.stem not in source_stems:
                    issues.append(
                        LintIssue(
                            kind=IssueKind.MISSING_BACKLINK,
                            severity=IssueSeverity.WARNING,
                            file=topic_page.path,
                            message=(
                                f"Missing backlink: [[{page.path.stem}]] lists "
                                f"[[{topic_stem}]] as a topic, but {topic_stem} "
                                f"doesn't link back in its Sources section"
                            ),
                            suggestion=f"Add [[{page.path.stem}]] to {topic_stem}'s ## Sources",
                        )
                    )

    return issues


# ---------------------------------------------------------------------------
# Check: orphan pages (zero inbound links)
# ---------------------------------------------------------------------------


def _check_orphan_pages(
    pages: list[PageInfo],
    link_graph: dict[Path, list[str]],
    name_index: dict[str, Path],
) -> list[LintIssue]:
    """Find pages with zero inbound links."""
    linked_stems: set[str] = set()
    for targets in link_graph.values():
        for t in targets:
            linked_stems.add(t.split("#")[0].strip())

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


# ---------------------------------------------------------------------------
# Check: parent chain (replaces old breadcrumb check)
# ---------------------------------------------------------------------------


def _check_parent_chain(
    pages: list[PageInfo], name_index: dict[str, Path]
) -> list[LintIssue]:
    """Validate that topic pages have a valid parent chain back to index."""
    issues: list[LintIssue] = []
    page_by_stem: dict[str, PageInfo] = {p.path.stem: p for p in pages}

    for page in pages:
        if page.page_type != PageType.TOPIC:
            continue

        if not page.parent:
            issues.append(
                LintIssue(
                    kind=IssueKind.BROKEN_BREADCRUMB,
                    severity=IssueSeverity.ERROR,
                    file=page.path,
                    message="Missing parent: topic page has no 'parent' frontmatter",
                    suggestion="Add parent: \"[[Parent Topic]]\" to frontmatter",
                )
            )
            continue

        # Resolve parent
        parent_stem = page.parent.split("#")[0].strip()
        if parent_stem not in name_index:
            # Try path suffix match
            found = any(
                str(p).endswith(parent_stem + ".md")
                for p in name_index.values()
            )
            if not found:
                issues.append(
                    LintIssue(
                        kind=IssueKind.BROKEN_BREADCRUMB,
                        severity=IssueSeverity.ERROR,
                        file=page.path,
                        message=f"Broken parent: [[{page.parent}]] does not exist",
                        context=page.parent,
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Check: missing frontmatter fields
# ---------------------------------------------------------------------------


def _check_missing_frontmatter(pages: list[PageInfo]) -> list[LintIssue]:
    """Check for required frontmatter fields per page type."""
    issues: list[LintIssue] = []

    required: dict[PageType, list[str]] = {
        PageType.TOPIC: ["title", "description", "tags", "parent", "type"],
        PageType.SOURCE: ["title", "description", "authors", "date", "tags", "doi", "type"],
        PageType.INDEX: ["title", "type"],
        PageType.PROCESSED: ["title", "type"],
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
        for field in reqs:
            val = page.meta.get(field)
            if val is None or val == "":
                issues.append(
                    LintIssue(
                        kind=IssueKind.MISSING_FRONTMATTER,
                        severity=IssueSeverity.ERROR,
                        file=page.path,
                        message=f"Missing required frontmatter field: '{field}'",
                    )
                )

    return issues


# ---------------------------------------------------------------------------
# Check: missing ## sections
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Check: dispute chronology
# ---------------------------------------------------------------------------


def _check_dispute_chronology(pages: list[PageInfo]) -> list[LintIssue]:
    """Check that Disputed markers lead with the earlier publication year.

    Supports both legacy format (> **Disputed:**) and Obsidian callout
    format (> [!warning] Disputed).
    """
    issues: list[LintIssue] = []

    for page in pages:
        # Legacy format: > **Disputed:** ...
        for m in _DISPUTED_BOLD_RE.finditer(page.body):
            _check_years(page, m.group(0), issues)

        # Callout format: > [!warning] Disputed\n> body lines...
        for m in _CALLOUT_DISPUTED_RE.finditer(page.body):
            # Collect continuation lines (> ...)
            start = m.end()
            lines = [m.group(0)]
            for line in page.body[start:].split("\n"):
                stripped = line.strip()
                if stripped.startswith(">"):
                    lines.append(line)
                elif stripped == "":
                    continue  # skip blank lines within the callout
                else:
                    break
            callout_text = "\n".join(lines)
            _check_years(page, callout_text, issues)

    return issues


def _check_years(
    page: PageInfo, text: str, issues: list[LintIssue]
) -> None:
    years = [int(y) for y in _YEAR_RE.findall(text)]
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
                context=text[:120],
            )
        )


# ---------------------------------------------------------------------------
# Check: split candidates
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Check: folder structure conventions
# ---------------------------------------------------------------------------


def _check_structure(pages: list[PageInfo], root: Path) -> list[LintIssue]:
    """Check folder structure conventions."""
    issues: list[LintIssue] = []

    for page in pages:
        if page.page_type != PageType.TOPIC:
            continue

        folder = page.path.parent
        if folder != root and folder.name != page.path.stem:
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
