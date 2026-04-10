"""Shared data types for agent-wiki."""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class PageType(Enum):
    TOPIC = "topic"
    SOURCE = "source"
    INDEX = "index"
    LOG = "log"
    STATUS = "status"


class IssueSeverity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class IssueKind(Enum):
    BROKEN_LINK = "broken_link"
    MISSING_BACKLINK = "missing_backlink"
    ORPHAN_PAGE = "orphan_page"
    BROKEN_BREADCRUMB = "broken_breadcrumb"
    MISSING_FRONTMATTER = "missing_frontmatter"
    MISSING_SECTION = "missing_section"
    DISPUTE_CHRONOLOGY = "dispute_chronology"
    SPLIT_CANDIDATE = "split_candidate"
    STRUCTURE_MISMATCH = "structure_mismatch"


@dataclass(frozen=True)
class WikiLink:
    """A parsed wiki-link with position info for rewriting."""

    target: str
    display: str | None = None
    start: int = 0
    end: int = 0


@dataclass(frozen=True)
class LintIssue:
    """A single lint finding."""

    kind: IssueKind
    severity: IssueSeverity
    file: Path
    message: str
    context: str = ""
    suggestion: str = ""

    def to_dict(self) -> dict:
        return {
            "kind": self.kind.value,
            "severity": self.severity.value,
            "file": str(self.file),
            "message": self.message,
            "context": self.context,
            "suggestion": self.suggestion,
        }


@dataclass
class PageInfo:
    """Parsed metadata about a wiki page."""

    path: Path
    title: str = ""
    page_type: PageType | None = None
    parent: str | None = None
    authors: list[str] = field(default_factory=list)
    year: int | None = None
    file_ref: str | None = None
    outbound_links: list[str] = field(default_factory=list)
    sections: list[str] = field(default_factory=list)
    line_count: int = 0
    breadcrumb: str | None = None
    body: str = ""


@dataclass
class WikiStats:
    """Summary statistics for the wiki."""

    total_pages: int = 0
    topic_pages: int = 0
    source_pages: int = 0
    total_links: int = 0
    unique_links: int = 0
    orphan_count: int = 0
    broken_link_count: int = 0
    missing_backlink_count: int = 0
    pages_by_type: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "total_pages": self.total_pages,
            "topic_pages": self.topic_pages,
            "source_pages": self.source_pages,
            "total_links": self.total_links,
            "unique_links": self.unique_links,
            "orphan_count": self.orphan_count,
            "broken_link_count": self.broken_link_count,
            "missing_backlink_count": self.missing_backlink_count,
            "pages_by_type": self.pages_by_type,
        }
