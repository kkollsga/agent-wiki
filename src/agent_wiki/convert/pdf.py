"""PDF to structured markdown conversion using pymupdf4llm.

Produces markdown with proper headings, paragraphs, tables, and
extracted images — not flat text.
"""

import re
import shutil
from pathlib import Path

import fitz  # PyMuPDF
import pymupdf4llm


def _sanitize_for_pymupdf(p: str) -> str:
    """Match pymupdf4llm's internal path sanitization."""
    return p.replace(" ", "_").replace("(", "-").replace(")", "-")


def convert_pdf(
    pdf_path: Path,
    output_path: Path,
    *,
    img_dir: Path | None = None,
    base_dir: Path | None = None,
    max_dpi: int = 150,
    extract_images: bool = True,
    pages: list[int] | None = None,
) -> Path:
    """Convert a PDF to a structured markdown file with extracted images.

    Uses pymupdf4llm for layout-aware markdown: headings, paragraphs,
    tables, bold/italic are all detected from font metrics.

    Image workflow:
    1. pymupdf4llm writes images to a sanitized temp path (underscores)
    2. Post-processing renames images to short names (0001-01.png)
    3. Folder is renamed back to the original name (with spaces)
    4. Markdown references are updated to match
    5. If base_dir given, image paths are rewritten to be relative to it

    Args:
        pdf_path: Path to the input PDF.
        output_path: Path for the output .md file.
        img_dir: Directory for extracted images. Defaults to output_path.parent / "img".
        base_dir: If given, image paths in the markdown are rewritten to be
            relative to this directory (typically the wiki root).
        max_dpi: DPI for extracted images (default 150).
        extract_images: Whether to extract embedded images (default True).
        pages: List of 0-indexed page numbers to convert. None = all pages.

    Returns:
        The output_path.
    """
    pdf_path = Path(pdf_path)
    output_path = Path(output_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    if img_dir is None:
        img_dir = output_path.parent / "img"

    # Get page count from PDF
    doc = fitz.open(str(pdf_path))
    page_count = len(doc)
    doc.close()

    # Step 1: Let pymupdf4llm write to a sanitized path (it insists on _)
    sanitized_img_dir = Path(_sanitize_for_pymupdf(str(img_dir)))
    if extract_images:
        sanitized_img_dir.mkdir(parents=True, exist_ok=True)

    md = pymupdf4llm.to_markdown(
        str(pdf_path),
        pages=pages,
        write_images=extract_images,
        image_path=str(sanitized_img_dir),
        image_format="png",
        dpi=max_dpi,
        image_size_limit=0.05,
    )

    # Step 2: Post-process — shorten image names and rename folder to spaces
    if extract_images:
        md = _post_process_images(md, sanitized_img_dir, img_dir)

    # Step 3: Rewrite image paths to be relative to base_dir (wiki root)
    if base_dir is not None:
        base_dir = Path(base_dir).resolve()
        try:
            cwd = Path.cwd().resolve()
            prefix = str(base_dir.relative_to(cwd))
            if not prefix.endswith("/"):
                prefix += "/"
            md = re.sub(
                r"(!\[[^\]]*\]\()" + re.escape(prefix),
                r"\1",
                md,
            )
        except ValueError:
            pass

    # Step 4: Extract metadata and build frontmatter
    fm = _extract_frontmatter(md, pdf_path, page_count)
    content = fm + md

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return output_path


def _extract_frontmatter(md: str, pdf_path: Path, page_count: int) -> str:
    """Extract metadata from converted markdown and build rich frontmatter.

    Searches the paper text for title, authors, DOI, date, and journal.
    Falls back to filename/defaults for fields that can't be extracted.
    """
    head = "\n".join(md.split("\n")[:200])

    # --- DOI ---
    doi = ""
    doi_match = re.search(r"(?:doi[:\s]*|DOI[:\s]*)?(10\.\d{4,}/[^\s,;)\"']+)", head)
    if doi_match:
        doi = doi_match.group(1).rstrip(".")

    # --- Title ---
    title = ""
    candidates = []
    for m in re.finditer(r"^##\s+\*\*(.+?)\*\*\s*$", head, re.MULTILINE):
        t = m.group(1).strip()
        if len(t) > 15 and not re.match(r"^\d+\.\s", t):
            candidates.append(t)
    for m in re.finditer(r"^#\s+(.+)$", head, re.MULTILINE):
        t = m.group(1).strip().strip("*")
        if len(t) > 15 and not re.match(r"^\d+\.\s", t):
            candidates.append(t)
    if candidates:
        title = max(candidates, key=len)
    if not title:
        title = pdf_path.stem

    # --- Authors ---
    authors = ""
    lines = head.split("\n")
    title_idx = 0
    for i, line in enumerate(lines[:60]):
        if title and title[:30] in line:
            title_idx = i
            break
    for line in lines[title_idx + 1 : title_idx + 16]:
        clean = re.sub(r"[_*]", "", line).strip()
        if not clean or clean.startswith("#") or clean.startswith("!") or clean.startswith("|"):
            continue
        if len(clean) > 500:
            continue
        initials = re.findall(r"[A-Z](?:\.\s*-?\s*[A-Z])*\.", clean)
        has_and = " and " in clean
        if len(initials) >= 2 or (len(initials) >= 1 and has_and):
            authors = clean
            break

    # --- Date / Year ---
    date = ""
    year_match = re.search(r"(?:19|20)\d{2}", head[:3000])
    if year_match:
        date = f"{year_match.group(0)}-01-01"

    # --- Journal ---
    journal = ""
    for line in head.split("\n")[:80]:
        if "![" in line or ".png" in line or "http" in line:
            continue
        clean = line.strip()
        jm = re.search(r"_([A-Z][^_]{10,?})_", clean)
        if jm:
            journal = jm.group(1).strip().rstrip(",.")
            break
        jm = re.search(
            r"((?:Marine|Geological|Journal of|Sediment|Earth|Petroleum|Basin)[A-Za-z\s,&]+)",
            clean,
        )
        if jm and len(jm.group(1)) > 15:
            journal = jm.group(1).strip().rstrip(",.")
            break

    # --- Build frontmatter ---
    safe_title = title.replace('"', '\\"')
    fm_lines = ["---"]
    fm_lines.append(f'title: "{safe_title}"')
    fm_lines.append('description: ""')
    if authors:
        safe_authors = authors.replace('"', '\\"')
        fm_lines.append(f'authors: "{safe_authors}"')
    else:
        fm_lines.append('authors: ""')
    fm_lines.append(f"date: {date}" if date else 'date: ""')
    fm_lines.append(f'doi: "{doi}"' if doi else 'doi: ""')
    if journal:
        safe_journal = journal.replace('"', '\\"')
        fm_lines.append(f'journal: "{safe_journal}"')
    fm_lines.append("tags: []")
    fm_lines.append(f"pages: {page_count}")
    fm_lines.append("type: processed")
    fm_lines.append("---\n")

    return "\n".join(fm_lines)


def _post_process_images(md: str, sanitized_dir: Path, target_dir: Path) -> str:
    """Shorten image filenames and rename folder from sanitized to original.

    1. Rename files: '<stem>.pdf-0001-01.png' -> '0001-01.png'
    2. Rename folder: 'img/Some_Paper' -> 'img/Some Paper' (if different)
    3. Update all image references in the markdown
    """
    if not sanitized_dir.exists():
        return md

    # Shorten image filenames
    for img_file in sorted(sanitized_dir.glob("*.png")):
        old_name = img_file.name
        match = re.search(r"(\d{4}-\d{2})\.png$", old_name)
        if not match:
            continue
        new_name = match.group(1) + ".png"
        new_path = img_file.parent / new_name

        if new_path != img_file and not new_path.exists():
            img_file.rename(new_path)
            md = md.replace(old_name, new_name)

    # Rename folder from sanitized (underscores) to original (spaces)
    if sanitized_dir != target_dir:
        if target_dir.exists() and target_dir != sanitized_dir:
            for f in sanitized_dir.iterdir():
                shutil.move(str(f), str(target_dir / f.name))
            sanitized_dir.rmdir()
        elif not target_dir.exists():
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            sanitized_dir.rename(target_dir)

        # Update paths in markdown — absolute form
        md = md.replace(str(sanitized_dir), str(target_dir))
        # Also replace CWD-relative form (pymupdf4llm emits relative paths)
        try:
            cwd = Path.cwd().resolve()
            san_rel = str(sanitized_dir.resolve().relative_to(cwd))
            tgt_rel = str(target_dir.resolve().relative_to(cwd))
            md = md.replace(san_rel, tgt_rel)
        except ValueError:
            pass
        # Fallback: replace just the directory name component
        if sanitized_dir.name != target_dir.name:
            md = md.replace(
                f"img/{sanitized_dir.name}/", f"img/{target_dir.name}/"
            )

    return md
