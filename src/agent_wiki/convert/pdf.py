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

    Args:
        pdf_path: Path to the input PDF.
        output_path: Path for the output .md file.
        img_dir: Directory for extracted images. Defaults to output_path.parent / "img".
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

    # Build frontmatter from PDF metadata
    doc = fitz.open(str(pdf_path))
    meta = doc.metadata or {}
    page_count = len(doc)
    doc.close()

    frontmatter_lines = ["---"]
    title = meta.get("title", "") or pdf_path.stem
    frontmatter_lines.append(f'title: "{title}"')
    author = meta.get("author", "")
    if author:
        frontmatter_lines.append(f'author: "{author}"')
    frontmatter_lines.append(f"pages: {page_count}")
    frontmatter_lines.append("---")
    frontmatter_lines.append("")

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

    # Combine frontmatter + body
    content = "\n".join(frontmatter_lines) + md

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")

    return output_path


def _post_process_images(md: str, sanitized_dir: Path, target_dir: Path) -> str:
    """Shorten image filenames and rename folder from sanitized to original.

    1. Rename files: '<stem>.pdf-0001-01.png' → '0001-01.png'
    2. Rename folder: 'img/Some_Paper' → 'img/Some Paper' (if different)
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
            # Target already exists — merge into it
            for f in sanitized_dir.iterdir():
                shutil.move(str(f), str(target_dir / f.name))
            sanitized_dir.rmdir()
        elif not target_dir.exists():
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            sanitized_dir.rename(target_dir)

        # Update paths in markdown
        md = md.replace(str(sanitized_dir), str(target_dir))

    return md
